// One desk folder: a sidebar section titled with the desk's name.
//
// A click on the title folds and unfolds the folder: it opens nothing and is
// never selected. On the title while hovered: rename (in place) and close
// (deletes the desk, no confirm; a tab on it goes home). No menu, no resize
// edge. The title drags the desk (`DESK_MIME`) to move it above or under
// another, and takes a plane, item or pane at the end of the desk.
//
// An empty desk's body is a dashed "Drag planes here" block, a drop target
// for its first item. Otherwise the body is its rows (./folders.ts
// `folderRows`, drawn by ./DeskRows.tsx), each a drop site whose aim is
// ./folders.ts `rowAim`. The mark is the tree's: a line between rows, a ring
// on a row or a title.

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
	sidebarDropLineStyle,
	sidebarRowWrap,
} from "../design";
import { DESK_MIME, type Target } from "../desk/dnd";
import { setDragChip } from "../desk/drag";
import type { Side } from "../desk/model";
import type { Folder } from "./DeskFolders";
import { DeskRow, type DragProps, type DropProps } from "./DeskRows";
import { edgeAt } from "./drag";
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

/** Where a drag is aimed in the folders now: a desk's title (`key` null) or one of its rows. */
export type Aimed = { desk: string; key: string | null; mark: Mark } | null;

/** Drag handlers for a drop site whose aim is `aimAt`'s, null where nothing lands. */
export type DropHandlers = (
	aimAt: (e: React.DragEvent<HTMLElement>) => { aim: Aim; key: string | null; desk: string } | null,
) => DropProps;

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
}) {
	const { id, desk, folded, rows } = folder;
	const title = deskLabel(desk.name);
	const end: Target = titleTarget(id);
	const drops = dropHandlers(() => ({
		aim: { target: end, mark: { ring: true } },
		key: null,
		desk: id,
	}));
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

	return (
		<SidebarSection
			id={folderKey(id)}
			title={title}
			folded={folded}
			onFoldedChange={(next) => setFolded(folderKey(id), next)}
			head={head}
			headClassName={cn(
				aim && aim.key === null && sidebarDropInto,
				reorder.moving === id && sidebarDragging,
			)}
			headMark={
				reorder.aim ? (
					<span
						aria-hidden="true"
						className={sidebarDropLine(reorder.aim === "before" ? "before" : "after")}
						style={{ left: 0 }}
					/>
				) : null
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
					className={cn(sidebarDeskEmpty, aim?.key === EMPTY_KEY && sidebarDropInto)}
					{...dropHandlers(() => ({
						aim: { target: end, mark: { ring: true } },
						key: EMPTY_KEY,
						desk: id,
					}))}
				>
					Drag planes here
				</div>
			)}
			{rows.map((row, i) => {
				const mark = aim?.key === row.key ? aim.mark : null;
				const className = mark?.ring
					? sidebarDropInto
					: lifted === row.key
						? sidebarDragging
						: undefined;
				const drop = dropHandlers((e) => ({
					aim: rowAim(
						id,
						row,
						edgeAt(e.currentTarget, e.clientY),
						sideAt(e.currentTarget, e.clientX),
					),
					key: row.key,
					desk: id,
				}));
				return (
					<div key={row.key} role="none" className={sidebarRowWrap}>
						<DeskRow
							deskId={id}
							row={row}
							next={rows[i + 1]}
							looks={looks}
							selected={row.key === selected}
							className={className}
							drop={drop}
							dragOf={dragOf}
						/>
						{mark && !mark.ring ? (
							<span
								className={sidebarDropLine(mark.edge)}
								style={sidebarDropLineStyle(mark.depth)}
								aria-hidden="true"
							/>
						) : null}
					</div>
				);
			})}
		</SidebarSection>
	);
}
