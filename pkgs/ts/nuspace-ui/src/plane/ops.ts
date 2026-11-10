// The Viewer op table, browser side. Mirrors
// `nuspace/devices/web/viewer/interactions.py`.
//
// One ref per op: a notify goes to `<viewer ref>.ops.<name>` and the payload
// carries that op's arguments and nothing else. There is no `op` key, because
// the path already answered that question, and the server binds one arm per
// path rather than branching on a string.
//
// `Ops` is what keeps the two sides in step: the keys are the op names the
// python ref subscribes to, and each value is exactly the field set the
// matching `nuspace.ops` call reads. Add an interaction on one side and this
// file is where the other side fails to compile.
//
// Every Cell write is here and every Plane write the sidebar makes is in
// ../sidebar/ops.ts. That is the whole line between the two refs. `planes.open`
// is on this side because which panes are open is a fact about what the Viewer
// has open, and `plane.web` because the settings are flipped from a pane.
//
// ## Ids are minted here
//
// `cell.create` carries the id of the Cell being made. That makes a create
// a pure function of its event on the server, and lets the caret aim at a
// known id rather than guess at one from a position. Use `mintId` from
// ../core/ids; do not invent a second scheme.

/** Every op the Viewer sends, with its argument shape. */
export type Ops = {
	/**
	 * The full ordered list of open panes, left to right, and each one's
	 * params by Plane, sent whenever either changes and on load. One way: the
	 * server writes it as the tab's pane order and each pane's params (data:
	 * nothing runs again), and answers with a `set_plane` plus a `set_status`
	 * per Plane.
	 */
	"planes.open": { plane_ids: string[]; params: Record<string, Record<string, string>> };
	/**
	 * Set the Plane's web flags given (`editable`, `full_width`, `compact`).
	 * The pane applies them optimistically and the next `set_plane` confirms.
	 */
	"plane.web": { plane_id: string; flags: Record<string, boolean> };
	"cell.create": {
		plane_id: string;
		cell_id: string;
		/** The Cell it is made from. The server stores that Cell's
		 *  program, or the starter program when no Cell has this name. */
		name: string;
		/** Before or after a cell of the plane, neither for the end. */
		before?: string;
		after?: string;
	};
	/** Replaces the stored program. Nothing else about the cell moves. A cell
	 *  id is unique across the space, so it is the whole address. */
	"cell.update": { cell_id: string; source: string };
	"cell.delete": { cell_id: string };
	/** Set or change the cell's key. A key taken or misspelled is refused
	 *  server side, and the refusal toasts. */
	"cell.key": { cell_id: string; key: string };
	/** Drop the cell's key, free for another cell. */
	"cell.remove_key": { cell_id: string };
	/** Set or change the plane's key, refused server side like a cell's. */
	"plane.key": { plane_id: string; key: string };
	/** Drop the plane's key, free for another plane. */
	"plane.remove_key": { plane_id: string };
	/** One cell before or after another of its plane, neither for the end. */
	"cell.move": { cell_id: string; before?: string; after?: string };
	/** Run the cell again in this pane's run. With the run over, the whole
	 *  pane runs again. */
	"cell.restart": { cell_id: string };
	/** Run this pane's plane again: its run stopped, a new one made. */
	"plane.restart": { plane_id: string };
};

/** Send one op. Threaded down from the strip (../main/Main.tsx) into each plane. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;

/**
 * The moves that turn `current` into `next`, one `cell.move` each: walk
 * `next` and put every cell out of place after the one before it. A block
 * moved as one costs a move per cell in it.
 */
export function cellMoves(current: readonly string[], next: readonly string[]): Ops["cell.move"][] {
	const now = current.filter((id) => next.includes(id));
	const out: Ops["cell.move"][] = [];
	next.forEach((id, i) => {
		if (now[i] === id) return;
		const from = now.indexOf(id);
		if (from >= 0) now.splice(from, 1);
		now.splice(i, 0, id);
		out.push(i === 0 ? { cell_id: id, before: now[1] } : { cell_id: id, after: next[i - 1] });
	});
	return out;
}
