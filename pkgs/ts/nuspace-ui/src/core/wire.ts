// Outbound ops, and the one place a nuspace op path is spelled.
//
// Every nuspace surface talks back the same way: one ref per op. A notify
// goes to `<the ref>.ops.<name>` and the payload carries that op's arguments
// and nothing else. There is no `op` key in the payload, because the path
// already answered that question, and the server binds one arm per path
// rather than branching on a string.
//
// What changed with the tree: a ref address is a list of segments, not a
// dot-joined string. So the op path is built by appending, and the op name
// stays ONE segment even though it has a dot in it -- "planes.open" is a
// name, not a two-level path, and a segment may hold any character. That is
// the whole reason `Path` is a list end to end.

import { OPS, type Path } from "@nustackdev/ui-core";
import { tree } from "@nustackdev/ui-kit";

/** Where one op on `path` lives. The single spelling of the op path. */
export function opRef(path: Path, op: string): Path {
	return [...path, "ops", op];
}

/**
 * Send one of a ref's ops. `O` is the surface's op table, so the op name and
 * its argument shape are checked against each other at the call site -- add
 * an interaction on the python side and this is where the browser fails to
 * compile.
 *
 * Not a hook: handlers deep in a surface call it without prop-drilling and it
 * never participates in a render. The store is a module singleton, so there
 * is nothing to subscribe to.
 */
export function notifyOp<O, K extends keyof O & string>(path: Path, op: K, args: O[K]): void {
	tree.getState().send({ op: OPS.notify, ref: opRef(path, op), payload: args });
}
