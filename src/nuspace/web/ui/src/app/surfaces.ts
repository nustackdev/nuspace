// Finding a surface in the tree.
//
// There is no mount envelope to read a page list off any more, and no
// `page.fields` to hunt through. The shell's four surfaces are nodes like any
// other, and what identifies one is its type -- "PagesRef", "AppsRef",
// "LensRef", "ChatRef" -- exactly the way nudle's router finds its pages by
// type rather than by a slot name the shell would have to agree with in a
// second place.
//
// The search is a walk and not a look at the root's children, because where
// nuspace roots its surfaces is the python side's call: they may sit at the
// top or under a shell node, and either way the browser should not have to be
// told. First match in write order wins; there is one of each.

import type { Path, TreeNode } from "@nustackdev/ui-core";
import { pathKey, useTree } from "@nustackdev/ui-kit";
import { useMemo } from "react";

function findOfType(node: TreeNode, type: string, here: Path): Path | null {
	for (const [segment, child] of node.children) {
		const at = [...here, segment];
		if (child.type === type) return at;
		const deeper = findOfType(child, type, at);
		if (deeper) return deeper;
	}
	return null;
}

/**
 * Where the one node of `type` lives, or null.
 *
 * The subscription is on the path as a string, so the shell re-renders when a
 * surface appears or moves and not when anything inside one changes. A path
 * is rebuilt on every walk, so a plain Object.is on the list would say
 * "changed" on every store touch in the space.
 */
export function useTypePath(type: string): Path | null {
	const key = useTree((s) => {
		const found = findOfType(s.root, type, []);
		return found ? pathKey(found) : "";
	});
	return useMemo(() => (key ? (JSON.parse(key) as Path) : null), [key]);
}

/** Whether anything has landed yet. What tells "empty" from "not yet". */
export function useBooted(): boolean {
	return useTree((s) => s.root.children.size > 0);
}
