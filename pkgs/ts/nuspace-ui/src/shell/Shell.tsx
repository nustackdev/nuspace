// The shell: the sidebar and the desk area, side by side on one canvas
// (`ground-deep` behind both, 6px between them), and the toaster a failed
// interaction shows in (../refs/toast.ts).
//
// There is no top bar, because there is no third region, and the two controls the window still has (the
// connection dot and the theme flip) sit in the sidebar's bottom bar. Folded,
// the sidebar does not vanish, it gets thin: its panel folds to the rail's
// width (../sidebar/SidebarRail.tsx), the toggle that brings it back on top
// and the sidebar's first level as icons under it. The panel holds both the
// sidebar and the rail and shows one by its own fold state, which the kit
// updates on every frame of a drag, so dragging past the minimum lands on
// the rail and dragging out of the rail lands on the sidebar, never both and
// never neither. The sidebar lists every Plane that draws, and the desk
// area draws whatever the router shows (a solo plane or a desk), so navigation
// is the sidebar's and the links', and the shell only places the two.
//
// Both are found BY TYPE (see core/surfaces.ts), not by a slot name. Where
// python hangs them is python's call, and the wire type is the one thing about
// a region both sides already agree on.
//
// Every link is a plain anchor whose href is where it goes: a cell's (the
// kit's LinkRef, PageLinkRef, a markdown link) and the sidebar's rows
// alike. The kit's AnchorCatcher on the shell's root hands an in-app click or
// Enter to the shell's rule (../desk/open.ts `linkRule`): a plain click on a
// plane url navigates the pane it sits in, in place, and opens solo from
// anywhere else, Option Cmd opens it to the side,
// and anything that is not the app's url is left to the browser, as are Cmd,
// Shift and middle clicks. The sidebar routes its pane
// rows first (../sidebar/links.ts): the strip opens with that pane focused.
//
// The two sit in the kit's split (`ResizablePanelGroup`): the sidebar is a
// collapsible panel with the kit's sidebar bounds and a px default, so it
// holds its width while the window resizes and the desk area takes the
// change. The split's handle is the 6px gap, no fill.
// Drag its border to resize it, past its minimum to fold it; Enter on the
// border, the sidebar header's button, the reopen button and cmd/ctrl+\ fold
// and unfold it too, all through the one split (../sidebar/collapse.ts),
// which keeps the layout across reloads. Home, search and settings have keys
// from anywhere, mounted here so they work before the sidebar lands.
//
// A narrow window (../sidebar/collapse.ts `SIDEBAR_NARROW_PX`) keeps the
// same split, mounted and untouched, and only draws it differently: the
// sidebar's panel held at the rail's width whatever the split's share, the
// border gone, and the sidebar, when opened, over the desk with the scrim
// behind it and the desk inert. Escape, a click on the scrim or a navigation
// closes it. Nothing is remounted either way across the line, and nothing
// narrow lands on the split, so a wide window gets back the width and the
// fold it had.
//
// Before the tree lands neither region is on it. The shell still draws: the
// sidebar as its chrome with skeleton rows, the desk as the viewer skeleton, so
// the boot and a plane switch look alike. Once anything has landed, a region
// still missing is a real absence and says so. A boot that runs past
// `BOOTING_DELAY_MS` (a first start compiling python) swaps the desk's
// skeleton for a note, so a long wait reads as booting and not as stuck.

import {
	EmptyState,
	NodeView,
	ResizableHandle,
	ResizablePanel,
	ResizablePanelGroup,
	type ResizablePanelGroupHandle,
	SIDEBAR_WIDTH,
	Spinner,
	Toaster,
	useAnchorCatcher,
} from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect, useLayoutEffect, useRef } from "react";
import { BOOTING_DELAY_MS, useAfter } from "../core/delay";
import { useRoute } from "../core/router";
import { useBooted, useTypePath } from "../core/surfaces";
import {
	SIDEBAR_RAIL_PX,
	shellMain,
	shellMissing,
	shellPanePlane,
	shellRoot,
	shellScrim,
	shellSideNarrowRail,
	shellSideNarrowStyle,
	shellSideOpen,
	shellSideOverlay,
	shellSideRail,
	shellSideSlot,
	shellSlot,
	shellSplitHandle,
	shellSplitHandleNarrow,
} from "../design";
import { useDragScroll } from "../desk/autoscroll";
import { linkRule } from "../desk/open";
import { ViewerSkeleton } from "../pane/ViewerSkeleton";
import {
	bindSidebar,
	focusSidebarToggle,
	publishSidebar,
	SIDEBAR_LAYOUT_KEY,
	SidebarPlaceholder,
	SidebarRail,
	setSidebarOverlay,
	useNavShortcuts,
	useNewPlaneShortcut,
	useSidebarNarrow,
	useSidebarOverlay,
	useSidebarShortcut,
} from "../sidebar/api";
import { useTab } from "./tab";

export function Shell() {
	const sidebar = useTypePath("SidebarRef");
	const viewer = useTypePath("ViewerRef");
	const rootRef = useRef<HTMLDivElement | null>(null);
	const booted = useBooted();
	const slow = useAfter(!booted, BOOTING_DELAY_MS);
	const split = useRef<ResizablePanelGroupHandle | null>(null);
	// The sidebar's panel: the real sidebar, or its placeholder until the tree lands.
	const side = sidebar !== null || !booted;
	const narrow = useSidebarNarrow();
	const overlay = useSidebarOverlay() && narrow;
	// A navigation closes the overlay: a row followed, a link, back.
	const route = useRoute();
	// biome-ignore lint/correctness/useExhaustiveDependencies: the route is the trigger, not an input.
	useEffect(() => setSidebarOverlay(false), [route]);
	const closeOverlay = () => {
		setSidebarOverlay(false);
		focusSidebarToggle();
	};
	const onOverlayKey = (e: React.KeyboardEvent) => {
		if (e.key !== "Escape" || !overlay) return;
		// A menu, popover or field inside takes its Escape first; a tooltip
		// (the toggle's, shown as focus lands on it) is no reason to stay.
		if (e.defaultPrevented && !onlyTooltip(e.target)) return;
		e.preventDefault();
		closeOverlay();
	};
	useSidebarShortcut();
	useNewPlaneShortcut();
	useNavShortcuts();
	useTab(viewer);
	useDragScroll();

	// Before the first paint, so the reopen button is right from the start.
	useLayoutEffect(() => {
		bindSidebar(split);
		return () => bindSidebar(null);
	}, []);

	useAnchorCatcher(rootRef, linkRule);

	return (
		<div ref={rootRef} className={shellRoot}>
			<ResizablePanelGroup
				ref={split}
				storageKey={SIDEBAR_LAYOUT_KEY}
				onLayout={(sizes) => {
					if (sizes.length > 1) publishSidebar(split.current?.isCollapsed(0) ?? false);
				}}
			>
				{side
					? [
							<ResizablePanel
								key="sidebar"
								id="shell-sidebar"
								defaultSize={`${SIDEBAR_WIDTH.DEFAULT}px`}
								minSize={`${SIDEBAR_WIDTH.MIN}px`}
								maxSize={`${SIDEBAR_WIDTH.MAX}px`}
								collapsible
								collapsedSize={`${SIDEBAR_RAIL_PX}px`}
								className={shellSideSlot}
								style={narrow ? shellSideNarrowStyle(SIDEBAR_RAIL_PX) : undefined}
								data-narrow={narrow ? "" : undefined}
							>
								{/* biome-ignore lint/a11y/noStaticElementInteractions: Escape for what is inside, not a control of its own. */}
								<div
									className={narrow ? shellSideOverlay(overlay) : shellSideOpen}
									style={narrow ? { width: SIDEBAR_WIDTH.DEFAULT } : undefined}
									data-sidebar-overlay={narrow ? (overlay ? "open" : "closed") : undefined}
									onKeyDown={onOverlayKey}
								>
									{sidebar ? <NodeView path={sidebar} /> : <SidebarPlaceholder />}
								</div>
								<div className={narrow ? shellSideNarrowRail : shellSideRail}>
									<SidebarRail sidebar={sidebar} />
								</div>
							</ResizablePanel>,
							<ResizableHandle
								key="sidebar-edge"
								aria-label="Resize sidebar"
								className={narrow ? shellSplitHandleNarrow : shellSplitHandle}
							/>,
						]
					: null}
				<ResizablePanel key="main" id="shell-main" className={shellSlot}>
					<main className={shellMain} inert={overlay}>
						{viewer ? (
							<NodeView path={viewer} />
						) : booted ? (
							<EmptyState className={shellMissing}>no Viewer on the tree</EmptyState>
						) : slow ? (
							<EmptyState
								className={shellMissing}
								icon={<Spinner size="lg" tone="neutral" label="Booting" />}
								description="First boot takes a little longer while everything gets ready. Almost there!"
							>
								Booting your space
							</EmptyState>
						) : (
							<div className={shellPanePlane}>
								<ViewerSkeleton />
							</div>
						)}
					</main>
				</ResizablePanel>
			</ResizablePanelGroup>
			{overlay ? (
				<div
					aria-hidden="true"
					className={shellScrim}
					data-sidebar-scrim=""
					onClick={closeOverlay}
				/>
			) : null}
			<Toaster />
		</div>
	);
}

/**
 * Whether an Escape already taken was only a tooltip's: one is showing, no
 * menu, popover or dialog is open, and the key did not come from a field.
 */
function onlyTooltip(target: EventTarget | null): boolean {
	if (target instanceof HTMLElement && target.closest("input, textarea, [contenteditable=true]"))
		return false;
	if (!document.querySelector("[role=tooltip]")) return false;
	return !document.querySelector(
		"[role=menu], [role=dialog], [role=listbox], [data-slot=popover-content]",
	);
}
