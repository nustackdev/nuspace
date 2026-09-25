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
// Every write to the tree is here, and every Cell write is in ../plane/ops.ts.
//
// ## What is NOT here
//
// Opening a Plane. The sidebar moves the browser's URL, and what the URL now
// names is a fact about what the Viewer has open, so `planes.open` is the
// Viewer's op.

/** Every op the sidebar sends, with its argument shape. */
export type Ops = {
	/**
	 * `plane_id` is minted here. `parent_id` is a Plane id, or `ROOT_ID` for
	 * the top. `made_by` names the registered Plane to seed it from, and
	 * `title` is what it is called.
	 */
	"plane.create": { plane_id: string; parent_id: string; made_by: string; title: string };
	"plane.rename": { plane_id: string; title: string };
	/** Takes every Cell on the Plane with it, and every Plane below it. */
	"plane.delete": { plane_id: string };
	/**
	 * Reparent and reorder in one. `index` is the position among the
	 * sidebar's children of `parent_id`, counted without the moved Plane. The
	 * server refuses a move into the Plane's own subtree.
	 */
	"plane.move": { plane_id: string; parent_id: string; index: number };
	/** `icon` is a stored spelling (../icon/parse.ts), "" for the default. */
	"plane.icon": { plane_id: string; icon: string };
};

/** Send one op. Threaded down from `Sidebar.tsx` into the rail. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
