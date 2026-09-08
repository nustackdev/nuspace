// PagesRef wire types + coercion.
//
// msgpack payloads arrive untyped, so every field is narrowed here and
// nowhere else. Everything downstream can assume these shapes.

import type { MountField } from "@nustackdev/ui-core";

export type PageNode = { id: string | null; title: string; pages: PageNode[] };

export type BlockKind = "prose" | "program";

/** Fixed contract, shared with the out-of-process executor. Do not redesign. */
export type SectionState =
	| "invalid"
	| "idle"
	| "starting"
	| "running"
	| "stopped"
	| "failed";

export type SectionStatus = {
	section_id: string;
	state: SectionState;
	error: string | null;
	started_at: number | null;
};

export type Block = {
	id: string;
	kind: BlockKind;
	source: string;
	order: number;
	fields: MountField[];
	/** null for prose: a prose island is not a program and has no state. */
	status: SectionStatus | null;
};

export type ActivePage = {
	page_id: string | null;
	path: string[];
	title: string;
	blocks: Block[];
};

export type PagesValue = { tree: PageNode; page: ActivePage | null };

export const EMPTY_TREE: PageNode = { id: null, title: "", pages: [] };

/** `invalid` never compiled; `failed` ran and died. They read differently. */
export function isBad(s: SectionState): boolean {
	return s === "invalid" || s === "failed";
}

export function isLive(s: SectionState): boolean {
	return s === "running" || s === "starting";
}

// -- coercion ----------------------------------------------------------------

export function coerceStrs(raw: unknown): string[] {
	return Array.isArray(raw) ? raw.map((s) => String(s)) : [];
}

export function coerceNode(raw: unknown, fallbackId: string | null): PageNode {
	if (!raw || typeof raw !== "object") {
		return { id: fallbackId, title: "", pages: [] };
	}
	const r = raw as Record<string, unknown>;
	const kids = Array.isArray(r.pages) ? r.pages : [];
	return {
		id: r.id == null ? null : String(r.id),
		title: String(r.title ?? ""),
		pages: kids.map((k) => coerceNode(k, null)),
	};
}

const STATES: SectionState[] = [
	"invalid",
	"idle",
	"starting",
	"running",
	"stopped",
	"failed",
];

export function coerceStatus(raw: unknown): SectionStatus | null {
	if (!raw || typeof raw !== "object") return null;
	const r = raw as Record<string, unknown>;
	const state = String(r.state ?? "idle") as SectionState;
	return {
		section_id: String(r.section_id ?? ""),
		state: STATES.includes(state) ? state : "idle",
		error: r.error == null ? null : String(r.error),
		started_at: typeof r.started_at === "number" ? r.started_at : null,
	};
}

export function coerceFields(raw: unknown): MountField[] {
	if (!Array.isArray(raw)) return [];
	const out: MountField[] = [];
	for (const f of raw) {
		if (!f || typeof f !== "object") continue;
		const r = f as Record<string, unknown>;
		const path = String(r.path ?? "");
		const type = String(r.type ?? "");
		if (!path || !type) continue;
		const entry: MountField = { path, type };
		if (r.props && typeof r.props === "object") {
			entry.props = r.props as Record<string, unknown>;
		}
		if (Array.isArray(r.fields)) entry.fields = coerceFields(r.fields);
		out.push(entry);
	}
	return out;
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
			kind: r.kind === "program" ? "program" : "prose",
			source: String(r.snippet ?? r.source ?? ""),
			order: typeof r.order === "number" ? r.order : out.length,
			fields: coerceFields(r.fields),
			status: coerceStatus(r.status),
		});
	}
	return out;
}
