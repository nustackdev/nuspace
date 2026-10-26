// The shell: the sidebar and the main strip, side by side, and nothing else.
//
// There is no top strip and no surface switcher, because there is no third
// region to switch to, and the two controls the window still has (the
// connection dot and the theme flip) sit in the sidebar's bottom bar. The one
// piece of chrome the shell draws itself is the button that brings a collapsed
// sidebar back, over the main strip's top left corner, since the sidebar's own
// is hidden with it. The sidebar lists every Plane that draws, under a cell per group,
// and the main strip draws whichever ones the router has open, so navigation is
// the sidebar's and the links', and the shell only places the two.
//
// Both are found BY TYPE (see core/surfaces.ts), not by a slot name. Where
// python hangs them is python's call, and the wire type is the one thing about
// a region both sides already agree on.
//
// Every link is a plain anchor whose href is where it goes: a cell's (the
// kit's LinkRef, PageLinkRef, a markdown link) and the sidebar's rows and pins
// alike. The kit's AnchorCatcher on the shell's root hands an in-app click or
// Enter to the pane router's rule (core/router.ts `paneRule`): plain opens in
// the focused pane, Option beside it, and anything that is not a pane URL is
// left to the browser, as are Cmd, Shift and middle clicks. On the root, not
// the strip, so a sidebar row and a link in a cell are one gesture.
//
// The two sit in the kit's split (`ResizablePanelGroup`): the rail is a
// collapsible panel with the kit's sidebar bounds and a px default, so it
// holds its width while the window resizes and the strip takes the change.
// Drag its border to resize it, past its minimum to fold it; Enter on the
// border, the rail's button, the reopen button and cmd/ctrl+\ fold and
// unfold it too, all through the one split (../sidebar/collapse.ts), which
// keeps the layout across reloads.
//
// Before the tree lands neither region is on it. The shell still draws: the
// rail as its chrome with skeleton rows, the strip as the viewer skeleton, so
// the boot and a plane switch look alike. Once anything has landed, a region
// still missing is a real absence and says so. A boot that runs past
// `BOOTING_DELAY_MS` (a first start compiling python) swaps the strip's
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
	useAnchorCatcher,
} from "@nustackdev/ui-kit";
import { useLayoutEffect, useRef } from "react";
import { BOOTING_DELAY_MS, useAfter } from "../core/delay";
import { paneRule } from "../core/router";
import { useBooted, useTypePath } from "../core/surfaces";
import { useTab } from "../core/tab";
import {
	shellMain,
	shellMissing,
	shellPanePlane,
	shellRailOpen,
	shellRoot,
	shellSlot,
	shellSplitHandle,
} from "../design";
import { ViewerSkeleton } from "../pane/ViewerSkeleton";
import { useNewPlaneShortcut } from "../sidebar/add";
import {
	bindRail,
	focusRailToggle,
	migrateRail,
	publishRail,
	RAIL_LAYOUT_KEY,
	setRailCollapsed,
	useRailCollapsed,
	useRailShortcut,
} from "../sidebar/collapse";
import { RailPlaceholder } from "../sidebar/Rail";
import { RailToggle } from "../sidebar/RailHeader";

export function Shell() {
	const sidebar = useTypePath("SidebarRef");
	const viewer = useTypePath("ViewerRef");
	const rootRef = useRef<HTMLDivElement | null>(null);
	const booted = useBooted();
	const slow = useAfter(!booted, BOOTING_DELAY_MS);
	const split = useRef<ResizablePanelGroupHandle | null>(null);
	const splitEl = useRef<HTMLDivElement | null>(null);
	// The rail's panel: the real rail, or its placeholder until the tree lands.
	const rail = sidebar !== null || !booted;
	const collapsed = useRailCollapsed() && rail;
	useRailShortcut();
	useNewPlaneShortcut();
	useTab(viewer);

	// Before the first paint, so the reopen button is right from the start.
	useLayoutEffect(() => {
		if (split.current) migrateRail(split.current, splitEl.current);
		bindRail(split);
		return () => bindRail(null);
	}, []);

	useAnchorCatcher(rootRef, paneRule);

	return (
		<div ref={rootRef} className={shellRoot}>
			<ResizablePanelGroup
				ref={split}
				elementRef={splitEl}
				storageKey={RAIL_LAYOUT_KEY}
				onLayout={(sizes) => {
					if (sizes.length > 1) publishRail(sizes[0] <= 0);
				}}
			>
				{rail
					? [
							<ResizablePanel
								key="rail"
								id="shell-rail"
								defaultSize={`${SIDEBAR_WIDTH.DEFAULT}px`}
								minSize={`${SIDEBAR_WIDTH.MIN}px`}
								maxSize={`${SIDEBAR_WIDTH.MAX}px`}
								collapsible
								className={shellSlot}
							>
								{sidebar ? <NodeView path={sidebar} /> : <RailPlaceholder />}
							</ResizablePanel>,
							<ResizableHandle
								key="rail-edge"
								aria-label="Resize sidebar"
								className={shellSplitHandle}
							/>,
						]
					: null}
				<ResizablePanel key="main" id="shell-main" className={shellSlot}>
					<main className={shellMain} data-rail={collapsed ? "collapsed" : undefined}>
						{collapsed ? (
							<div className={shellRailOpen}>
								<RailToggle
									label="Show sidebar"
									onClick={() => {
										setRailCollapsed(false);
										focusRailToggle();
									}}
								/>
							</div>
						) : null}
						{viewer ? (
							<NodeView path={viewer} />
						) : booted ? (
							<EmptyState className={shellMissing}>no Viewer on the tree</EmptyState>
						) : slow ? (
							<EmptyState
								className={shellMissing}
								icon={<Spinner size="lg" tone="neutral" label="Waking up" />}
								description="First boot takes a little longer while everything gets ready. Almost there!"
							>
								Waking up your space
							</EmptyState>
						) : (
							<div className={shellPanePlane}>
								<ViewerSkeleton />
							</div>
						)}
					</main>
				</ResizablePanel>
			</ResizablePanelGroup>
		</div>
	);
}
