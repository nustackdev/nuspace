// Expansion is *revealed-then-sticky*: every section opens on arrival, and
// navigating to a Plane opens its whole ancestor chain, so a deep link, a back
// button, or a rename that reships the tree never leaves the open Plane buried
// in a folded branch. After that the fold state is yours until you navigate
// again. The reveal runs off the selection key rather than out of the click
// handler on purpose - arriving by URL has to behave exactly like arriving by
// click.

import { useCallback, useEffect, useRef } from "react";
import { ancestorsOf, childrenOf, type PageTree } from "./types";

/**
 * `reveal(key)` opens a row if it is not open already, and never closes one.
 * Also runs the arrival reveal: every section, and every ancestor of every
 * open Plane, whenever the route or the focused pane changes.
 */
export function useReveal({
	tree,
	root,
	routes,
	selKey,
	expanded,
	onToggle,
}: {
	tree: PageTree;
	root: string;
	routes: string[];
	selKey: string;
	expanded: Set<string>;
	onToggle: (key: string) => void;
}): (key: string) => void {
	// `onToggle` flips a key, so "reveal" is "flip it if it is not already on".
	//
	// Two refs, both load-bearing.
	//
	// `expandedRef` is why the reveal below can run on a *selection* change
	// rather than on every fold: read the set through a ref and collapsing the
	// branch you are standing in does not instantly re-open it.
	//
	// `pending` is why revealing a whole ancestor chain works at all. The store
	// updates synchronously but the prop only lands on the next render, so a
	// second `reveal` in the same pass still sees the old set and flips the key
	// straight back off. That is the whole reason a deep link used to arrive
	// with the tree folded shut.
	const expandedRef = useRef(expanded);
	const pending = useRef(new Set<string>());
	if (expandedRef.current !== expanded) {
		expandedRef.current = expanded;
		pending.current.clear();
	}

	const reveal = useCallback(
		(key: string) => {
			if (expandedRef.current.has(key) || pending.current.has(key)) return;
			pending.current.add(key);
			onToggle(key);
		},
		[onToggle],
	);

	const routesKey = routes.join("+");

	// A rail whose sections all start folded is a rail that looks empty.
	// biome-ignore lint/correctness/useExhaustiveDependencies: the walk reads the tree, but rerunning on every reship would fight the fold state; `root` flipping from "" is what carries the first tree in
	useEffect(() => {
		if (!root) return;
		for (const section of childrenOf(tree, root)) reveal(section.id);
		for (const id of routes)
			for (const row of ancestorsOf(tree, id)) if (row.id !== root) reveal(row.id);
	}, [routesKey, selKey, root, reveal]);

	return reveal;
}
