// The node types both shells share, registered on import.
//
// Same shape as the kit's own `nodes/index.ts`: one module per type, each
// exporting a `NodeEntry` -- a component, the handlers for the ops the type
// answers itself, and a dispose if it holds a resource. Data and behaviour do
// not share an object; a node's state IS its props.
//
// The modules in this directory are adapters and nothing more: each maps a
// wire type onto a feature (../sidebar, ../main) and holds no logic of its own.
//
// Every key here is a `_wire_type` on the python side and the two spellings
// have to match exactly. A write addressed at a type nobody registered is
// dropped in silence.
//
// The two types a shell draws, ViewerRef and SidebarRef, are the shell's own:
// desktop registers ./viewer.ts and ./sidebar.ts (./desktop.ts), the mobile
// shell its own (../mobile/refs.ts), so neither bundle carries the other's
// components. Everything here draws nothing.
//
// Importing this module registers them. `main.tsx` does it once, before the
// shell loads and the socket can dispatch anything.

import { type NodeEntry, register } from "@nustackdev/ui-kit";
import { DesksRef } from "./desks";
import { PaneRef } from "./pane";
import { ToastRef } from "./toast";

export const nuspaceEntries: Record<string, NodeEntry> = {
	DesksRef,
	PaneRef,
	ToastRef,
	// Structural and write-only: a cell moving its own pane. Renders nothing.
};

for (const [type, entry] of Object.entries(nuspaceEntries)) register(type, entry);
