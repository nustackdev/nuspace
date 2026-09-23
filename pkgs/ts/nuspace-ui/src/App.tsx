import { NodeView, Spinner, TooltipProvider } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./app/connect";
import { useBooted, useTypePath } from "./app/surfaces";
import { shellBooting, shellMain, shellMissing, shellRoot } from "./design";

// The shell: a sidebar and a Viewer, side by side, and nothing else.
//
// There is no top strip, no surface switcher and no chrome in the corner,
// because there is no third region to switch to and the two controls the window
// still has (the connection pill and the theme flip) sit in the sidebar's
// footer. The sidebar lists every Plane that draws, under a section per group,
// and the Viewer draws whichever one the URL names, so navigation is entirely
// the sidebar's and the shell only places the two.
//
// Both are found BY TYPE (see app/surfaces.ts), not by a slot name. Where
// python hangs them is python's call, and the wire type is the one thing about
// a region both sides already agree on.
//
// The socket is opened here and nowhere else. What it is doing is read through
// `useConnectionStatus` by whoever draws it, so a reconnect never re-renders
// the shell.

export function App() {
	useNuspaceConnection();
	const booted = useBooted();
	const sidebar = useTypePath("SidebarRef");
	const viewer = useTypePath("ViewerRef");

	if (!booted) {
		return (
			<div className={shellBooting}>
				<Spinner size="sm" tone="neutral" label="Connecting" />
				waiting for the tree...
			</div>
		);
	}

	return (
		<TooltipProvider>
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
		</TooltipProvider>
	);
}
