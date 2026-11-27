// What a cell or a plane is and how it runs, for its menu.
//
// Asked for when the menu opens, and only then: a cell's menu sends
// `cell.info` with the cell's id, the pane's `...` sends `plane.info`, and
// the server answers once with `set_cell_info` or `set_plane_info` on the
// pane's node (../pane/state.ts). Nothing keeps either live, and each open
// asks again.
//
// A cell's run is its newest cell run in the plane run this pane follows,
// the one its status is read off; a plane's is that plane run. A run's `id`
// is "" when there is none. Times arrive as epoch seconds, 0 for never, and
// are kept as epoch ms, null for never, the way the kit's RelativeTime takes
// them.

import type { CellState } from "./types";

/** One run, a cell's or a plane's. */
export type RunInfo = {
	/** "" for none: every other field is then empty. */
	id: string;
	/** The cell's version it ran. 0 for a plane's run, which runs no one version. */
	version: number;
	/** Who asked for it: `nav`, `reload`, ... */
	by: string;
	/** The backend it runs on. */
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
	run: RunInfo;
};

export type PlaneInfo = {
	planeId: string;
	/** The PlaneSpec it was made from, "" for none. */
	spec: string;
	/** That spec's label as installed, "" for none. */
	label: string;
	/** How many cells it holds, and how many planes sit inside it. */
	cells: number;
	children: number;
	createdAt: number | null;
	modifiedAt: number | null;
	/** The plane run this pane follows. */
	run: RunInfo;
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

function coerceRun(raw: unknown): RunInfo {
	const run = record(raw);
	return {
		id: str(run, "id"),
		version: int(run, "version"),
		by: str(run, "by"),
		backend: str(run, "backend"),
		createdAt: stamp(run, "created_at"),
		startedAt: stamp(run, "started_at"),
		endedAt: stamp(run, "ended_at"),
		exit: str(run, "exit"),
		error: str(run, "error"),
	};
}

/** A wire answer about a cell, or null for one that names no cell. */
export function coerceCellInfo(raw: unknown): CellInfo | null {
	const r = record(raw);
	const cellId = str(r, "cell_id");
	if (!cellId) return null;
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
		run: coerceRun(r.run),
	};
}

/** A wire answer about the pane's plane, or null for one that names no plane. */
export function coercePlaneInfo(raw: unknown): PlaneInfo | null {
	const r = record(raw);
	const planeId = str(r, "plane_id");
	if (!planeId) return null;
	return {
		planeId,
		spec: str(r, "spec"),
		label: str(r, "label"),
		cells: int(r, "cells"),
		children: int(r, "children"),
		createdAt: stamp(r, "created_at"),
		modifiedAt: stamp(r, "modified_at"),
		run: coerceRun(r.run),
	};
}

/**
 * A run as a state, the way a cell's status reads its cell run: none is
 * idle, not started is starting, started and not ended is running; ended,
 * failed is failed, interrupted or killed is stopped, ok is idle.
 */
export function runState(run: RunInfo): CellState {
	if (!run.id) return "idle";
	if (run.endedAt === null) return run.startedAt === null ? "starting" : "running";
	if (run.exit === "failed") return "failed";
	if (run.exit === "interrupted" || run.exit === "killed") return "stopped";
	return "idle";
}
