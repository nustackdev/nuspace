// The node types the mobile shell draws, registered on import. The shared ones
// are ../refs/register.ts. ./App.tsx imports this, so it loads with the mobile
// shell's chunk and never on desktop.
//
// SidebarRef keeps desktop's write body (the sidebar's state is shared) and
// draws nothing in the tree: the mobile shell puts its sidebar screen where it
// wants it and reads the node by its path.

import { type NodeEntry, register } from "@nustackdev/ui-kit";
import { applySidebarWrite } from "../sidebar/state";
import { MobileViewer } from "./Viewer";

export const mobileEntries: Record<string, NodeEntry> = {
	SidebarRef: {
		component: () => null,
		handlers: {
			write: (ctx, payload) => ctx.update((props) => applySidebarWrite(props, payload)),
		},
	},
	ViewerRef: { component: MobileViewer },
};

for (const [type, entry] of Object.entries(mobileEntries)) register(type, entry);
