// The sidebar op table, browser side. Mirrors
// `nuspace/devices/web/sidebar/interactions.py`.
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
// Opening a Plane. The sidebar moves the desk through the router, and which
// panes are open is a fact about what the Viewer has open, so `planes.open` is
// the Viewer's op.

/** Every op the sidebar sends, with its argument shape. */
export type Ops = {
	/**
	 * `plane_id` is minted here. `parent_id` is a Plane id, or `ROOT_ID` for
	 * the top. `spec` names the registered Plane to seed it from, "" for the
	 * empty one, and `title` is what it is called.
	 */
	"plane.create": { plane_id: string; parent_id: string; spec: string; title: string };
	"plane.rename": { plane_id: string; title: string };
	/** Takes every Cell on the Plane with it, and every Plane below it. */
	"plane.delete": { plane_id: string };
	/**
	 * Reparent and reorder in one: before or after a sibling under
	 * `parent_id`, neither for the end. The server refuses a move into the
	 * Plane's own subtree.
	 */
	"plane.move": { plane_id: string; parent_id: string } & Anchor;
	/** `icon` is a stored spelling (../icon/parse.ts), "" for the default. */
	"plane.icon": { plane_id: string; icon: string };
	/**
	 * Pin before or after a pin, neither for the end. The Plane stays in the
	 * tree. Already pinned, the server refuses it: move it with `pin_move`.
	 */
	"plane.pin": { plane_id: string } & Anchor;
	"plane.unpin": { plane_id: string };
	/** Move a pinned Plane, placed as in `plane.pin`. */
	"plane.pin_move": { plane_id: string } & Anchor;
	/** The rail opened a branch: the server ships its children. The tree is lazy. */
	"plane.expand": { plane_id: string };
	/** The rail closed a branch. */
	"plane.collapse": { plane_id: string };
};

/** Where a placed thing goes: before or after a sibling, neither for the end. */
export type Anchor = { before?: string; after?: string };

/** The anchor that puts an item at `index` of `others` (the item itself left out). */
export function anchorAt(others: readonly string[], index: number): Anchor {
	return index >= 0 && index < others.length ? { before: others[index] } : {};
}

/** Send one op. Threaded down from `Sidebar.tsx` into the rail. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
