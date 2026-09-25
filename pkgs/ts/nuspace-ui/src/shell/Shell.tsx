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
// Before the tree lands neither region is on it. The shell still draws: the
// rail as its chrome with skeleton rows, the strip as the viewer skeleton, so
// the boot and a plane switch look alike. Once anything has landed, a region
// still missing is a real absence and says so.

import { EmptyState, NodeView } from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { routeAnchorClick } from "../core/router";
import { useBooted, useTypePath } from "../core/surfaces";
import { useTab } from "../core/tab";
import { shellMain, shellMissing, shellPanePlane, shellRailOpen, shellRoot } from "../design";
import { ViewerSkeleton } from "../pane/ViewerSkeleton";
import {
	focusRailToggle,
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
	const collapsed = useRailCollapsed() && (sidebar !== null || !booted);
	useRailShortcut();
	useTab(viewer, sidebar);

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
			{sidebar ? <NodeView path={sidebar} /> : booted ? null : <RailPlaceholder />}
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
		</div>
	);
}
