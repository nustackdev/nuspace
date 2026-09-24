// SidebarRef: the node type the sidebar is mounted as. Mirrors
// `nuspace/web/sidebar`. The component and the write body live in ../sidebar.

import type { NodeEntry } from "@nustackdev/ui-kit";
import { Sidebar } from "../sidebar/Sidebar";
import { applySidebarWrite } from "../sidebar/state";

export const SidebarRef: NodeEntry = {
	component: Sidebar,
	handlers: { write: (ctx, payload) => ctx.update((props) => applySidebarWrite(props, payload)) },
};
