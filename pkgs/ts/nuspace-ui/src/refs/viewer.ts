// ViewerRef: the node type the desk area is mounted as. Mirrors
// `nuspace/web/viewer`. The component is ../main/Desk.tsx.
//
// No write handler: the viewer is written once, at boot, with the `/` menu,
// and everything a pane shows lands on the pane's own node (./pane.ts).

import type { NodeEntry } from "@nustackdev/ui-kit";
import { Desk } from "../main/Desk";

export const ViewerRef: NodeEntry = { component: Desk };
