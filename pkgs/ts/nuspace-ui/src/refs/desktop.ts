// The node types the desktop shell draws, registered on import: the desk area
// and the sidebar. The shared ones are ./register.ts. ../App.tsx imports this,
// so it loads with the desktop shell's chunk and never on a phone.

import { type NodeEntry, register } from "@nustackdev/ui-kit";
import { SidebarRef } from "./sidebar";
import { ViewerRef } from "./viewer";

export const desktopEntries: Record<string, NodeEntry> = { SidebarRef, ViewerRef };

for (const [type, entry] of Object.entries(desktopEntries)) register(type, entry);
