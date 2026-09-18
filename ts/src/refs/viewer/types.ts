// ViewerRef wire types + coercion.
//
// msgpack payloads arrive untyped, so every field is narrowed here and nowhere
// else. Everything downstream can assume these shapes.
//
// Block order is list position in the Plane's `order` on the server, so blocks
// arrive already in order and carry no `order` field to renormalise.

/**
 * Provenance, not type. Every block is a Nu program; `tpl` says what made the
 * one it stores. The editor reads it to pick an affordance and for nothing
 * else.
 */
export type BlockTpl = "text" | "program";

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
	tpl: BlockTpl;
	/** The Nu program this block stores. For a `text` block it is the
	 *  template, identical for every text block on the Plane. */
	source: string;
	/** Never null. Every block compiles, runs and is supervised. */
	status: SectionStatus;
};

// A block carries no field list. The refs its program mounts arrive as
// ordinary nodes under the block's own address and the browser learns them
// from the write stream -- see ./blocks.ts, which is the one file that knows
// where that address is.

export type ActivePage = {
	page_id: string;
	title: string;
	/** Whether the Plane's own Cells can be authored from in here. Its prop,
	 *  never the Viewer's call. */
	editable: boolean;
	blocks: Block[];
};

export type ViewerValue = { page: ActivePage | null };

/** `invalid` never compiled; `failed` ran and died. They read differently. */
export function isBad(s: SectionState): boolean {
	return s === "invalid" || s === "failed";
}

export function isLive(s: SectionState): boolean {
	return s === "running" || s === "starting";
}

// -- coercion ----------------------------------------------------------------

const STATES: SectionState[] = ["invalid", "idle", "starting", "running", "stopped", "failed"];

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
			tpl: r.tpl === "text" ? "text" : "program",
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
