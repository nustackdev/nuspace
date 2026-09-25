// Plane wire types + coercion: what a `set_plane` carries.
//
// msgpack payloads arrive untyped, so every field is narrowed here and nowhere
// else. Everything downstream can assume these shapes.
//
// Cell order is list position in the Plane's `order` on the server, so cells
// arrive already in order and carry no `order` field to renormalise.

/** Which way the caret leaves an editor across a cell boundary. */
export type ExitDir = "up" | "down";

/** Fixed contract, shared with the out-of-process executor. Do not redesign. */
export type CellState = "invalid" | "idle" | "starting" | "running" | "stopped" | "failed";

export type CellStatus = {
	cell_id: string;
	state: CellState;
	error: string | null;
	started_at: number | null;
};

export type Cell = {
	id: string;
	name: string;
	/** The Nu program this cell stores. */
	source: string;
	/** The snippet it was made from, "" when none. A cell made from the text
	 *  snippet is a text cell (see ./useTextCells.ts). */
	made_by: string;
	/** Whether its program draws, as the server worked out from the source.
	 *  Null when it never said (an older cell): it may draw. */
	has_ui: boolean | null;
	/** Never null. Every cell compiles, runs and is supervised. */
	status: CellStatus;
};

// A cell carries no field list. The refs its program mounts arrive as
// ordinary nodes under the cell's own address and the browser learns them
// from the write stream -- see ./cell/address.ts, which is the one file that knows
// where that address is.

/**
 * The Plane's own settings, as `set_plane.meta` ships them. Open-ended: the two
 * named keys are the ones the browser reads today, and anything else the
 * server adds rides along untouched so a `plane.meta` merge never drops it.
 */
export type PlaneMeta = Record<string, unknown> & {
	/** Whether the Plane's own Cells can be authored from in here. The
	 *  Plane's call, never the Viewer's. */
	editable: boolean;
	/** The plane spans its pane instead of the reading measure. */
	full_width: boolean;
	/** A tight head and no run-off under the last cell. */
	compact: boolean;
};

export type ActivePlane = {
	plane_id: string;
	title: string;
	meta: PlaneMeta;
	cells: Cell[];
};

/**
 * Why an open pane has no Plane to draw, as `set_absent.reason` ships it:
 * no Plane by that id, or one that runs without a view.
 */
export type AbsentReason = "missing" | "headless";

/** A wire reason, or null for one this browser does not know. */
export function coerceAbsent(raw: unknown): AbsentReason | null {
	return raw === "missing" || raw === "headless" ? raw : null;
}

/** One registered snippet, as the `/` menu offers it. */
export type SlashSnippet = { name: string; label: string };

/** The name reserved for the text snippet, as `nuspace.TEXT`. Its cells are
 *  the text cells (see ./Draft.tsx and ./useTextCells.ts). */
export const TEXT = "text";

/** Whether the text snippet is registered: without it, the text sugar is off. */
export function hasText(snippets: SlashSnippet[]): boolean {
	return snippets.some((s) => s.name === TEXT);
}

/** `invalid` never compiled; `failed` ran and died. They read differently. */
export function isBad(s: CellState): boolean {
	return s === "invalid" || s === "failed";
}

export function isLive(s: CellState): boolean {
	return s === "running" || s === "starting";
}

// -- Coercion ----------------------------------------------------------------

const STATES: CellState[] = ["invalid", "idle", "starting", "running", "stopped", "failed"];

/** Both named keys default to false when absent, whatever else is there. */
export function coerceMeta(raw: unknown): PlaneMeta {
	const r =
		raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
	return {
		...r,
		editable: r.editable === true,
		full_width: r.full_width === true,
		compact: r.compact === true,
	};
}

export function coerceStatus(raw: unknown): CellStatus | null {
	if (!raw || typeof raw !== "object") return null;
	const r = raw as Record<string, unknown>;
	const state = String(r.state ?? "idle") as CellState;
	return {
		cell_id: String(r.cell_id ?? ""),
		state: STATES.includes(state) ? state : "idle",
		error: r.error ? String(r.error) : null,
		started_at: typeof r.started_at === "number" && r.started_at > 0 ? r.started_at : null,
	};
}

export function coerceCells(raw: unknown): Cell[] {
	if (!Array.isArray(raw)) return [];
	const out: Cell[] = [];
	for (const b of raw) {
		if (!b || typeof b !== "object") continue;
		const r = b as Record<string, unknown>;
		const id = String(r.id ?? "");
		if (!id) continue;
		out.push({
			id,
			name: String(r.name ?? id),
			source: String(r.source ?? ""),
			made_by: String(r.made_by ?? ""),
			has_ui: typeof r.has_ui === "boolean" ? r.has_ui : null,
			status: coerceStatus(r.status) ?? {
				cell_id: id,
				state: "idle",
				error: null,
				started_at: null,
			},
		});
	}
	return out;
}
