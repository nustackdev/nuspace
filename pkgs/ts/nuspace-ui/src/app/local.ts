// Browser-owned state, parked on the node it belongs to.
//
// A slice used to be an open object, so a surface hung whatever it wanted off
// it: caret intent, block selection, the slash menu, a drag, a draft. A node
// is not open -- it is a type, a bag of props and its children -- so all of
// that lives in one reserved prop, `local`.
//
// One prop and not many, for two reasons. The server merges an inbound write
// straight into props, so a flat spelling would put `selected` next to
// whatever the wire calls its fields and the first collision would be silent.
// And a single key is one `setProps` per edit, which is one immer copy of one
// node.
//
// Nothing sends this anywhere. `setProps` is local by construction -- it
// touches the store and never the socket -- which is exactly the rule the ui
// notes state: interaction state that no other Nu code reads does not go near
// python.

import { getNode, type Path } from "@nustackdev/ui-core";
import { nodeAt, tree, useTree } from "@nustackdev/ui-kit";

/** The reserved prop. Never written by the wire, never read by it. */
export const LOCAL = "local";

function read<T>(path: Path, empty: T): T {
	return (nodeAt(path)?.props[LOCAL] as T | undefined) ?? empty;
}

/** The whole local bag. Re-renders on any change to it. */
export function useLocal<T>(path: Path, empty: T): T {
	return useTree((s) => (getNode(s.root, path)?.props[LOCAL] as T | undefined) ?? empty);
}

/**
 * One slot out of the local bag.
 *
 * Narrow on purpose: a keystroke in one block moves `focus` and nothing else,
 * and a component watching `collapsed` should not hear about it. Pick a
 * primitive where you can -- the comparison is Object.is, so a selector that
 * builds a fresh array re-renders every time regardless.
 */
export function useLocalSlot<T, S>(path: Path, empty: T, pick: (local: T) => S): S {
	return useTree((s) => pick((getNode(s.root, path)?.props[LOCAL] as T | undefined) ?? empty));
}

/** Merge into the local bag. A function form sees what is there now. */
export function patchLocal<T>(
	path: Path,
	empty: T,
	patch: Partial<T> | ((local: T) => Partial<T>),
): void {
	if (!nodeAt(path)) return;
	const current = read(path, empty);
	const next = typeof patch === "function" ? (patch as (l: T) => Partial<T>)(current) : patch;
	tree.getState().setProps(path, { [LOCAL]: { ...current, ...next } });
}

/**
 * The local bag inside a `write` handler's own props draft.
 *
 * A handler already holds the props it is about to merge, and a surface that
 * re-ships its content has to prune local state naming things that are gone
 * in the same move. Going through `patchLocal` there would be a second write
 * to the same node for no reason.
 */
export function localOf<T>(props: Record<string, unknown>, empty: T): T {
	return (props[LOCAL] as T | undefined) ?? empty;
}
