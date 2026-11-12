// The drop target on the canvas, drawn as the region the drop makes
// (../design `deskDropRegion`), labeled with what it does:
//
//   a pane's left / right edge, in a strip    "New column": the half of its
//                                             column, the column's full height
//   a pane's top / bottom half, in a strip    "Stack above" / "Stack below":
//                                             the half of the pane
//   a plane item's or solo plane's edge       "Side by side": the half of it
//   a plane item's or solo plane's half       "Stack above" / "Stack below"
//
// One region per host, measured against it: the strip's columns (so it
// scrolls with them) or the solo pane's box. It glides from one target to
// the next and is placed, not flown in, when it appears. An empty desk's
// region is the whole desk (`deskEmptyAim`), drawn by the desk itself.

import { Badge, cn } from "@nustackdev/ui-kit";
import { type RefObject, useLayoutEffect, useRef, useState } from "react";
import { deskDropGlide, deskDropRegion } from "../design";
import type { Target } from "../desk/dnd";

type Box = { left: number; top: number; width: number; height: number };

/** How far inside its region the drawn region sits, px. */
const INSET = 2;

/** What a drop on `aim` does, as its label. */
export function dropLabel(aim: Target): string | null {
	const edge =
		aim.kind === "onto"
			? aim.edge
			: aim.kind === "strip" && "plane" in aim.drop
				? aim.drop.edge
				: null;
	if (edge === "top") return "Stack above";
	if (edge === "bottom") return "Stack below";
	if (edge === null) return null;
	return aim.kind === "onto" ? "Side by side" : "New column";
}

/** The region a drop on `aim` makes, in `host`'s box, or null when it draws none. */
function regionOf(host: HTMLElement, aim: Target): Box | null {
	let el: Element | null = null;
	let edge: "left" | "right" | "top" | "bottom";
	if (aim.kind === "onto") {
		el = host.querySelector("[data-pane]");
		edge = aim.edge;
	} else if (aim.kind === "strip" && "plane" in aim.drop) {
		const plane = aim.drop.plane;
		const pane = [...host.querySelectorAll<HTMLElement>("[data-pane]")].find(
			(p) => p.dataset.pane === plane,
		);
		edge = aim.drop.edge;
		el =
			edge === "left" || edge === "right"
				? (pane?.closest("[data-column]") ?? null)
				: (pane ?? null);
	} else return null;
	if (!el) return null;
	const h = host.getBoundingClientRect();
	const r = el.getBoundingClientRect();
	let { left, top, width, height } = {
		left: r.left - h.left,
		top: r.top - h.top,
		width: r.width,
		height: r.height,
	};
	if (edge === "left" || edge === "right") {
		width /= 2;
		if (edge === "right") left += width;
	} else {
		height /= 2;
		if (edge === "bottom") top += height;
	}
	return {
		left: left + INSET,
		top: top + INSET,
		width: Math.max(0, width - 2 * INSET),
		height: Math.max(0, height - 2 * INSET),
	};
}

/** The region of the drop `aim` points at inside `host`, null at rest. */
export function DropRegion({
	aim,
	host,
}: {
	aim: Target | null;
	host: RefObject<HTMLElement | null>;
}) {
	const [box, setBox] = useState<Box | null>(null);
	useLayoutEffect(() => {
		setBox(aim && host.current ? regionOf(host.current, aim) : null);
	}, [aim, host]);
	// Shown on the last paint: only then does it glide to the next target.
	const shown = useRef(false);
	const glide = shown.current;
	useLayoutEffect(() => {
		shown.current = box !== null;
	}, [box]);
	if (!aim || !box) return null;
	const label = dropLabel(aim);
	return (
		<div
			aria-hidden
			data-drop-region=""
			className={cn(deskDropRegion, glide && deskDropGlide)}
			style={box}
		>
			{label ? <Badge>{label}</Badge> : null}
		</div>
	);
}
