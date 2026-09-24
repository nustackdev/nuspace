// Every node type nuspace ships, registered on import.
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
// Importing this module registers them. `main.tsx` does it once, before the
// socket can dispatch anything.

import { type NodeEntry, register } from "@nustackdev/ui-kit";
import { RouteRef } from "./route";
import { SidebarRef } from "./sidebar";
import { ViewerRef } from "./viewer";

export const nuspaceEntries: Record<string, NodeEntry> = {
	SidebarRef,
	ViewerRef,
	// Structural and pulled-only: the server reads the route out of it, and it
	// renders nothing.
	RouteRef,
};

for (const [type, entry] of Object.entries(nuspaceEntries)) register(type, entry);
