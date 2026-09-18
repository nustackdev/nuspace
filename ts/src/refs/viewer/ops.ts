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
// Every Cell write is here and every Plane write is in ../sidebar/ops.ts. That
// is the whole line between the two refs, and `page.select` is on this side of
// it because what the URL names is a fact about what the Viewer has open.
//
// ## Ids are minted here
//
// `section.create` carries the id of the Cell being made. That makes a create
// a pure function of its event on the server, and lets the caret aim at a
// known id rather than guess at one from a position. Use `mintId` from
// ../../app/ids; do not invent a second scheme.
//
// ## What is NOT here
//
// Typing in a text block. A text block's ref is wired straight to kv by the
// block's own program, so a keystroke is a notify on that ref and never
// touches the Viewer.
//
// Split and merge. Both are compositions of the ops below -- a split is an
// update plus a create at the next index, a merge is an update plus a delete
// -- and the canvas composes them rather than the server growing a verb for
// each editor gesture. The two halves are independent writes to different
// sections, so it does not matter which arm runs first.

import type { BlockTpl } from "./types";

/** Every op the Viewer sends, with its argument shape. */
export type Ops = {
	/** No kv write: the answer is a `set_page` plus a `set_status`. */
	"page.select": { page_id: string };
	"section.create": {
		page_id: string;
		section_id: string;
		name: string;
		tpl: BlockTpl;
		/** The Nu program. For a templated tpl this is the shipped starter,
		 *  which rides the chain onto the ref as a declared prop -- never
		 *  written here. */
		source: string;
		index: number;
	};
	/** Replaces the stored program. Nothing else about the section moves. */
	"section.update": { page_id: string; section_id: string; source: string };
	"section.delete": { page_id: string; section_id: string };
	/** Keeps the section's id, and so its kv namespace, on the new Plane. */
	"section.move": {
		page_id: string;
		section_id: string;
		to_page_id: string;
		index: number;
	};
	"section.reorder": { page_id: string; section_ids: string[] };
};

/** Send one op. Threaded down from `viewer.tsx` into the canvas. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
