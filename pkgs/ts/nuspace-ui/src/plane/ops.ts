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
// A web plane draws its cells from its layout (./types.ts `LayoutItem`), and
// every reorder on it is a `layout.*` event, never `cell.move`: what the
// keyboard moves (`orderMoves`) and every drop (./layout/model.ts `dropOp`).
// A spot for one cell is before or after an item, neither for the end, or
// into a strip's column at an index counted with the cell taken out.

import type { StoredItem } from "./types";

/** Where one cell goes in a layout: beside an item (neither for the end), or into a strip's column. */
export type CellSpot =
	| { before?: string; after?: string }
	| { into: string; column: number; index: number };

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
	"plane.key": { key: string };
	/** Drop the plane's key, free for another plane. */
	"plane.remove_key": Record<string, never>;
	/** One cell before or after another of its plane, neither for the end. Not
	 *  sent from here: a web plane's reorder is `layout.move`. Kept as the
	 *  server's, for non-web and headless use. */
	"cell.move": { cell_id: string; before?: string; after?: string };
	/** Ask for the planes a cell can be transferred to: answered once with
	 *  `set_targets` on this pane's node (./transfer.ts). */
	"cell.targets": Record<string, never>;
	/** One cell to another plane, editable and not this one (./transfer.ts):
	 *  before or after a cell there, neither for its end. It leaves this pane
	 *  when the cells ship again. */
	"cell.transfer": { cell_id: string; plane_id: string; before?: string; after?: string };
	/** Run the cell again in this pane's run. With the run over, the whole
	 *  pane runs again. */
	"cell.restart": { cell_id: string };
	/** Run this pane's plane again: its run stopped, a new one made. */
	"plane.restart": Record<string, never>;
	/** One item replaced whole, in its place: a strip made, regrouped or resized.
	 *  The cells it names are taken out of every other item. */
	"layout.set": { item_id: string; item: StoredItem };
	/** One item before or after another, neither for the end: the web plane's reorder. */
	"layout.move": { item_id: string; before?: string; after?: string };
	/** One cell of this plane to a spot in its layout, out of the item that held it. */
	"layout.place": { cell_id: string } & CellSpot;
	/** One cell to another plane, then to a spot in its layout. Two commits: a
	 *  failed place leaves it transferred, drawn last there. */
	"layout.transfer": { cell_id: string; plane_id: string } & CellSpot;
};

/** The layout events, by name. */
export type LayoutOpName = Extract<keyof Ops, `layout.${string}`>;

/** One layout event and its payload, as a drop or a key decides it. */
export type LayoutOp = { [K in LayoutOpName]: { op: K; args: Ops[K] } }[LayoutOpName];

/** Send one of the pane's ops. Bound to its node by the pane (../pane/Pane.tsx), threaded into its plane. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;

/** One id placed before or after another: what one `layout.move` (or `cell.move`) carries. */
export type OrderMove = { id: string; before?: string; after?: string };

/**
 * The moves that turn `current` into `next`, one move each: walk `next` and
 * put every id out of place after the one before it. A block moved as one
 * costs a move per id in it.
 */
export function orderMoves(current: readonly string[], next: readonly string[]): OrderMove[] {
	const now = current.filter((id) => next.includes(id));
	const out: OrderMove[] = [];
	next.forEach((id, i) => {
		if (now[i] === id) return;
		const from = now.indexOf(id);
		if (from >= 0) now.splice(from, 1);
		now.splice(i, 0, id);
		out.push(i === 0 ? { id, before: now[1] } : { id, after: next[i - 1] });
	});
	return out;
}

/** Send one layout event, as a drop or a key decided it. */
export function sendOp(notify: Notify, op: LayoutOp): void {
	(notify as (name: string, args: unknown) => void)(op.op, op.args);
}
