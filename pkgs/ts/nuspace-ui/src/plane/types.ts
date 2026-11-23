// Plane wire types + coercion: what a pane's writes carry (`set_head`,
// `set_cells` with its layout, `set_status`, `set_trail`, `set_absent`).
//
// msgpack payloads arrive untyped, so every field is narrowed here and nowhere
// else. Everything downstream can assume these shapes.
//
// A cell carries its classes, the protocols it keeps, resolved Nu side. The
// core only routes by them (./intents.ts); what a class means is the sugar
// layer's (./sugar), the one place that knows any.
//
// Cell order is list position in the Plane's `cells` on the server, so cells
// arrive already in order and carry no `order` field to renormalise. On the
// web that order is membership only: the layout beside it is how they draw.

import { PLANE_WIDTHS, type PlaneWidth } from "../design";

/** Which way the caret leaves an editor across a cell boundary. */
export type ExitDir = "up" | "down";

/** Fixed contract, shared with the out-of-process executor. Do not redesign. */
export type CellState = "invalid" | "idle" | "starting" | "running" | "stopped" | "failed";

export type CellStatus = {
	cell_id: string;
	state: CellState;
	error: string | null;
};

export type Cell = {
	id: string;
	/** Its handle, what code and agents reach it by. "" when it has none. */
	key: string;
	/** The Nu program this cell stores. */
	source: string;
	/** Whether its program draws, as the server worked out from the source.
	 *  Null when it never said (an older cell): it may draw. */
	draws: boolean | null;
	/** The protocols it keeps, read Nu side off the spec it was made from:
	 *  `["prose"]`. Empty for a cell made from no spec. The only thing a
	 *  sugar (./sugar) binds to. */
	classes: string[];
	/** Never null. Every cell compiles, runs and is supervised. */
	status: CellStatus;
};

// A cell carries no field list. The refs its program mounts arrive as
// ordinary nodes under the cell's own address and the browser learns them
// from the write stream -- see ./cell/address.ts, which is the one file that knows
// where that address is.

/**
 * The Plane's own settings, as the pane's `set_head` ships them. Open-ended: the
 * named keys are the ones the browser reads today, and anything else the
 * server adds rides along untouched so a `plane.web` flags merge never drops it.
 */
export type PlaneMeta = Record<string, unknown> & {
	/** Whether the Plane's own Cells can be authored from in here. The
	 *  Plane's call, never the Viewer's. */
	editable: boolean;
	/** How wide the plane runs in its pane, at most: page, board or full. */
	width: PlaneWidth;
	/** Its handle, what code and agents reach it by. "" when it has none. */
	key: string;
};

/**
 * How a pane heads its plane, as `set_head` ships it: its title, whether
 * remove refuses it (`system`, so the pane offers no delete), and its
 * settings (icon, key and web flags).
 */
export type PaneHead = {
	title: string;
	system: boolean;
	meta: PlaneMeta;
};

/** A wire head. Its flat fields fold into `meta`, which keeps them by name. */
export function coerceHead(raw: unknown): PaneHead {
	const r =
		raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
	return {
		title: String(r.title ?? ""),
		system: r.system === true,
		meta: coerceMeta({
			editable: r.editable,
			width: r.width,
			key: r.key,
			icon: typeof r.icon === "string" ? r.icon : "",
		}),
	};
}

/** What a pane's plane draws with: its head and its cells, once both have landed. */
export type ActivePlane = {
	plane_id: string;
	title: string;
	meta: PlaneMeta;
	cells: Cell[];
	/** How the cells are drawn (`coerceLayout`). Left out, one cell per row, in `cells` order. */
	layout?: LayoutItem[];
	/** A protected plane: no cell is dropped onto it from another. */
	system?: boolean;
};

/** One step of a pane's trail: a plane above it, by id and title. */
export type Crumb = { id: string; title: string };

/** A wire trail, top first. Entries with no id are dropped. */
export function coerceTrail(raw: unknown): Crumb[] {
	if (!Array.isArray(raw)) return [];
	const out: Crumb[] = [];
	for (const e of raw) {
		if (!e || typeof e !== "object") continue;
		const r = e as Record<string, unknown>;
		const id = String(r.id ?? "");
		if (id) out.push({ id, title: String(r.title ?? "") });
	}
	return out;
}

/**
 * Why an open pane has no Plane to draw, as `set_absent.reason` ships it:
 * no Plane by that id, or one that runs without a view.
 */
export type AbsentReason = "missing" | "headless";

/** A wire reason, or null for one this browser does not know. */
export function coerceAbsent(raw: unknown): AbsentReason | null {
	return raw === "missing" || raw === "headless" ? raw : null;
}

/** One registered Cell, as the `/` menu offers it. `group` heads its
 *  section, `icon` is spelled as a plane's (../icon/parse.ts). */
export type CellSpec = {
	name: string;
	label: string;
	group?: string;
	icon?: string;
	description?: string;
	/** The protocols its cells keep. */
	classes?: string[];
	/** The classes it is the default of, resolved Nu side: one spec each. */
	default_for?: string[];
};

/** `invalid` never compiled; `failed` ran and died. They read differently. */
export function isBad(s: CellState): boolean {
	return s === "invalid" || s === "failed";
}

export function isLive(s: CellState): boolean {
	return s === "running" || s === "starting";
}

// -- Coercion ----------------------------------------------------------------

const STATES: CellState[] = ["invalid", "idle", "starting", "running", "stopped", "failed"];

/**
 * The named flags default to false, the width to page and the key to "" when
 * absent or unknown, whatever else is there.
 */
export function coerceMeta(raw: unknown): PlaneMeta {
	const r =
		raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
	return {
		...r,
		editable: r.editable === true,
		width: PLANE_WIDTHS.includes(r.width as PlaneWidth) ? (r.width as PlaneWidth) : "page",
		key: typeof r.key === "string" ? r.key : "",
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
			key: typeof r.key === "string" ? r.key : "",
			source: String(r.source ?? ""),
			draws: typeof r.draws === "boolean" ? r.draws : null,
			classes: Array.isArray(r.classes) ? r.classes.map(String) : [],
			status: coerceStatus(r.status) ?? {
				cell_id: id,
				state: "idle",
				error: null,
			},
		});
	}
	return out;
}

// -- Layout ------------------------------------------------------------------
//
// How a web plane arranges its cells, as `set_cells` ships it beside them
// (`nuspace/web/layout`): items in drawing order, each one cell alone or a
// strip of columns side by side at their shares, the cells of a column
// stacked. Fixed up on the server against the same cells, so every cell sits
// in exactly one item. The pure logic over it is ./layout/model.ts.

/** One column of a strip: its cells top to bottom, and its share of the strip's width. */
export type LayoutColumn = { cells: string[]; share: number };

/** A cell alone on its row. */
export type CellItem = { id: string; kind: "cell"; cell: string };

/** Columns side by side, at their shares (summing to 1). Two cells or more. */
export type StripItem = { id: string; kind: "strip"; columns: LayoutColumn[] };

export type LayoutItem = CellItem | StripItem;

/** An item as an op stores it: its id is the key, never in the value. */
export type StoredItem =
	| { kind: "cell"; cell: string }
	| { kind: "strip"; columns: LayoutColumn[] };

function coerceColumns(raw: unknown, live: Set<string>, seen: Set<string>): LayoutColumn[] {
	if (!Array.isArray(raw)) return [];
	const out: LayoutColumn[] = [];
	for (const c of raw) {
		if (!c || typeof c !== "object") continue;
		const r = c as Record<string, unknown>;
		const cells = (Array.isArray(r.cells) ? r.cells : [])
			.map(String)
			.filter((id) => live.has(id) && !seen.has(id));
		for (const id of cells) seen.add(id);
		const share = typeof r.share === "number" && r.share > 0 ? r.share : 0;
		if (cells.length && share) out.push({ cells, share });
	}
	const total = out.reduce((a, c) => a + c.share, 0);
	return out.map((c) => ({ ...c, share: c.share / total }));
}

/**
 * A wire layout, kept to `cells`: what names no live cell, or one an earlier
 * item holds, is dropped; a strip left with one cell reads as a cell item.
 * A cell no item holds goes last on its own, its id its cell id. That never
 * happens with a server that ships the layout; with none (an older one, a
 * test) every cell is its own item, in `cells` order.
 */
export function coerceLayout(raw: unknown, cells: readonly { id: string }[]): LayoutItem[] {
	const live = new Set(cells.map((c) => c.id));
	const seen = new Set<string>();
	const out: LayoutItem[] = [];
	for (const e of Array.isArray(raw) ? raw : []) {
		if (!e || typeof e !== "object") continue;
		const r = e as Record<string, unknown>;
		const id = typeof r.id === "string" ? r.id : "";
		if (!id) continue;
		if (r.kind === "cell") {
			const cell = typeof r.cell === "string" ? r.cell : "";
			if (!live.has(cell) || seen.has(cell)) continue;
			seen.add(cell);
			out.push({ id, kind: "cell", cell });
		} else if (r.kind === "strip") {
			const columns = coerceColumns(r.columns, live, seen);
			const held = columns.flatMap((c) => c.cells);
			if (held.length === 1) out.push({ id, kind: "cell", cell: held[0] });
			else if (held.length > 1) out.push({ id, kind: "strip", columns });
		}
	}
	for (const c of cells) if (!seen.has(c.id)) out.push({ id: c.id, kind: "cell", cell: c.id });
	return out;
}
