// Page wire types + coercion: what a `set_page` carries.
//
// msgpack payloads arrive untyped, so every field is narrowed here and nowhere
// else. Everything downstream can assume these shapes.
//
// Block order is list position in the Plane's `order` on the server, so blocks
// arrive already in order and carry no `order` field to renormalise.

/** Which way the caret leaves an editor across a block boundary. */
export type ExitDir = "up" | "down";

/** Fixed contract, shared with the out-of-process executor. Do not redesign. */
export type SectionState = "invalid" | "idle" | "starting" | "running" | "stopped" | "failed";

export type SectionStatus = {
	section_id: string;
	state: SectionState;
	error: string | null;
	started_at: number | null;
};

export type Block = {
	id: string;
	name: string;
	/** The Nu program this block stores. */
	source: string;
	/** Never null. Every block compiles, runs and is supervised. */
	status: SectionStatus;
};

// A block carries no field list. The refs its program mounts arrive as
// ordinary nodes under the block's own address and the browser learns them
// from the write stream -- see ./block/address.ts, which is the one file that knows
// where that address is.

/**
 * The Plane's own settings, as `set_page.meta` ships them. Open-ended: the two
 * named keys are the ones the browser reads today, and anything else the
 * server adds rides along untouched so a `page.meta` merge never drops it.
 */
export type PageMeta = Record<string, unknown> & {
	/** Whether the Plane's own Cells can be authored from in here. The
	 *  Plane's call, never the Viewer's. */
	editable: boolean;
	/** The page spans its pane instead of the reading measure. */
	full_width: boolean;
	/** A tight head and no run-off under the last block. */
	compact: boolean;
};

export type ActivePage = {
	page_id: string;
	title: string;
	meta: PageMeta;
	blocks: Block[];
};

/** One registered snippet, as the `/` menu offers it. */
export type SlashSnippet = { name: string; label: string };

/** `invalid` never compiled; `failed` ran and died. They read differently. */
export function isBad(s: SectionState): boolean {
	return s === "invalid" || s === "failed";
}

export function isLive(s: SectionState): boolean {
	return s === "running" || s === "starting";
}

// -- coercion ----------------------------------------------------------------

const STATES: SectionState[] = ["invalid", "idle", "starting", "running", "stopped", "failed"];

/** Both named keys default to false when absent, whatever else is there. */
export function coerceMeta(raw: unknown): PageMeta {
	const r =
		raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
	return {
		...r,
		editable: r.editable === true,
		full_width: r.full_width === true,
		compact: r.compact === true,
	};
}

export function coerceStatus(raw: unknown): SectionStatus | null {
	if (!raw || typeof raw !== "object") return null;
	const r = raw as Record<string, unknown>;
	const state = String(r.state ?? "idle") as SectionState;
	return {
		section_id: String(r.section_id ?? ""),
		state: STATES.includes(state) ? state : "idle",
		error: r.error ? String(r.error) : null,
		started_at: typeof r.started_at === "number" && r.started_at > 0 ? r.started_at : null,
	};
}

export function coerceBlocks(raw: unknown): Block[] {
	if (!Array.isArray(raw)) return [];
	const out: Block[] = [];
	for (const b of raw) {
		if (!b || typeof b !== "object") continue;
		const r = b as Record<string, unknown>;
		const id = String(r.id ?? "");
		if (!id) continue;
		out.push({
			id,
			name: String(r.name ?? id),
			source: String(r.source ?? ""),
			status: coerceStatus(r.status) ?? {
				section_id: id,
				state: "idle",
				error: null,
				started_at: null,
			},
		});
	}
	return out;
}
