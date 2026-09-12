// The Pages op table, browser side. Mirrors `nuspace/web/refs/pages.py`.
//
// One ref per op: a notify goes to `<pages ref>.ops.<name>` and the payload
// carries that op's arguments and nothing else. There is no `op` key, because
// the path already answered that question, and the server binds one arm per
// path rather than branching on a string.
//
// `Ops` is what keeps the two sides in step: the keys are the op names the
// python ref subscribes to, and each value is exactly the field set the
// matching `nuspace.pages.ops` call reads. Add an interaction on one side and
// this file is where the other side fails to compile.
//
// ## Ids are minted here
//
// `page.create` and `section.create` carry the id of the thing being made.
// That makes a create a pure function of its event on the server, and lets a
// click route to what it just made without a round trip to learn its name.
// Use `mintId` from ./types; do not invent a second scheme.
//
// ## What is NOT here
//
// Typing in a text block. A text block's ref is wired straight to kv by the
// block's own program, so a keystroke is a notify on that ref and never
// touches the page document.
//
// Split and merge. Both are compositions of the ops below -- a split is an
// update plus a create at the next index, a merge is an update plus a delete
// -- and the canvas composes them rather than the server growing a verb for
// each editor gesture. The two halves are independent writes to different
// sections, so it does not matter which arm runs first.
//
// Restart. There is no liveness pillar to restart into yet.

import type { BlockTpl } from "./types";

/** Every op the Pages surface accepts, with its argument shape. */
export type Ops = {
	/** No kv write: the answer is a `set_page` plus a `set_status`. */
	"page.select": { page_id: string };
	"page.create": { page_id: string; parent_id: string; title: string };
	"page.rename": { page_id: string; title: string };
	/** Takes the whole subtree with it. */
	"page.delete": { page_id: string };
	"page.move": { page_id: string; parent_id: string; index: number };
	/** One parent's children, in the order they should now be in. */
	"page.reorder": { parent_id: string; page_ids: string[] };
	"section.create": {
		page_id: string;
		section_id: string;
		name: string;
		tpl: BlockTpl;
		/** The Nu program. For a templated tpl this is the shipped starter,
		 *  which arrives in the ref's mount props -- never written here. */
		source: string;
		index: number;
	};
	/** Replaces the stored program. Nothing else about the section moves. */
	"section.update": { page_id: string; section_id: string; source: string };
	"section.delete": { page_id: string; section_id: string };
	/** Keeps the section's id, and so its kv namespace, on the new page. */
	"section.move": {
		page_id: string;
		section_id: string;
		to_page_id: string;
		index: number;
	};
	"section.reorder": { page_id: string; section_ids: string[] };
};

/** Send one op. Threaded down from `pages.tsx` into the rail and the canvas. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
