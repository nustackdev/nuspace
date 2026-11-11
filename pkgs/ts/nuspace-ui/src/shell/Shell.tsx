// The shell: the sidebar and the desk area, side by side on one canvas
// (`ground-deep` behind both, 6px between them), and the toaster a failed
// interaction shows in (../refs/toast.ts).
//
// There is no top bar, because there is no third region, and the two controls the window still has (the
// connection dot and the theme flip) sit in the sidebar's bottom bar. Folded,
// the sidebar does not vanish, it gets thin: the shell draws its rail
// (../sidebar/SidebarRail.tsx) left of the split, the toggle that brings it
// back on top and the sidebar's first level as icons under it. The sidebar lists every Plane that draws, and the desk
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
// Enter to the router's rule (core/router.ts `paneRule`): a plain click on a
// plane url navigates the pane it sits in, in place, and opens solo from
// anywhere else, and anything that is not the app's url is left to the
// browser, as are Cmd, Shift and middle clicks. The sidebar routes its pane
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
import { useLayoutEffect, useRef } from "react";
import { BOOTING_DELAY_MS, useAfter } from "../core/delay";
import { paneRule } from "../core/router";
import { useBooted, useTypePath } from "../core/surfaces";
import {
	shellMain,
	shellMissing,
	shellPanePlane,
	shellRoot,
	shellSlot,
	shellSplitHandle,
} from "../design";
import { useDragScroll } from "../desk/autoscroll";
import { ViewerSkeleton } from "../pane/ViewerSkeleton";
import {
	bindSidebar,
	publishSidebar,
	SIDEBAR_LAYOUT_KEY,
	SidebarPlaceholder,
	SidebarRail,
	useNavShortcuts,
	useNewPlaneShortcut,
	usePlaneTree,
	useSidebarCollapsed,
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
	const collapsed = useSidebarCollapsed() && side;
	const tree = usePlaneTree(sidebar);
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

	useAnchorCatcher(rootRef, paneRule);

	return (
		<div ref={rootRef} className={shellRoot}>
			{collapsed ? <SidebarRail tree={tree} /> : null}
			<ResizablePanelGroup
				ref={split}
				storageKey={SIDEBAR_LAYOUT_KEY}
				onLayout={(sizes) => {
					if (sizes.length > 1) publishSidebar(sizes[0] <= 0);
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
								className={shellSlot}
							>
								{sidebar ? <NodeView path={sidebar} /> : <SidebarPlaceholder />}
							</ResizablePanel>,
							<ResizableHandle
								key="sidebar-edge"
								aria-label="Resize sidebar"
								className={shellSplitHandle}
							/>,
						]
					: null}
				<ResizablePanel key="main" id="shell-main" className={shellSlot}>
					<main className={shellMain}>
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
			<Toaster />
		</div>
	);
}
