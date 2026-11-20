// Where a cell can be transferred to: another plane, picked from a list.
//
// The list is asked for when the cell's "Move to plane" picker opens, and
// only then: the pane sends `cell.targets`, the server answers once with
// `set_targets` on the pane's node (../pane/state.ts), every web plane that
// is editable, not removed and not a system plane. Nothing keeps it live,
// and each open asks again. The core op does not read `editable`; this
// list is where the web keeps to it.
//
// The pane leaves its own plane out: `cell.transfer` to the cell's own plane
// is refused (that is a reorder, `cell.move`). A system plane as the source
// is refused by the op too, and the refusal toasts.
//
// A transfer sends the op and nothing more: the cell leaves this pane when
// its plane's cells ship again, and lands on the other's.

import { UNTITLED } from "../core/looks";

/** A plane a cell can go to, as `set_targets` ships it. `""` for no title or icon. */
export type Target = { id: string; title: string; icon: string };

/** A wire target list. Entries with no id are dropped. */
export function coerceTargets(raw: unknown): Target[] {
	if (!Array.isArray(raw)) return [];
	const out: Target[] = [];
	for (const e of raw) {
		if (!e || typeof e !== "object") continue;
		const r = e as Record<string, unknown>;
		const id = typeof r.id === "string" ? r.id : "";
		if (!id) continue;
		const text = (k: string) => (typeof r[k] === "string" ? (r[k] as string) : "");
		out.push({ id, title: text("title"), icon: text("icon") });
	}
	return out;
}

/** Where a cell of plane `planeId` can go: every other target, by title, "Untitled" for none. */
export function targetsFrom(targets: readonly Target[], planeId: string): Target[] {
	return targets
		.filter((t) => t.id !== planeId)
		.map((t) => ({ ...t, title: t.title || UNTITLED }))
		.sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id));
}
