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

/** Every op the Pages surface accepts, with its argument shape. */
export type Ops = {
	"page.select": { path: string[] };
	"page.create": { parent_path: string[]; title: string };
	"page.rename": { path: string[]; title: string };
	"page.delete": { path: string[] };
	"block.create": {
		page_path: string[];
		kind: "prose" | "program";
		source: string;
		after: string | null;
	};
	"block.update": { page_path: string[]; block_id: string; source: string };
	"block.delete": { page_path: string[]; block_ids: string[] };
	"block.split": {
		page_path: string[];
		block_id: string;
		head: string;
		tail: string;
		insert: { kind: "prose" | "program"; source: string } | null;
	};
	"block.merge": {
		page_path: string[];
		block_id: string;
		into_id: string;
		source: string;
	};
	"block.reorder": { page_path: string[]; order: string[] };
	"block.restart": { block_id: string };
};

/** Send one op. Threaded down from `pages.tsx` into the rail and the canvas. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
