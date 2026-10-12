// The shell: the sidebar and the main strip, side by side, and nothing else.
//
// There is no top strip and no surface switcher, because there is no third
// region to switch to, and the two controls the window still has (the
// connection dot and the theme flip) sit in the sidebar's bottom bar. The one
// piece of chrome the shell draws itself is the button that brings a collapsed
// sidebar back, over the main strip's top left corner, since the sidebar's own
// is hidden with it. The sidebar lists every Plane that draws, under a cell per group,
// and the main strip draws whichever ones the URL names, so navigation is
// entirely the sidebar's and the shell only places the two.
//
// Both are found BY TYPE (see core/surfaces.ts), not by a slot name. Where
// python hangs them is python's call, and the wire type is the one thing about
// a region both sides already agree on.
//
// Links a cell draws (the kit's LinkRef, a markdown link) are plain anchors.
// One listener on the main strip routes a click on a same-origin one to /<id>
// or /<a>+<b> through the router (core/router.ts `routeAnchorClick`), so it
// switches panes instead of reloading the tab. A modified click is the
// browser's, as in the sidebar. Native, not React: it has to see anchors the kit
// renders without handlers of ours, and it runs before the browser follows
// them.
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
// still missing is a real absence and says so.

import {
	EmptyState,
	NodeView,
	ResizableHandle,
	ResizablePanel,
	ResizablePanelGroup,
	type ResizablePanelGroupHandle,
	SIDEBAR_WIDTH,
} from "@nustackdev/ui-kit";
import { useEffect, useLayoutEffect, useRef } from "react";
import { routeAnchorClick } from "../core/router";
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
	const mainRef = useRef<HTMLElement | null>(null);
	const booted = useBooted();
	const split = useRef<ResizablePanelGroupHandle | null>(null);
	const splitEl = useRef<HTMLDivElement | null>(null);
	// The rail's panel: the real rail, or its placeholder until the tree lands.
	const rail = sidebar !== null || !booted;
	const collapsed = useRailCollapsed() && rail;
	useRailShortcut();
	useNewPlaneShortcut();
	useTab(viewer, sidebar);

	// Before the first paint, so the reopen button is right from the start.
	useLayoutEffect(() => {
		if (split.current) migrateRail(split.current, splitEl.current);
		bindRail(split);
		return () => bindRail(null);
	}, []);

	useEffect(() => {
		const main = mainRef.current;
		if (!main) return;
		const onClick = (e: MouseEvent) => {
			routeAnchorClick(e);
		};
		main.addEventListener("click", onClick);
		return () => main.removeEventListener("click", onClick);
	}, []);

	return (
		<div className={shellRoot}>
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
					<main ref={mainRef} className={shellMain} data-rail={collapsed ? "collapsed" : undefined}>
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
