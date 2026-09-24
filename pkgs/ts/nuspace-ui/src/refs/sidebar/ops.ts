// The sidebar op table, browser side. Mirrors
// `nuspace/web/sidebar/interactions.py`.
//
// One ref per op: a notify goes to `<sidebar ref>.ops.<name>` and the payload
// carries that op's arguments and nothing else. There is no `op` key, because
// the path already answered that question, and the server binds one arm per
// path rather than branching on a string.
//
// `Ops` is what keeps the two sides in step: the keys are the op names the
// python ref subscribes to, and each value is exactly the field set the
// matching `nuspace.ops` call reads. Add an interaction on one side and this
// file is where the other side fails to compile.
//
// Every Plane write is here and every Cell write is in ../viewer/ops.ts. That
// is the whole line between the two refs.
//
// ## What is NOT here
//
// Opening a Plane. The sidebar moves the browser's URL, and what the URL now
// names is a fact about what the Viewer has open, so `pages.open` is the
// Viewer's op.

/** Every op the sidebar sends, with its argument shape. */
export type Ops = {
	/**
	 * `group` is the section the + was pressed under and decides what gets
	 * built, which can be more than one Plane. `parent_id` is where the row
	 * sits, which is a different question and not one anything answers yet.
	 */
	"page.create": { page_id: string; parent_id: string; group: string; title: string };
	"page.rename": { page_id: string; title: string };
	/** Takes every Cell on the Plane with it. */
	"page.delete": { page_id: string };
	"page.move": { page_id: string; parent_id: string; index: number };
	/** One parent's children, in the order they should now be in. */
	"page.reorder": { parent_id: string; page_ids: string[] };
};

/** Send one op. Threaded down from `sidebar.tsx` into the rail. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
