// The pinned row, under the rail's top bar: one icon per pinned Plane, in
// order. A pin is a shortcut: the Plane is in the tree as well. Hidden when
// nothing is pinned.
//
// An icon opens its Plane the way a tree row does, through the same handler:
// a plain click in the focused pane, cmd/ctrl-click in a browser tab. The name
// is in its tooltip. The focused pane's Plane is washed like the selected row.
//
// The strip scrolls sideways with no scrollbar. While it overflows, a
// vertical wheel scrolls it too, and an edge with more behind it fades.
//
// Drag and drop is native, like the tree's (./useRailDrag.ts):
//
//   a tree row dropped here      pinned where it lands, and left in the tree
//   a pin dropped here           moved where it lands
//   a pin dropped on the panes   opened there as a split (../main/useCanvasDrop.ts)
//   a pin dropped anywhere else  nothing: the tree only takes its own rows
//
// Where a drop lands is read off the pointer against the icon under it: its
// left half is before it, its right half after it.

import { cn, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { hrefFor, onNavClick } from "../core/router";
import { railDragging, railPin, railPinDropLine, railPins, railPinsFade } from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { type Pins, pinDropIndex } from "./pin";
import type { PlaneTree, Registered } from "./types";
import { PLANE_MIME } from "./useRailDrag";

/** What a pin's drag carries, apart from a tree row's so the tree ignores it. */
export const PIN_MIME = "application/x-nuspace-pin";

/** Where a drop would land: beside the pin at `index`. */
type PinTarget = { index: number; edge: "before" | "after" };

/** The gap a target names, 0 before the first pin. */
export function pinSlot(target: PinTarget): number {
	return target.edge === "before" ? target.index : target.index + 1;
}

export function PinnedRow(props: {
	tree: PlaneTree;
	pins: Pins;
	registered: Registered[];
	routes: string[];
	/** The focused pane's Plane. */
	selKey: string;
	reveal: (key: string) => void;
}) {
	const shown = props.pins.ids.filter((id) => props.tree[id]);
	return shown.length ? <PinStrip {...props} shown={shown} /> : null;
}

function PinStrip({
	tree,
	pins,
	registered,
	routes,
	selKey,
	reveal,
	shown,
}: {
	tree: PlaneTree;
	pins: Pins;
	registered: Registered[];
	routes: string[];
	selKey: string;
	reveal: (key: string) => void;
	/** The pins the tree holds, in order. */
	shown: string[];
}) {
	const ref = useRef<HTMLElement | null>(null);
	const [fade, setFade] = useState({ start: false, end: false });
	const [dragId, setDragId] = useState<string | null>(null);
	const [target, setTarget] = useState<PinTarget | null>(null);

	const measure = useCallback(() => {
		const el = ref.current;
		if (!el) return;
		const start = el.scrollLeft > 0;
		const end = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
		setFade((f) => (f.start === start && f.end === end ? f : { start, end }));
	}, []);

	// A vertical wheel scrolls the strip sideways, only while it overflows.
	// Native, since React's wheel listener is passive and cannot take the event.
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		const onWheel = (e: WheelEvent) => {
			if (el.scrollWidth <= el.clientWidth || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
			e.preventDefault();
			el.scrollLeft += e.deltaY;
		};
		el.addEventListener("wheel", onWheel, { passive: false });
		const resized = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
		resized?.observe(el);
		return () => {
			el.removeEventListener("wheel", onWheel);
			resized?.disconnect();
		};
	}, [measure]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: a pin in or out changes the width.
	useEffect(measure, [shown.length, measure]);

	const end = useCallback(() => {
		setDragId(null);
		setTarget(null);
	}, []);

	/** Whether this drag is one the strip takes: a pin, or a tree row. */
	const takes = (e: React.DragEvent) =>
		dragId !== null || Array.from(e.dataTransfer.types).includes(PLANE_MIME);

	const drop = (e: React.DragEvent, to: PinTarget) => {
		e.preventDefault();
		e.stopPropagation();
		const moving = dragId;
		const id = moving ?? e.dataTransfer.getData(PLANE_MIME);
		end();
		if (!id || !tree[id]) return;
		const index = pinDropIndex(shown, id, pinSlot(to));
		if (index === null) return;
		if (moving) pins.move(id, index);
		else pins.pin(id, index);
	};

	const aim = (e: React.DragEvent, index: number): PinTarget => {
		const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
		return { index, edge: e.clientX < r.left + r.width / 2 ? "before" : "after" };
	};

	const last: PinTarget = { index: shown.length - 1, edge: "after" };

	return (
		<nav
			ref={ref}
			aria-label="Pinned"
			className={railPins}
			style={railPinsFade(fade.start, fade.end)}
			onScroll={measure}
			// The strip's own pad and gaps: a drop there goes last.
			onDragOver={(e) => {
				if (!takes(e)) return;
				e.preventDefault();
				e.dataTransfer.dropEffect = "move";
				if (!target) setTarget(last);
			}}
			onDragLeave={(e) => {
				if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setTarget(null);
			}}
			onDrop={(e) => {
				if (takes(e)) drop(e, last);
			}}
		>
			{shown.map((id, index) => {
				const row = tree[id];
				const title = row.title || "Untitled";
				const selected = id === selKey;
				const aimed = target?.index === index ? target.edge : null;
				const navClick = onNavClick(id);
				return (
					<Tooltip key={id}>
						<TooltipTrigger asChild>
							<a
								href={hrefFor(id)}
								aria-label={title}
								aria-current={selected ? "page" : undefined}
								data-pin={id}
								draggable
								className={cn(
									railPin(selected, !selected && routes.includes(id)),
									dragId === id && railDragging,
								)}
								onClick={(e) => {
									// The tree row's click: open it and reveal what is inside it.
									if (row.children.length) reveal(id);
									navClick(e);
								}}
								onDragStart={(e) => {
									e.dataTransfer.effectAllowed = "move";
									e.dataTransfer.setData(PIN_MIME, id);
									setDragId(id);
								}}
								onDragEnd={end}
								onDragOver={(e) => {
									if (!takes(e)) return;
									e.preventDefault();
									e.stopPropagation();
									e.dataTransfer.dropEffect = "move";
									const next = aim(e, index);
									if (target?.index !== next.index || target.edge !== next.edge) setTarget(next);
								}}
								onDrop={(e) => {
									if (takes(e)) drop(e, aim(e, index));
								}}
							>
								<PlaneIcon
									icon={planeIcon(row.icon, registered.find((r) => r.name === row.made_by)?.icon)}
								/>
								{aimed ? <span className={railPinDropLine(aimed)} aria-hidden="true" /> : null}
							</a>
						</TooltipTrigger>
						<TooltipContent side="bottom">{title}</TooltipContent>
					</Tooltip>
				);
			})}
		</nav>
	);
}
