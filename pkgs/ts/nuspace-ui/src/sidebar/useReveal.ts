// Expansion is *revealed-then-sticky*: navigating to a Plane opens its whole
// ancestor chain, so a deep link, a back button, or a rename that reships the
// tree never leaves the open Plane buried in a folded branch. After that the fold state is yours until you navigate
// again. The reveal runs off the selection key rather than out of the click
// handler on purpose - arriving by URL has to behave exactly like arriving by
// click.
//
// The tree is lazy: it holds only the branches this tab has open, so a plane
// under a closed folder has no row to climb from when you arrive. The server
// fills that in: when a pane opens on a plane, it opens every branch above it
// for this tab and the tree reships with the plane's row in it. So an arrival
// waits for its plane's row to land, then opens the chain once. Rows that
// land later for a plane already revealed never reopen what you folded.

import { useCallback, useEffect, useRef } from "react";
import { ancestorsOf, type PlaneTree } from "./types";

/**
 * `reveal(key)` opens a row if it is not open already, and never closes one.
 * Also runs the arrival reveal: every ancestor of every open Plane, whenever
 * the route or the focused pane changes, once that Plane's row is in the tree.
 */
export function useReveal({
	tree,
	root,
	routes,
	selKey,
	expanded,
	onToggle,
}: {
	tree: PlaneTree;
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

	// The open planes still to reveal on this arrival. Each leaves once its
	// row is in the tree and its chain is open, so later reships leave the
	// fold state alone.
	const waiting = useRef(new Set<string>());

	// biome-ignore lint/correctness/useExhaustiveDependencies: a new arrival is a new route list or a new focus, `routes` itself is read through its key
	useEffect(() => {
		waiting.current = new Set(routes);
	}, [routesKey, selKey]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: reruns on an arrival too, so a plane whose row is already there reveals at once
	useEffect(() => {
		if (!root) return;
		for (const id of [...waiting.current]) {
			if (!tree[id]) continue;
			waiting.current.delete(id);
			for (const row of ancestorsOf(tree, id)) if (row.id !== root) reveal(row.id);
		}
	}, [tree, root, routesKey, selKey, reveal]);

	return reveal;
}
