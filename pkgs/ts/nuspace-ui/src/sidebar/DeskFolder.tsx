// One desk folder: a sidebar section titled with the desk's name.
//
// A click on the title folds and unfolds the folder: it opens nothing and is
// never selected. On the title while hovered: rename (in place) and close
// (deletes the desk, no confirm; a tab on it goes home). No menu, no resize
// edge. The title drags the desk (`DESK_MIME`) to move it above or under
// another, and takes a plane, item or pane: pinned at the end of the desk,
// or from its bottom 20%, once rested on, at the top, over the first row.
//
// An empty desk's body is a dashed "Drag planes here" block, a drop target
// for its first item. Otherwise the body is its rows (./folders.ts
// `folderRows`, drawn by ./DeskRows.tsx), and under the last row the space
// that pins at the end of the desk, as the Planes tree's tail. The body
// takes the drop for its rows: the row under the pointer (./drag.ts `rowAt`;
// the gaps between rows keep the aim) aims by ./folders.ts `rowAim`. The
// marks are the tree's (./DropMarks.tsx): a line on a gap between rows, a
// ring on a row or a title, each saying what the drop does.

import { cn } from "@nustackdev/ui-kit";
import { Pen, X } from "lucide-react";
import type * as React from "react";
import type { PlaneLook } from "../core/looks";
import { closeDesk, renameDesk } from "../core/router";
import {
	sidebarDeskEmpty,
	sidebarDragging,
	sidebarDropInto,
	sidebarDropLine,
	sidebarDropQuiet,
	sidebarDropRefused,
	sidebarDropTail,
	sidebarDropZone,
	sidebarRowWrap,
} from "../design";
import { DESK_MIME, type Target } from "../desk/dnd";
import { setDragChip } from "../desk/drag";
import type { Side } from "../desk/model";
import type { Folder } from "./DeskFolders";
import { DeskRow, type DragProps, type DropProps } from "./DeskRows";
import { DropHint, DropLine } from "./DropMarks";
import { bandAt, DROP_ROW, DROP_TAIL, edgeHolds, type Hint, rowAt } from "./drag";
import {
	type Aim,
	deskLabel,
	folderKey,
	type Mark,
	rowAim,
	setFolded,
	titleTarget,
} from "./folders";
import { SectionAction, SidebarSection } from "./SidebarSection";

/**
 * Where a drag is aimed in the folders now: a desk's title (`key` null) or
 * one of its rows, the drop, its mark, what it says and whether it lands. A
 * refused one is always a ring.
 */
export type Aimed = {
	desk: string;
	key: string | null;
	mark: Mark;
	target: Target;
	hint: Hint;
	ok: boolean;
} | null;

/**
 * What a drop site's pointer is over: an aim at a row or title, `{ keep }`
 * over no row of desk `keep` (the gaps between rows), where the aim holds, or null.
 */
export type AimHit = { aim: Aim; key: string | null; desk: string } | { keep: string } | null;

/** Drag handlers for a drop site whose aim is `aimAt`'s. */
export type DropHandlers = (aimAt: (e: React.DragEvent<HTMLElement>) => AimHit) => DropProps;

/** The ring of `aim`, a drop or a refusal. */
const ringOf = (aim: NonNullable<Aimed>) => (aim.ok ? sidebarDropInto : sidebarDropRefused);

/** What a folder's title needs to move desks: who is moving, where it would land, and the calls. */
export type DeskReorder = {
	moving: string | null;
	aim: "before" | "after" | null;
	onStart: () => void;
	onEnd: () => void;
	onAim: (edge: "before" | "after" | null) => void;
	onDrop: (dragged: string, edge: "before" | "after") => void;
};

/** The aim key of an empty desk's body, the drop target for its first item. */
const EMPTY_KEY = "empty";

/** The pointer's half of a row: the side a drop onto a plane item goes. */
function sideAt(el: HTMLElement, clientX: number): Side {
	const r = el.getBoundingClientRect();
	return clientX < r.left + r.width / 2 ? "left" : "right";
}

export function DeskFolder({
	folder,
	reorder,
	looks,
	selected,
	aim,
	lifted,
	renaming,
	onRename,
	dropHandlers,
	dragOf,
	settled,
}: {
	folder: Folder;
	/** Moving desks by their titles. */
	reorder: DeskReorder;
	looks: Record<string, PlaneLook>;
	selected: string | null;
	aim: Aimed;
	lifted: string | null;
	renaming: boolean;
	onRename: (on: boolean) => void;
	dropHandlers: DropHandlers;
	dragOf: (key: string, write: (dt: DataTransfer) => void) => DragProps;
	/** Whether the pointer has rested on row `key` (./drag.ts `useSettle`). */
	settled: (key: string) => boolean;
}) {
	const { id, desk, folded, rows } = folder;
	const title = deskLabel(desk.name);
	const end: Target = titleTarget(id);
	// The gap a line is on: after a row and before the next are one gap.
	const at = aim?.key ? rows.findIndex((r) => r.key === aim.key) : -1;
	const line =
		aim && !aim.mark.ring && at >= 0
			? { gap: at + (aim.mark.edge === "after" ? 1 : 0), depth: aim.mark.depth, hint: aim.hint }
			: null;
	const first = rows[0];
	// The title, as a row with no top edge: its bottom 20%, once rested on (or
	// with the line already on the gap under it), pins at the top of the
	// desk, the line over the first row; the rest pins at the end, ringed.
	const drops = dropHandlers((e) => {
		const r = e.currentTarget.getBoundingClientRect();
		const band = bandAt(e.clientY - r.top, r.height);
		const rested = settled(`title:${id}`);
		const edge = edgeHolds(band === "after" ? "after" : "into", -1, rested, line?.gap ?? null);
		if (edge === "after" && first) {
			return {
				aim: {
					target: { kind: "between", desk: id, index: 0 },
					mark: { ring: false, edge: "before", depth: 0 },
				},
				key: first.key,
				desk: id,
			};
		}
		return { aim: { target: end, mark: { ring: true } }, key: null, desk: id };
	});
	// The title takes two drags: a plane, item or pane (into the desk, at its
	// end) and a desk (moved above or under this one).
	const isDesk = (e: React.DragEvent) => e.dataTransfer.types.includes(DESK_MIME);
	const edgeOf = (e: React.DragEvent<HTMLElement>): "before" | "after" => {
		const r = e.currentTarget.getBoundingClientRect();
		return e.clientY < r.top + r.height / 2 ? "before" : "after";
	};
	const head: React.HTMLAttributes<HTMLDivElement> = {
		draggable: !renaming,
		onDragStart: (e) => {
			setDragChip(e);
			e.dataTransfer.effectAllowed = "move";
			e.dataTransfer.setData(DESK_MIME, id);
			reorder.onStart();
		},
		onDragEnd: reorder.onEnd,
		onDragOver: (e) => {
			if (!isDesk(e)) return drops.onDragOver?.(e);
			if (reorder.moving === id) return;
			e.preventDefault();
			e.dataTransfer.dropEffect = "move";
			reorder.onAim(edgeOf(e));
		},
		onDragLeave: (e) => {
			if (!isDesk(e)) return drops.onDragLeave?.(e);
			if (!e.currentTarget.contains(e.relatedTarget as Node | null)) reorder.onAim(null);
		},
		onDrop: (e) => {
			if (!isDesk(e)) return drops.onDrop?.(e);
			const dragged = e.dataTransfer.getData(DESK_MIME);
			e.preventDefault();
			e.stopPropagation();
			if (dragged && dragged !== id) reorder.onDrop(dragged, edgeOf(e));
			else reorder.onEnd();
		},
	};

	// The body: the row under the pointer aims (./folders.ts
	// `rowAim`), its edges only once the pointer has rested on it.
	const body = dropHandlers((e) => {
		// Under the last row: a pin at the end of the desk, at once.
		const last = rows.at(-1);
		if (last && (e.target as Element).closest?.(`[${DROP_TAIL}]`)) {
			return {
				aim: { target: end, mark: { ring: false, edge: "after", depth: 0 } },
				key: last.key,
				desk: id,
			};
		}
		const hit = rowAt(e, e.currentTarget);
		const i = hit ? rows.findIndex((r) => r.key === hit.el.getAttribute(DROP_ROW)) : -1;
		const row = rows[i];
		if (!hit || !row) return { keep: id };
		const band = edgeHolds(bandAt(hit.y, hit.height), i, settled(row.key), line?.gap ?? null);
		return {
			aim: rowAim(id, row, band, sideAt(hit.el, e.clientX)),
			key: row.key,
			desk: id,
		};
	});

	const items: React.ReactNode[] = [];
	rows.forEach((row, i) => {
		const ring = aim?.key === row.key && aim.mark.ring ? aim : null;
		// The line on the gap above this row, or under the last.
		const edge =
			line?.gap === i
				? "before"
				: line?.gap === rows.length && i === rows.length - 1
					? "after"
					: null;
		const near = line !== null && (line.gap === i || line.gap === i + 1);
		items.push(
			<div
				key={row.key}
				role="none"
				className={cn(sidebarRowWrap, near && sidebarDropQuiet)}
				{...{ [DROP_ROW]: row.key }}
			>
				<DeskRow
					deskId={id}
					row={row}
					next={rows[i + 1]}
					looks={looks}
					selected={row.key === selected}
					className={ring ? ringOf(ring) : lifted === row.key ? sidebarDragging : undefined}
					dragOf={dragOf}
				/>
				{ring ? <DropHint hint={ring.hint} at /> : null}
				{edge && line ? <DropLine edge={edge} depth={line.depth} hint={line.hint} /> : null}
			</div>,
		);
	});

	return (
		<SidebarSection
			id={folderKey(id)}
			title={title}
			folded={folded}
			onFoldedChange={(next) => setFolded(folderKey(id), next)}
			head={head}
			headClassName={cn(
				aim && aim.key === null && ringOf(aim),
				reorder.moving === id && sidebarDragging,
			)}
			headMark={
				<>
					{reorder.aim ? (
						<span
							aria-hidden="true"
							className={sidebarDropLine(reorder.aim === "before" ? "before" : "after")}
							style={{ left: 0 }}
						/>
					) : null}
					{aim && aim.key === null ? <DropHint hint={aim.hint} at /> : null}
				</>
			}
			rename={
				renaming
					? {
							label: `Rename ${title}`,
							onCommit: (value) => {
								onRename(false);
								const next = value.trim();
								if (next && next !== desk.name) renameDesk(id, next);
							},
							onCancel: () => onRename(false),
						}
					: null
			}
			actions={
				<>
					<SectionAction label={`Rename ${title}`} tip="Rename" onClick={() => onRename(true)}>
						<Pen />
					</SectionAction>
					<SectionAction label={`Close ${title}`} tip="Close" onClick={() => closeDesk(id)}>
						<X />
					</SectionAction>
				</>
			}
		>
			{rows.length ? null : (
				<div
					data-desk-empty={id}
					className={cn(sidebarDeskEmpty, aim?.key === EMPTY_KEY && ringOf(aim))}
					{...dropHandlers(() => ({
						aim: { target: end, mark: { ring: true } },
						key: EMPTY_KEY,
						desk: id,
					}))}
				>
					Drag planes here
					{aim?.key === EMPTY_KEY ? <DropHint hint={aim.hint} at /> : null}
				</div>
			)}
			{rows.length ? (
				<div role="none" className={sidebarDropZone} {...body}>
					{items}
					{/* Under the last row: a drop here pins at the end of the desk. */}
					<div className={sidebarDropTail} {...{ [DROP_TAIL]: "" }} />
				</div>
			) : null}
		</SidebarSection>
	);
}
