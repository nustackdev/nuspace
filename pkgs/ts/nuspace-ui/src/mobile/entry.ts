// Marks on a history entry: how the phone's modes live in the url's history
// rather than in flags of their own. The sidebar screen (./sidebar/open.ts)
// and editing a plane's cells (./plane/editing.ts) are each "the entry the
// tab is on carries my mark", so back leaves them, forward comes back to
// them, and nothing has to keep a flag in step with the url.
//
// A mark is one key in the entry's state object, kept beside whatever else
// the state holds.

import type { Entry } from "@nustackdev/ui-kit";

/** The value `entry` carries under `key`; undefined for none. */
export function markOf(entry: Pick<Entry, "state">, key: string): unknown {
	const state = entry.state;
	if (!state || typeof state !== "object" || Array.isArray(state)) return undefined;
	return (state as Record<string, unknown>)[key];
}

/**
 * `state` with `key` set to `value`, or without `key` when `value` is null,
 * kept as it was otherwise. Null when nothing is left.
 */
export function withMark(state: unknown, key: string, value: unknown): unknown {
	const base = state && typeof state === "object" && !Array.isArray(state) ? { ...state } : {};
	const out = base as Record<string, unknown>;
	if (value === null || value === undefined) delete out[key];
	else out[key] = value;
	return Object.keys(out).length ? out : null;
}
