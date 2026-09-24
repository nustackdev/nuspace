// The shell: the sidebar and the main strip, side by side, and nothing else.
//
// There is no top strip, no surface switcher and no chrome in the corner,
// because there is no third region to switch to and the two controls the window
// still has (the connection pill and the theme flip) sit in the sidebar's
// footer. The sidebar lists every Plane that draws, under a section per group,
// and the main strip draws whichever ones the URL names, so navigation is
// entirely the sidebar's and the shell only places the two.
//
// Both are found BY TYPE (see app/surfaces.ts), not by a slot name. Where
// python hangs them is python's call, and the wire type is the one thing about
// a region both sides already agree on.
//
// Links a cell draws (the kit's LinkRef, a markdown link) are plain anchors.
// One listener on the main strip routes a click on a same-origin one to /<id>
// or /<a>+<b> through the router (app/router.ts `routeAnchorClick`), so it
// switches panes instead of reloading the tab, and cmd/ctrl-click opens a
// split as in the sidebar. Native, not React: it has to see anchors the kit
// renders without handlers of ours, and it runs before the browser follows
// them.

import { NodeView } from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { routeAnchorClick } from "../app/router";
import { useTypePath } from "../app/surfaces";
import { shellMain, shellMissing, shellRoot } from "../design";

export function Shell() {
	const sidebar = useTypePath("SidebarRef");
	const viewer = useTypePath("ViewerRef");
	const mainRef = useRef<HTMLElement | null>(null);

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
			{sidebar ? <NodeView path={sidebar} /> : null}
			<main ref={mainRef} className={shellMain}>
				{viewer ? (
					<NodeView path={viewer} />
				) : (
					<section className={shellMissing}>no Viewer on the tree</section>
				)}
			</main>
		</div>
	);
}
