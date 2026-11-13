// Desk: the canvas, the ViewerRef node's component. It draws the one thing
// the router shows (../core/router.ts):
//
//   solo     a plane outside any desk: one pane, the whole canvas
//   item     a desk item. A plane item: its plane alone, full size, like
//            solo. A strip: one row of columns left to right, each the
//            canvas's full height with its panes stacked in it. The row
//            scrolls sideways only, in the kit's scroll area
//   desk     an empty desk: a hint to drag a plane in
//   pending  a spinner, until the desks or the roles land
//   missing  not found: a desk, a desk's item or a url that is none of
//            them, drawn as a pane (../pane/NotFound.tsx)
//
// On a desk (an empty desk or one of its items) the desk header runs across
// the top, over what it shows (./DeskHeader.tsx): the desk's name and close,
// nothing else. A solo plane has none.
//
// A pane draws the plane it shows: its recent, else its original. A link
// inside a desk item navigates that plane item or pane in place, through the
// router's anchor rule on the shell, which finds the pane by `data-pane`.
//
// Focus and scroll are this tab's, in memory, never in the desk. In a strip,
// focus moves on a click in a pane. A focus change, or a change of its place,
// brings the focused pane on screen, sideways only as far as needed. A pane
// row in the sidebar opening the strip (`openPane`) reveals its pane the same
// way, smoothly.
//
// The canvas takes drops (./drop.tsx) anywhere on a pane: its left or right
// quarter, else its top or bottom half. Onto a plane item the two become a
// strip, side by side or stacked; inside a strip a pane there; anywhere on an
// empty desk; and onto a solo plane, which
// makes a new desk of the two (`dropOnSolo`). Where it lands is drawn as the
// region the drop makes (./DropRegion.tsx).
//
// The effect here ships `planes.open` with every shown plane in order and its
// params whenever either changes, and once on load. One way: the server
// writes them, and a cell that follows its params reads them again
// (`nuspace.ui.on_params`); nothing runs again. A focus move changes neither,
// so it sends nothing.
//
// One Viewer, and it never asks what kind of thing it is drawing. Each pane
// reads its own node (`<viewer>/panes/<plane>`, ../pane/state.ts), renders
// one Plane's Cells and roots their refs, every Cell the same way. Nothing
// here reads what a pane shows: the desk only says where each pane sits.
// A pane is keyed by its plane, so one that stays in its column is never
// remounted.
//
// Column widths are ./Column.tsx's: nothing here measures the canvas.

import {
	Badge,
	EmptyState,
	type NodeProps,
	pathKey,
	ScrollArea,
	Spinner,
} from "@nustackdev/ui-kit";
import { Columns2 } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { useDesks } from "../core/desks";
import {
	currentRoutes,
	onReveal,
	paramsOf,
	type Route,
	useFocusedRoute,
	useRoute,
	useRoutes,
} from "../core/router";
import { notifyOp } from "../core/wire";
import {
	deskArea,
	deskColumns,
	deskEmpty,
	deskEmptyAim,
	deskFrame,
	deskRow,
	deskRowViewport,
	deskSolo,
	deskStripArea,
	shellMissing,
} from "../design";
import { dragging, dropDoes } from "../desk/dnd";
import type { PaneAt, Surface } from "../desk/drag";
import { locate, shown } from "../desk/model";
import { NotFound } from "../pane/NotFound";
import { Pane } from "../pane/Pane";
import type { ViewerOps } from "../plane/ops";
import { Column } from "./Column";
import { DeskHeader } from "./DeskHeader";
import { DropRegion } from "./DropRegion";
import { useCanvasDrop } from "./drop";
import { settlePanes, useCellSpecs } from "./state";

/** What an empty desk says, and the hint under it. */
export const EMPTY_DESK = "This desk is empty";
export const EMPTY_DESK_HINT = "Drag a plane here from the sidebar";

/** What the canvas shows as a drop surface, null for what takes no drop. */
export function surfaceOf(route: Route): Surface | null {
	if (route.kind === "solo") return { kind: "solo", plane: route.plane };
	if (route.kind === "desk") return { kind: "desk", desk: route.desk };
	if (route.kind !== "item") return null;
	return { kind: route.item.kind, desk: route.desk, item: route.item.id };
}

/** Where the panes the canvas shows sit. */
function paneAt(route: Route): PaneAt {
	return route.kind === "item"
		? { kind: route.item.kind, desk: route.desk, item: route.item.id }
		: { kind: "solo" };
}

export function Desk({ path }: NodeProps) {
	const cellSpecs = useCellSpecs(path);
	const route = useRoute();
	const routes = useRoutes();
	const focused = useFocusedRoute();
	const desks = useDesks();
	const key = pathKey(path);
	// What `planes.open` says, as a key: the panes in order with their params.
	const panesKey = JSON.stringify(routes.map((id) => [id, paramsOf(id)]));
	const areaRef = useRef<HTMLDivElement | null>(null);
	// What the drop region measures against: the strip's columns, or the solo pane's box.
	const dropHost = useRef<HTMLDivElement | null>(null);
	const drop = useCanvasDrop(surfaceOf(route));

	// The viewer's one op. The op name is the tail of the wire path, not a key
	// in the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const open = useCallback(
		(args: ViewerOps["planes.open"]) =>
			notifyOp<ViewerOps, "planes.open">(path, "planes.open", args),
		[key],
	);

	// The full list with its params, every time either changes and once on
	// load, an empty one included, so the server stops shipping a Plane nobody
	// has open. Panes that closed go first, node and cell ui, and a reopened
	// plane's cell ui is cleared, so nothing it draws predates the ask.
	// biome-ignore lint/correctness/useExhaustiveDependencies: the panes are compared by their key; path by value.
	useEffect(() => {
		const shown = currentRoutes();
		settlePanes(path, shown);
		const params = Object.fromEntries(shown.map((id) => [id, paramsOf(id)]));
		open({ plane_ids: shown, params });
	}, [panesKey, open]);

	// The focused pane on screen. On every focus change, when the panes change
	// under it, and when its place changes (a move, a drop).
	const strip = route.kind === "item" && route.item.kind === "strip" ? route.item : null;
	const place = strip ? JSON.stringify(locate(strip, focused)) : "";
	// biome-ignore lint/correctness/useExhaustiveDependencies: runs on focus, the pane set and the focused pane's place, nothing else.
	useEffect(() => {
		if (strip && focused) show(areaRef.current, focused, false);
	}, [focused, panesKey, place]);

	// A reveal (`openPane` from a sidebar pane row) may switch items first:
	// it scrolls once that strip is drawn, after the render it caused.
	const [reveal, setReveal] = useState<{ id: string } | null>(null);
	useEffect(() => onReveal((id) => setReveal({ id })), []);
	useEffect(() => {
		if (reveal) show(areaRef.current, reveal.id, true);
	}, [reveal]);

	const at = paneAt(route);
	const pane = (id: string): ReactNode => (
		<Pane viewerPath={path} at={at} planeId={id} cellSpecs={cellSpecs} focused={id === focused} />
	);

	if (route.kind === "pending") {
		return (
			<div className={deskArea}>
				<EmptyState className={shellMissing} icon={<Spinner size="lg" tone="neutral" />} />
			</div>
		);
	}
	if (route.kind === "missing") {
		return (
			<div className={deskArea}>
				<div className={deskSolo}>
					<NotFound what={route.what} />
				</div>
			</div>
		);
	}
	if (route.kind === "solo") {
		return (
			<div className={deskArea}>
				<div ref={dropHost} className={deskSolo} {...drop.props}>
					{pane(route.plane)}
					<DropRegion aim={drop.aim} refused={drop.refused} host={dropHost} />
				</div>
			</div>
		);
	}
	// On a desk, its header across the top, over what it shows.
	const framed = (deskId: string, body: ReactNode): ReactNode => (
		<div className={deskFrame}>
			<DeskHeader deskId={deskId} desk={desks?.[deskId] ?? null} />
			{body}
		</div>
	);
	if (route.kind === "desk") {
		return framed(
			route.desk,
			<div className={deskArea} data-desk={route.desk} {...drop.props}>
				<EmptyState className={deskEmpty} icon={<Columns2 />} description={EMPTY_DESK_HINT}>
					{EMPTY_DESK}
				</EmptyState>
				{drop.aim?.kind === "end" ? (
					<span aria-hidden data-drop-region="" className={deskEmptyAim}>
						<Badge>{dropDoes(dragging(), drop.aim).label}</Badge>
					</span>
				) : null}
			</div>,
		);
	}
	if (route.item.kind === "plane") {
		const plane = shown(route.item).plane;
		return framed(
			route.desk,
			<div className={deskArea}>
				<div
					ref={dropHost}
					className={deskSolo}
					data-desk={route.desk}
					data-item={route.item.id}
					{...drop.props}
				>
					{pane(plane)}
					<DropRegion aim={drop.aim} refused={drop.refused} host={dropHost} />
				</div>
			</div>,
		);
	}

	const { desk } = route;
	const item = route.item.id;
	const columns = route.item.columns;
	return framed(
		desk,
		<div className={deskStripArea}>
			<ScrollArea
				orientation="horizontal"
				className={deskRow}
				viewportClassName={deskRowViewport}
				viewportRef={areaRef}
				data-desk={desk}
				data-item={item}
				{...drop.props}
			>
				<div ref={dropHost} className={deskColumns}>
					{columns.map((column, i) => (
						<Column
							key={column.panes[0] ? shown(column.panes[0]).plane : i}
							desk={desk}
							item={item}
							column={column}
							only={columns.length === 1}
							last={i === columns.length - 1}
							pane={pane}
						/>
					))}
					<DropRegion aim={drop.aim} refused={drop.refused} host={dropHost} />
				</div>
			</ScrollArea>
		</div>,
	);
}

/** Scroll the pane showing `id` into view, only as far as needed. */
function show(area: HTMLElement | null, id: string, animate: boolean): void {
	const smooth = animate && !window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
	const panes = area ? [...area.querySelectorAll<HTMLElement>("[data-pane]")] : [];
	panes
		.find((el) => el.dataset.pane === id)
		?.scrollIntoView?.({
			block: "nearest",
			inline: "nearest",
			behavior: smooth ? "smooth" : "auto",
		});
}
