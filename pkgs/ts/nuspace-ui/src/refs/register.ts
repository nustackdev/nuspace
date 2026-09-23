// Every node type nuspace ships, registered on import.
//
// Same shape as the kit's own `nodes/index.ts`: one module per type, each
// exporting a `NodeEntry` -- a component, the handlers for the ops the type
// answers itself, and a dispose if it holds a resource. Data and behaviour do
// not share an object; a node's state IS its props.
//
// Every key here is a `_wire_type` on the python side and the two spellings
// have to match exactly. A write addressed at a type nobody registered is
// dropped in silence.
//
// Importing this module registers them. `main.tsx` does it once, before the
// socket can dispatch anything.

import { type NodeEntry, register } from "@nustackdev/ui-kit";
import { RouteRef } from "./route";
import { SidebarRef } from "./sidebar/sidebar";
import { ProseRef } from "./viewer/ProseRef";
import { ViewerRef } from "./viewer/viewer";

export const nuspaceEntries: Record<string, NodeEntry> = {
	SidebarRef,
	ViewerRef,
	// Structural and pulled-only: the server reads the route out of it, and it
	// renders nothing.
	RouteRef,
	// ProseRef is nu's, not nuspace's, and the kit already registers one.
	// This one REPLACES it, and the last `register` for a name wins, so this
	// map has to be applied after the kit's. The kit editor knows nothing
	// about neighbouring blocks, by design; a text block is a block, so
	// nuspace wraps that editor and rebuilds split, merge-up, arrow travel and
	// the slash menu on top. A ProseRef somewhere that is not a block finds no
	// block context and gets the kit's plain behaviour back.
	ProseRef,
};

for (const [type, entry] of Object.entries(nuspaceEntries)) register(type, entry);
