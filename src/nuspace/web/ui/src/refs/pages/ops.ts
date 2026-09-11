// The Pages op table, browser side. Mirrors `refs/pages/ops.py`.
//
// One ref per op: a notify goes to `<pages ref>.ops.<name>` and the payload
// carries that op's arguments and nothing else. There is no `op` key, because
// the path already answered that question, and the server subscribes one
// handler per path rather than branching on a string.
//
// Server bodies take named arguments, so a typo here is a TypeError over
// there rather than a silently empty string. `Ops` is what keeps the two
// sides in step: add an op on one side and this file is where the other side
// fails to compile.
//
// Typing in a text block does NOT appear here. A text block's ref is wired
// straight to kv by the block's own program, so a keystroke is a notify on
// that ref and never touches the page document. What is left in `block.*` is
// structure: create, delete, reorder, and the two ops that move text BETWEEN
// blocks (split, merge) and so cannot belong to either one's ref.

import type { BlockTpl } from "./types";

/** Every op the Pages surface accepts, with its argument shape. */
export type Ops = {
	"page.select": { path: string[] };
	"page.create": { parent_path: string[]; title: string };
	"page.rename": { path: string[]; title: string };
	"page.delete": { path: string[] };
	"block.create": {
		page_path: string[];
		tpl: BlockTpl;
		/** Whatever the tpl takes: python source for a program, markdown for
		 *  a text block. Empty means "give me the tpl's starter". */
		content: string;
		after: string | null;
	};
	"block.update": { page_path: string[]; block_id: string; content: string };
	"block.delete": { page_path: string[]; block_ids: string[] };
	"block.split": {
		page_path: string[];
		block_id: string;
		head: string;
		tail: string;
		insert: { tpl: BlockTpl; content: string } | null;
	};
	"block.merge": {
		page_path: string[];
		block_id: string;
		into_id: string;
		content: string;
	};
	"block.reorder": { page_path: string[]; order: string[] };
	"block.restart": { block_id: string };
};

/** Send one op. Threaded down from `pages.tsx` into the rail and the canvas. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
