// The plane screen: one plane, flattened for a phone. The header every
// screen wears on top (../Header.tsx: its icon, its title), then its cells
// one under another at the full width, in the layout's reading
// order (a strip column by column), the order desktop's keyboard walks. No
// gutters, no grips, no strips, no `/` menu, no box select: the phone reads
// and uses a plane, it does not lay one out.
//
// It reads the same PaneRef node desktop's pane does (../../pane/state.ts)
// and sends the same ops on it, so nothing about the server changes. A cell
// shows what it draws (./MobileCell.tsx). A long-press opens its sheet
// (./CellSheet.tsx); the floating + opens the add sheet (./AddCellSheet.tsx),
// which adds at the end.
//
// The server's scroll commands and its follow-the-end apply here as on
// desktop (../../pane/scroll.ts). `data-pane` is the plane shown, so a link
// tapped in a cell navigates this screen in place, as it would its pane.
//
// A plane deleted while it is on screen turns absent `missing`, and the
// screen leaves for home, as desktop's pane does.

import type { Path } from "@nustackdev/ui-core";
import { pathKey } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePlaneLooks } from "../../core/looks";
import { leavePlanes } from "../../core/router";
import { notifyOp } from "../../core/wire";
import { mobilePlaneBody, mobilePlaneEmpty, mobilePlaneScroll, mobileScreen } from "../../design";
import { PlaneIcon } from "../../icon/PlaneIcon";
import { planeIcon } from "../../icon/parse";
import { GoHome, NotFoundBody } from "../../pane/NotFound";
import { useScroller } from "../../pane/scroll";
import {
	markScrolled,
	panePath,
	usePaneAbsent,
	usePaneCells,
	usePaneFollow,
	usePaneHead,
	usePaneLayout,
	usePaneScroll,
	usePaneScrolled,
} from "../../pane/state";
import { ABSENT_TEXT, TITLE_FALLBACK } from "../../pane/titles";
import { ViewerSkeleton } from "../../pane/ViewerSkeleton";
import { cellUiPath } from "../../plane/cell/address";
import { createLanded } from "../../plane/create";
import { inReadingOrder, plainLayout } from "../../plane/layout/model";
import type { Notify, Ops } from "../../plane/ops";
import type { CellSpec } from "../../plane/types";
import { deletedCells } from "../../refs/toast";
import { MobileHeader } from "../Header";
import { AddCellSheet } from "./AddCellSheet";
import { type CellPressed, CellSheet, SourceScreen } from "./CellSheet";
import { MobileCell } from "./MobileCell";
import { appendCell } from "./model";

export function MobilePlane({
	viewerPath,
	planeId,
	cellSpecs,
	active = true,
	titled = true,
}: {
	/** The ViewerRef node: the panes and every cell's ui hang under it. */
	viewerPath: Path;
	planeId: string;
	/** The registered Cells: what the + sheet lists. */
	cellSpecs: CellSpec[];
	/** Whether it is the plane on screen, the one the + adds to: a desk's other pages are not. */
	active?: boolean;
	/** Whether it wears its own header: a desk's header names its pages instead. */
	titled?: boolean;
}) {
	const viewerKey = pathKey(viewerPath);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const path = useMemo(() => panePath(viewerPath, planeId), [viewerKey, planeId]);
	const head = usePaneHead(path);
	const shipped = usePaneCells(path);
	const shippedLayout = usePaneLayout(path);
	const absent = usePaneAbsent(path);
	const editable = head?.meta.editable ?? false;

	// The layout as drawn, and the cells in its reading order: the stack.
	const layout = useMemo(
		() => shippedLayout ?? plainLayout(shipped ?? []),
		[shippedLayout, shipped],
	);
	// Deleted here and not yet dropped by the server: out of sight meanwhile.
	const [leaving, setLeaving] = useState<string[]>([]);
	const cells = useMemo(
		() => (shipped ? inReadingOrder(shipped, layout).filter((c) => !leaving.includes(c.id)) : null),
		[shipped, layout, leaving],
	);

	// One ref per op, on this pane's own node: the path says the plane.
	const notify = useCallback<Notify>(
		(op, args) => notifyOp<Ops, typeof op>(path, op, args),
		[path],
	);

	// The body's scroll, as the node says.
	const viewport = useRef<HTMLDivElement | null>(null);
	const content = useRef<HTMLDivElement | null>(null);
	const onScrolled = useCallback((seq: string) => markScrolled(path, seq), [path]);
	useScroller({
		viewport,
		content,
		follow: usePaneFollow(path),
		scroll: usePaneScroll(path),
		applied: usePaneScrolled(path),
		ready: head != null && shipped != null,
		onApplied: onScrolled,
	});

	// A screen that had its plane and turns missing leaves: the plane went.
	const had = useRef(false);
	useEffect(() => {
		if (head) had.current = true;
	}, [head]);
	useEffect(() => {
		if (absent === "missing" && had.current) leavePlanes([planeId], true);
	}, [absent, planeId]);

	// What the server shipped: creates landed, and deletes done with.
	const added = useRef<string | null>(null);
	useEffect(() => {
		if (!shipped) return;
		const live = new Set(shipped.map((c) => c.id));
		for (const id of live) createLanded(id);
		setLeaving((ids) => (ids.some((id) => !live.has(id)) ? ids.filter((id) => live.has(id)) : ids));
		// The cell just added comes into view as it lands.
		const id = added.current;
		if (id && live.has(id)) {
			added.current = null;
			content.current
				?.querySelector(`[data-cell="${CSS.escape(id)}"]`)
				?.scrollIntoView({ block: "nearest", behavior: "smooth" });
		}
	}, [shipped]);

	const [pressed, setPressed] = useState<CellPressed>(null);
	const [source, setSource] = useState<string | null>(null);
	const byId = useMemo(() => new Map((shipped ?? []).map((c) => [c.id, c])), [shipped]);

	const onAdd = (spec: CellSpec) => {
		added.current = appendCell(notify, layout, spec.name);
	};
	const onDelete = (id: string) => {
		notify("cell.delete", { cell_id: id });
		setLeaving((ids) => [...ids, id]);
		deletedCells([id]);
	};

	const title = head?.title || TITLE_FALLBACK;

	return (
		<section
			className={`${mobileScreen} flex-col`}
			aria-label={absent ? planeId : title}
			data-pane={planeId}
			data-focused={active ? "" : undefined}
			data-plane-screen=""
		>
			{titled ? <PlaneHeader planeId={planeId} head={head} absent={!!absent} /> : null}
			<div ref={viewport} className={mobilePlaneScroll}>
				<div ref={content} className={mobilePlaneBody}>
					{absent ? (
						<NotFoundBody text={ABSENT_TEXT[absent]} action={<GoHome />} />
					) : !head || !cells ? (
						<ViewerSkeleton />
					) : (
						<>
							{cells.map((cell) => (
								<MobileCell
									key={cell.id}
									cell={cell}
									uiPath={cellUiPath(viewerPath, cell.id)}
									pressed={pressed?.id === cell.id}
									onLongPress={() => setPressed({ id: cell.id, step: "actions" })}
								/>
							))}
							{cells.length === 0 ? (
								<p className={mobilePlaneEmpty}>
									{editable ? "No cells yet. Tap + to add one." : "No cells on this plane."}
								</p>
							) : null}
						</>
					)}
				</div>
			</div>
			<CellSheet
				cell={pressed ? byId.get(pressed.id) : undefined}
				pressed={pressed}
				editable={editable}
				onPressed={setPressed}
				onRestart={(id) => notify("cell.restart", { cell_id: id })}
				onSource={setSource}
				onDelete={onDelete}
			/>
			<SourceScreen
				cell={source ? byId.get(source) : undefined}
				open={source !== null}
				onClose={() => setSource(null)}
			/>
			{editable && active ? <AddCellSheet cellSpecs={cellSpecs} onPick={onAdd} /> : null}
		</section>
	);
}

/**
 * The plane's header: its icon and its title, from its head once it lands,
 * from the desks' looks before. An absent plane is named by its id.
 */
function PlaneHeader({
	planeId,
	head,
	absent,
}: {
	planeId: string;
	head: ReturnType<typeof usePaneHead>;
	absent: boolean;
}) {
	const look = usePlaneLooks(useMemo(() => [planeId], [planeId]))[planeId];
	const icon = head ? head.meta.icon : look?.icon;
	const title = absent ? planeId : head?.title || look?.title || TITLE_FALLBACK;
	return (
		<MobileHeader
			icon={icon ? <PlaneIcon icon={planeIcon(String(icon))} /> : undefined}
			title={title}
		/>
	);
}
