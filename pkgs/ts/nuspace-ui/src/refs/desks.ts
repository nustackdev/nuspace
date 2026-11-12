// DesksRef: where the server ships the desks and the roles. Mirrors
// `nuspace/web/desks/ref.py` `DesksRef`.
//
// Write-only: it draws nothing. `set_desks` and `set_roles` feed ../core/desks.ts,
// which keeps them and hands them to the router; the desk ops go back out
// through this node's path.

import type { NodeEntry } from "@nustackdev/ui-kit";
import { applyDesksWrite } from "../core/desks";

export const DesksRef: NodeEntry = {
	component: () => null,
	handlers: { write: (ctx, payload) => applyDesksWrite(ctx.path, payload) },
};
