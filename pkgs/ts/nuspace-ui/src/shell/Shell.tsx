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

import { NodeView } from "@nustackdev/ui-kit";
import { useTypePath } from "../app/surfaces";
import { shellMain, shellMissing, shellRoot } from "../design";

export function Shell() {
	const sidebar = useTypePath("SidebarRef");
	const viewer = useTypePath("ViewerRef");

	return (
		<div className={shellRoot}>
			{sidebar ? <NodeView path={sidebar} /> : null}
			<main className={shellMain}>
				{viewer ? (
					<NodeView path={viewer} />
				) : (
					<section className={shellMissing}>no Viewer on the tree</section>
				)}
			</main>
		</div>
	);
}
