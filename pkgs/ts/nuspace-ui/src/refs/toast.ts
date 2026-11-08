// ToastRef: where the server tells this tab something went wrong. Mirrors
// `nuspace/devices/web/utils.py` `ToastRef`.
//
// Write-only: it draws nothing of its own. A `show` write is one failed
// interaction (a click, an edit, a pin the server refused), its error's type
// as the title and its message under it, shown in the kit's toaster, which
// the shell mounts once (../shell/Shell.tsx).

import { type NodeEntry, toast } from "@nustackdev/ui-kit";

/** Show one `show` payload as a toast. Pure apart from the toast, so it is testable. */
export function applyToastWrite(payload: unknown): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	if (String(p.op ?? "") !== "show") return;
	toast({ tone: "danger", title: String(p.type ?? "Error"), description: String(p.message ?? "") });
}

export const ToastRef: NodeEntry = {
	component: () => null,
	handlers: { write: (_ctx, payload) => applyToastWrite(payload) },
};
