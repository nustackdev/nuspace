// The pane's op table, browser side, and the viewer's one op. Mirrors
// `nuspace/web/viewer/interactions.py`.
//
// One ref per op: a notify goes to `<ref>.ops.<name>` and the payload
// carries that op's arguments and nothing else. There is no `op` key, because
// the path already answered that question, and the server binds one arm per
// path rather than branching on a string.
//
// A pane's ops ride its own PaneRef node (`<viewer>/panes/<plane>`), so none
// names its plane: the path says it. Every Cell write is here, and every
// Plane write a pane makes (rename, icon, delete, key, flags, restart). The
// sidebar has its own rename, icon and delete for its own rows
// (../sidebar/ops.ts). `planes.open` is the viewer's, because which panes are
// open is a fact about the viewer, not about one pane.
//
// `Ops` is what keeps the two sides in step: the keys are the op names the
// python ref subscribes to, and each value is exactly the field set the
// matching `nuspace.ops` call reads. Add an interaction on one side and this
// file is where the other side fails to compile.
//
// ## Ids are minted here
//
// `cell.create` carries the id of the Cell being made. That makes a create
// a pure function of its event on the server, and lets the caret aim at a
// known id rather than guess at one from a position. Use `mintId` from
// ../core/ids; do not invent a second scheme.
//
// ## The layout
//
// A web plane draws its cells from its layout (./types.ts `LayoutRow`), and
// every change to it sends the whole new rows, never `cell.move`: a drop
// (./layout/model.ts `dropOp`), a key, a resize, a create. The server
// reconciles what it gets with the plane's cells before it stores it.

import type { LayoutRow } from "./types";

/** The viewer's one op. */
export type ViewerOps = {
	/**
	 * The full ordered list of open panes, left to right, and each one's
	 * params by Plane, sent whenever either changes and on load. One way: the
	 * server writes it as the tab's pane order and each pane's params (data:
	 * nothing runs again), and answers on each pane's own node.
	 */
	"planes.open": { plane_ids: string[]; params: Record<string, Record<string, string>> };
};

/** Every op a pane sends, on its own node, with its argument shape. */
export type Ops = {
	/** Rename the pane's plane. The pane applies it at once, `set_head` confirms. */
	"plane.rename": { title: string };
	/** Set its icon: a stored spelling, "" for none. Applied at once like a rename. */
	"plane.icon": { icon: string };
	/** Remove the plane and everything under it. Panes leave as they turn missing. */
	"plane.delete": Record<string, never>;
	/**
	 * Set the Plane's web flags given (`editable`, `width`).
	 * The pane applies them optimistically and the next `set_head` confirms.
	 */
	"plane.web": { flags: Record<string, boolean | string> };
	"cell.create": {
		cell_id: string;
		/** The Cell it is made from. The server stores that Cell's
		 *  program, or the starter program when no Cell has this name. */
		name: string;
		/** The plane's layout with the new cell in place. The cell is added
		 *  first, then the layout set. An id taken is `Exists` (../plane/create.ts). */
		rows: LayoutRow[];
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
	"plane.key": { key: string };
	/** Drop the plane's key, free for another plane. */
	"plane.remove_key": Record<string, never>;
	/** One cell before or after another of its plane, neither for the end. Not
	 *  sent from here: a web plane's reorder is `layout.set`. Kept as the
	 *  server's, for non-web and headless use. */
	"cell.move": { cell_id: string; before?: string; after?: string };
	/** Ask for the planes a cell can be transferred to: answered once with
	 *  `set_targets` on this pane's node (./transfer.ts). */
	"cell.targets": Record<string, never>;
	/** Ask what the cell is and how it last ran in this pane's run: answered
	 *  once with `set_cell_info` on this pane's node (./cell/info.ts). */
	"cell.info": { cell_id: string };
	/** One cell to another plane, editable and not this one (./transfer.ts):
	 *  before or after a cell there, neither for its end. It leaves this pane
	 *  when the cells ship again. */
	"cell.transfer": { cell_id: string; plane_id: string; before?: string; after?: string };
	/** Run the cell again in this pane's run. With the run over, the whole
	 *  pane runs again. */
	"cell.restart": { cell_id: string };
	/** Run this pane's plane again: its run stopped, a new one made. */
	"plane.restart": Record<string, never>;
	/** The plane's layout, whole: every reorder, strip, column and resize. */
	"layout.set": { rows: LayoutRow[] };
	/** One cell to another plane, then that plane's layout as `rows`, the
	 *  cell in place there. Two commits: a failed set leaves it transferred,
	 *  drawn last there. */
	"layout.transfer": { cell_id: string; plane_id: string; rows: LayoutRow[] };
};

/** What a drop or a key sends: a layout write, or a plain transfer onto a sidebar row. */
export type LayoutOp =
	| { op: "layout.set"; args: Ops["layout.set"] }
	| { op: "layout.transfer"; args: Ops["layout.transfer"] }
	| { op: "cell.transfer"; args: Ops["cell.transfer"] };

/** Send one of the pane's ops. Bound to its node by the pane (../pane/Pane.tsx), threaded into its plane. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;

/** Send one layout op, as a drop or a key decided it. */
export function sendOp(notify: Notify, op: LayoutOp): void {
	(notify as (name: string, args: unknown) => void)(op.op, op.args);
}
