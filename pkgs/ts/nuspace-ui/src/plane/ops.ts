// The Viewer op table, browser side. Mirrors
// `nuspace/web/viewer/interactions.py`.
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
// is on this side because what the URL names is a fact about what the Viewer
// has open, and `plane.meta` because the settings are flipped from a pane.
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
	 * The full ordered list of open panes, left to right, sent whenever it
	 * changes and on load. No kv write: the answer is a `set_plane` plus a
	 * `set_status` per Plane.
	 */
	"planes.open": { plane_ids: string[] };
	/**
	 * Shallow-merge into the Plane's `meta`. The pane applies it optimistically
	 * and the next `set_plane` confirms it.
	 */
	"plane.meta": { plane_id: string; meta: Record<string, unknown> };
	"cell.create": {
		plane_id: string;
		cell_id: string;
		/** The snippet it is made from. The server stores that snippet's
		 *  program, or a blank one when no snippet has this name. */
		name: string;
		index: number;
	};
	/** Replaces the stored program. Nothing else about the cell moves. */
	"cell.update": { plane_id: string; cell_id: string; source: string };
	"cell.delete": { plane_id: string; cell_id: string };
	/** Keeps the cell's id, and so its kv namespace, on the new Plane. */
	"cell.move": {
		plane_id: string;
		cell_id: string;
		to_plane_id: string;
		index: number;
	};
	"cell.reorder": { plane_id: string; cell_ids: string[] };
};

/** Send one op. Threaded down from the strip (../main/Main.tsx) into each plane. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
