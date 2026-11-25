// ToastRef: where the server tells this tab something went wrong. Mirrors
// `nuspace/web/ref.py` `ToastRef`.
//
// It draws nothing of its own. A `show` write is one failed interaction (a
// click, an edit, a move the server refused), its error's type as the title
// and its message under it, shown in the kit's toaster, which the shell
// mounts once (../shell/Shell.tsx). A create whose id was taken is tried
// again instead of toasted (../plane/create.ts).
//
// The other way: a delete toasts here in the browser, with an Undo that goes
// back on this node's path. The node lives as long as the tab, so the Undo
// still lands after the pane that deleted has gone. The server restores the
// plane, or the cells, which come back at the end of their plane.

import { type NodeEntry, toast } from "@nustackdev/ui-kit";
import { typePath } from "../core/surfaces";
import { notifyOp } from "../core/wire";
import { retriedCreate } from "../plane/create";

/** Every op the toaster sends: the Undos of a delete. */
export type Ops = {
	"plane.restore": { plane_id: string };
	/** Restored in one commit, in this order: if one cannot come back, none does. */
	"cell.restore": { cell_ids: string[] };
};

/** Show one `show` payload as a toast. Pure apart from the toast, so it is testable. */
export function applyToastWrite(payload: unknown): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	if (String(p.op ?? "") !== "show") return;
	if (retriedCreate(String(p.type ?? ""), String(p.message ?? ""))) return;
	toast({ tone: "danger", title: String(p.type ?? "Error"), description: String(p.message ?? "") });
}

function undo<K extends keyof Ops & string>(op: K, args: Ops[K]): void {
	const at = typePath("ToastRef");
	if (at) notifyOp<Ops, K>(at, op, args);
}

/** Toast a plane's delete, with an Undo that brings it back with all under it. */
export function deletedPlane(id: string, title: string): void {
	toast({
		title: "Plane deleted",
		description: title,
		action: { label: "Undo", onClick: () => undo("plane.restore", { plane_id: id }) },
	});
}

/** Toast a delete of one cell or several, with an Undo that brings them all back. */
export function deletedCells(ids: string[]): void {
	if (ids.length === 0) return;
	toast({
		title: ids.length === 1 ? "Cell deleted" : `${ids.length} cells deleted`,
		action: { label: "Undo", onClick: () => undo("cell.restore", { cell_ids: [...ids] }) },
	});
}

export const ToastRef: NodeEntry = {
	component: () => null,
	handlers: { write: (_ctx, payload) => applyToastWrite(payload) },
};
