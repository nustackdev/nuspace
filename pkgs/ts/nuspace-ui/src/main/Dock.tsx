// The dock: the bar under the desk, a scaled map of its panes.
//
// The desk is a strip of panes side by side that scrolls sideways, every pane
// open at once, so it is a scrolling desk and not a set of tabs. The dock is
// its scrollbar, with labels: one chip per pane, in desk order, each as wide as
// its pane's share of the desk, and a window over them marking what is on
// screen. It never claims to sit above its pane, so nothing drifts as the desk
// scrolls; each pane carries its own title in its own bar (../pane/PaneBar.tsx).
//
// Only drawn while some scroll can leave a pane fully out of view: the last
// pane starts past the window with the desk at its start, or the first one
// ends before the window with the desk at its end. Short of that, a piece of
// every pane is always on screen, so there is nothing to map. Decided off the
// layout alone, never the scroll, so the dock does not come and go as you
// scroll.
//
// A chip carries no buttons, so it works the same at any width:
//   click                 focus its pane and scroll it into view
//   drag along the dock   move the pane; drop on a pane's bar works too
//   right-click           the pane's menu at the pointer, the same items as
//                         the `...` on its bar (../pane/PaneMenu.tsx)
//
// The window's bottom third is the thumb, an 8px fill along its edge: it drags the desk, the way a
// scrollbar's thumb does, and a wheel or a trackpad swipe anywhere over the
// dock scrolls the desk as if it were over the panes.
//
// Geometry is measured off the strip itself (scroll, its size and every
// pane's), so the dock follows a resize, a divider drag or a pane opening
// without being told.

import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuTrigger,
	OverflowTooltip,
} from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect, useRef, useState } from "react";
import { focusPane, movePane } from "../core/router";
import {
	DOCK_WINDOW_GAP,
	dock,
	dockChip,
	dockChipIcon,
	dockChipTitle,
	dockChipTrigger,
	dockDropLine,
	dockTrack,
	dockWindow,
	paneMenu,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { parseIcon } from "../icon/parse";
import { paneTitle } from "../pane/Pane";
import { PaneMenuItems } from "../pane/PaneMenu";
import type { AbsentReason, ActivePlane } from "../plane/types";
import { contextParts } from "../shell/menu";
import { pinDropIndex } from "../sidebar/pin";
import { edgeAt, PANE_MIME, type PaneEdge } from "./useCanvasDrop";

/** Where the desk is: its scroll, its visible width, its full width, its panes. */
export type DeskGeometry = {
	left: number;
	view: number;
	total: number;
	panes: { id: string; x: number; w: number }[];
};

/** A chip or the window, as percentages of the track. */
type Span = { left: number; width: number };

export type DockLayout = {
	chips: (Span & { id: string; onScreen: boolean })[];
	window: Span;
};

/** How far a pane has to be on screen, px, before its chip counts as on screen. */
const ON_SCREEN = 48;

/**
 * The dock's layout off the desk's geometry. Null while no scroll can leave a
 * pane fully out of view.
 */
export function dockLayout(g: DeskGeometry): DockLayout | null {
	const first = g.panes[0];
	const last = g.panes[g.panes.length - 1];
	if (!first || !last || g.total <= 0) return null;
	const lastHides = last.x >= g.view;
	const firstHides = first.x + first.w <= g.total - g.view;
	if (!lastHides && !firstHides) return null;
	const pct = (px: number) => (px / g.total) * 100;
	return {
		chips: g.panes.map((p) => ({
			id: p.id,
			left: pct(p.x),
			width: pct(p.w),
			onScreen: p.x + p.w > g.left + ON_SCREEN && p.x < g.left + g.view - ON_SCREEN,
		})),
		window: { left: pct(g.left), width: pct(g.view) },
	};
}

function measure(strip: HTMLElement): DeskGeometry {
	const base = strip.getBoundingClientRect().left - strip.scrollLeft;
	const panes = Array.from(strip.querySelectorAll<HTMLElement>(":scope > [data-pane]"), (el) => {
		const r = el.getBoundingClientRect();
		return { id: el.dataset.pane ?? "", x: r.left - base, w: r.width };
	});
	return { left: strip.scrollLeft, view: strip.clientWidth, total: strip.scrollWidth, panes };
}

function sameGeometry(a: DeskGeometry | null, b: DeskGeometry): boolean {
	if (!a || a.left !== b.left || a.view !== b.view || a.total !== b.total) return false;
	if (a.panes.length !== b.panes.length) return false;
	return a.panes.every(
		(p, i) => p.id === b.panes[i].id && p.x === b.panes[i].x && p.w === b.panes[i].w,
	);
}

/** The desk's geometry, kept current off its scroll and every size change. */
function useDeskGeometry(
	stripRef: React.RefObject<HTMLDivElement | null>,
	routesKey: string,
): DeskGeometry | null {
	const [geometry, setGeometry] = useState<DeskGeometry | null>(null);
	// biome-ignore lint/correctness/useExhaustiveDependencies: re-observes when the pane set changes.
	useEffect(() => {
		const strip = stripRef.current;
		if (!strip) return;
		let frame = 0;
		const update = () => {
			cancelAnimationFrame(frame);
			frame = requestAnimationFrame(() => {
				const next = measure(strip);
				setGeometry((prev) => (sameGeometry(prev, next) ? prev : next));
			});
		};
		const sizes = new ResizeObserver(update);
		sizes.observe(strip);
		for (const pane of strip.querySelectorAll(":scope > [data-pane]")) sizes.observe(pane);
		strip.addEventListener("scroll", update, { passive: true });
		update();
		return () => {
			cancelAnimationFrame(frame);
			sizes.disconnect();
			strip.removeEventListener("scroll", update);
		};
	}, [stripRef, routesKey]);
	return geometry;
}

/** Smooth, unless the user asked for less motion (motion.md). */
function scrollBehavior(): ScrollBehavior {
	return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

/** A press that travels less than this, px, is a click. */
const CLICK_SLOP = 3;

/** The chip under a point, looking through the window over it. */
function chipAt(x: number, y: number): HTMLElement | undefined {
	return document
		.elementsFromPoint(x, y)
		.find((el): el is HTMLElement => el instanceof HTMLElement && el.dataset.chip !== undefined);
}

/** Whether a drag is a pane: off a chip or off a pane's bar. */
function isPaneDrag(e: React.DragEvent): boolean {
	return Array.from(e.dataTransfer.types).includes(PANE_MIME);
}

export function Dock({
	routes,
	planes,
	absent,
	stripRef,
	onMeta,
	deleteOf,
}: {
	routes: string[];
	planes: Record<string, ActivePlane>;
	/** Panes with no Plane to draw: titled by id. */
	absent: Record<string, AbsentReason>;
	/** The desk, to measure and to scroll. */
	stripRef: React.RefObject<HTMLDivElement | null>;
	onMeta: (planeId: string, patch: Record<string, unknown>) => void;
	/** A plane's delete, undefined for one that cannot be deleted. */
	deleteOf: (planeId: string) => (() => void) | undefined;
}) {
	const geometry = useDeskGeometry(stripRef, routes.join("+"));
	const [dragId, setDragId] = useState<string | null>(null);
	const [target, setTarget] = useState<{ id: string; edge: PaneEdge } | null>(null);

	const navRef = useRef<HTMLElement | null>(null);

	const layout = geometry ? dockLayout(geometry) : null;
	const shown = layout !== null;

	// A wheel over the dock scrolls the desk, either axis. Not passive, so a
	// sideways swipe is not also the browser's back gesture.
	useEffect(() => {
		const nav = navRef.current;
		if (!shown || !nav) return;
		const onWheel = (e: WheelEvent) => {
			const strip = stripRef.current;
			if (!strip) return;
			const dx = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
			if (!dx) return;
			e.preventDefault();
			strip.scrollLeft += dx;
		};
		nav.addEventListener("wheel", onWheel, { passive: false });
		return () => nav.removeEventListener("wheel", onWheel);
	}, [shown, stripRef]);

	if (!layout || !geometry) return null;

	const endDrag = () => {
		setDragId(null);
		setTarget(null);
	};

	/** Focus a pane and bring it on screen, only as far as needed. */
	const show = (id: string) => {
		focusPane(id);
		stripRef.current
			?.querySelector<HTMLElement>(`:scope > [data-pane="${CSS.escape(id)}"]`)
			?.scrollIntoView({ inline: "nearest", block: "nearest", behavior: scrollBehavior() });
	};

	// Dragging the window moves the desk by the same share of its width. A
	// press that never travels is a click on the chip under the window.
	const onWindowDown = (e: React.PointerEvent<HTMLDivElement>) => {
		const strip = stripRef.current;
		const track = e.currentTarget.parentElement;
		if (e.button !== 0 || !strip || !track) return;
		e.preventDefault();
		const x0 = e.clientX;
		const left0 = strip.scrollLeft;
		const scale = strip.scrollWidth / track.getBoundingClientRect().width;
		let moved = false;
		const move = (m: PointerEvent) => {
			if (!moved && Math.abs(m.clientX - x0) < CLICK_SLOP) return;
			moved = true;
			strip.scrollLeft = left0 + (m.clientX - x0) * scale;
		};
		const up = (u: PointerEvent) => {
			window.removeEventListener("pointermove", move);
			window.removeEventListener("pointerup", up);
			window.removeEventListener("pointercancel", up);
			if (!moved && u.type === "pointerup") {
				const id = chipAt(u.clientX, u.clientY)?.dataset.chip;
				if (id) show(id);
			}
		};
		window.addEventListener("pointermove", move);
		window.addEventListener("pointerup", up);
		window.addEventListener("pointercancel", up);
	};

	// A right-click on the window opens the menu of the chip under it.
	const onWindowMenu = (e: React.MouseEvent<HTMLDivElement>) => {
		const chip = chipAt(e.clientX, e.clientY);
		if (!chip) return;
		e.preventDefault();
		chip.dispatchEvent(
			new MouseEvent("contextmenu", {
				bubbles: true,
				cancelable: true,
				clientX: e.clientX,
				clientY: e.clientY,
				button: 2,
			}),
		);
	};

	return (
		<nav ref={navRef} className={dock} aria-label="Desk">
			{/* biome-ignore lint/a11y/noStaticElementInteractions: only clears a drag's drop mark */}
			<div
				className={dockTrack}
				onDragLeave={(e) => {
					if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setTarget(null);
				}}
			>
				{layout.chips.map((chip) => {
					const id = chip.id;
					const plane = planes[id] ?? null;
					const title = paneTitle(id, plane, absent[id] ?? null);
					const icon = parseIcon(plane?.meta.icon);
					const aimed = target?.id === id ? target.edge : null;
					return (
						<ContextMenu key={id}>
							<ContextMenuTrigger asChild>
								{/* biome-ignore lint/a11y/noStaticElementInteractions: dragging is a mouse shortcut; the chip's button carries the keyboard */}
								<div
									data-chip={id}
									className={dockChip(chip.onScreen, dragId === id)}
									style={{ left: `${chip.left}%`, width: `${chip.width}%` }}
									draggable
									onDragStart={(e) => {
										e.dataTransfer.effectAllowed = "move";
										e.dataTransfer.setData(PANE_MIME, id);
										setDragId(id);
									}}
									onDragEnd={endDrag}
									onDragOver={(e) => {
										if (!isPaneDrag(e)) return;
										e.preventDefault();
										e.dataTransfer.dropEffect = "move";
										const edge = edgeAt(e.currentTarget, e.clientX);
										if (target?.id !== id || target.edge !== edge) setTarget({ id, edge });
									}}
									onDrop={(e) => {
										if (!isPaneDrag(e)) return;
										e.preventDefault();
										const moving = e.dataTransfer.getData(PANE_MIME);
										const at = routes.indexOf(id);
										const slot = edgeAt(e.currentTarget, e.clientX) === "before" ? at : at + 1;
										endDrag();
										const index = moving ? pinDropIndex(routes, moving, slot) : null;
										if (moving && index !== null) movePane(moving, index);
									}}
								>
									<OverflowTooltip label={title} side="top">
										<button
											type="button"
											aria-label={title}
											aria-current={chip.onScreen ? "true" : undefined}
											className={dockChipTrigger}
											onClick={() => show(id)}
										>
											{icon ? <PlaneIcon icon={icon} className={dockChipIcon} /> : null}
											<span className={dockChipTitle}>{title}</span>
										</button>
									</OverflowTooltip>
									{aimed ? <span className={dockDropLine(aimed)} aria-hidden="true" /> : null}
								</div>
							</ContextMenuTrigger>
							<ContextMenuContent className={paneMenu}>
								<PaneMenuItems
									parts={contextParts}
									planeId={id}
									meta={plane?.meta ?? null}
									onChange={(patch) => onMeta(id, patch)}
									onDelete={deleteOf(id)}
								/>
							</ContextMenuContent>
						</ContextMenu>
					);
				})}
				<div
					aria-hidden="true"
					className={dockWindow}
					onPointerDown={onWindowDown}
					onContextMenu={onWindowMenu}
					style={{
						left: `calc(${layout.window.left}% + ${DOCK_WINDOW_GAP}px)`,
						width: `calc(${layout.window.width}% - ${2 * DOCK_WINDOW_GAP}px)`,
					}}
				/>
			</div>
		</nav>
	);
}
