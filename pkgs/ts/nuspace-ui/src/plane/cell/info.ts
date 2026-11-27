// What a cell is and how it last ran, for its menu.
//
// Asked for when the menu opens, and only then: the pane sends `cell.info`
// with the cell's id, the server answers once with `set_cell_info` on the
// pane's node (../../pane/state.ts). Nothing keeps it live, and each open
// asks again. The state beside it is the cell's own status, which is.
//
// `run` is the cell's newest cell run in the plane run this pane follows,
// the one its status is read off. Its `id` is "" when it has none there.
// Times arrive as epoch seconds, 0 for never, and are kept as epoch ms, null
// for never, the way the kit's RelativeTime takes them.

/** The cell's newest run in this pane's plane run. */
export type CellRunInfo = {
	/** "" for none: every other field is then empty. */
	id: string;
	/** The cell's version it ran. */
	version: number;
	/** Who asked for it: `nav`, `reload`, ... */
	by: string;
	/** The backend its worker runs on. */
	backend: string;
	createdAt: number | null;
	startedAt: number | null;
	endedAt: number | null;
	/** How it ended, "" while it has not. */
	exit: string;
	error: string;
};

export type CellInfo = {
	cellId: string;
	name: string;
	key: string;
	/** The spec it was made from, "" for none. */
	spec: string;
	/** That spec's label and icon as installed, "" for none. */
	label: string;
	icon: string;
	/** Counts source writes. */
	version: number;
	createdAt: number | null;
	modifiedAt: number | null;
	run: CellRunInfo;
};

function str(r: Record<string, unknown>, k: string): string {
	return typeof r[k] === "string" ? (r[k] as string) : "";
}

function int(r: Record<string, unknown>, k: string): number {
	return typeof r[k] === "number" && Number.isFinite(r[k]) ? (r[k] as number) : 0;
}

/** Epoch seconds to epoch ms, null for none. */
function stamp(r: Record<string, unknown>, k: string): number | null {
	const s = int(r, k);
	return s > 0 ? s * 1000 : null;
}

function record(raw: unknown): Record<string, unknown> {
	return raw && typeof raw === "object" && !Array.isArray(raw)
		? (raw as Record<string, unknown>)
		: {};
}

/** A wire answer, or null for one that names no cell. */
export function coerceCellInfo(raw: unknown): CellInfo | null {
	const r = record(raw);
	const cellId = str(r, "cell_id");
	if (!cellId) return null;
	const run = record(r.run);
	return {
		cellId,
		name: str(r, "name"),
		key: str(r, "key"),
		spec: str(r, "spec"),
		label: str(r, "label"),
		icon: str(r, "icon"),
		version: int(r, "version"),
		createdAt: stamp(r, "created_at"),
		modifiedAt: stamp(r, "modified_at"),
		run: {
			id: str(run, "id"),
			version: int(run, "version"),
			by: str(run, "by"),
			backend: str(run, "backend"),
			createdAt: stamp(run, "created_at"),
			startedAt: stamp(run, "started_at"),
			endedAt: stamp(run, "ended_at"),
			exit: str(run, "exit"),
			error: str(run, "error"),
		},
	};
}
