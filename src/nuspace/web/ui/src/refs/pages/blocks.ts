// ============================== THE SEAM ==================================
//
// Where a block's ui lives in the tree, and it is the ONE place that knows.
//
// ## What this replaces
//
// A block used to carry a `fields` list: the server statically walked the
// section's term looking for refs whose segment was a literal string with the
// section prefix on it, wrote what it found to kv as json, and the browser
// read it back and built a slice per entry. Anything computed was silently
// skipped, so a dynamic ref never appeared at all.
//
// None of that exists now. A section's refs are re-rooted under the page and
// the section they belong to, and the first write to one autovivifies it. So
// a block's ui is simply the subtree at the block's own address, and
// rendering it is `NodeView` on that path -- the same call the shell makes
// for a surface.
//
// ## What is NOT settled, and why this file exists
//
// The exact address. The python side of task-145 (scope items 9 and 11 -- ui
// shapes for sections, entry point gains page and section) decides what the
// chain under a PagesRef node looks like, and it has not landed yet. Every
// function below encodes the assumption, and nothing else in the tree does:
//
//     <the PagesRef node> / sections / <section id> / ...the section's refs
//
// It is the assumption the old naming scheme already made -- `sections.<id>`
// is the prefix the copy button in a program block's bar hands you, and that
// string is mirrored here rather than spelled a second time. If python roots
// them somewhere else, this file is the diff.
//
// ==========================================================================

import type { Path, TreeNode } from "@nustackdev/ui-core";
import { nodeAt, useChildren } from "@nustackdev/ui-kit";

/** The segment every section hangs under. */
export const SECTIONS = "sections";

/** Where one block's refs live, relative to the PagesRef node. */
export function blockUiPath(pagesPath: Path, blockId: string): Path {
	return [...pagesPath, SECTIONS, blockId];
}

/**
 * The kv prefix a block's own program writes under, as text.
 *
 * Shown by the copy button in a program block's bar, so somebody writing the
 * next block can reach into this one. A string and not a path because it is
 * pasted into python source, where it is a ref chain spelled by hand.
 */
export function blockPrefix(blockId: string): string {
	return `${SECTIONS}.${blockId}`;
}

/** Whether a block mounted any ui at all. False means it runs headless. */
export function useBlockHasUi(uiPath: Path): boolean {
	return useChildren(uiPath).length > 0;
}

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
 * The markdown a text block currently holds, read off its own ProseRef.
 *
 * The page payload does not carry it: a text block's content lives on the ref
 * its program mounted, which is where the browser already has it and where a
 * keystroke lands without reshipping the page. A neighbour that needs it --
 * merge-up joining two blocks -- reads it from there. Found by type, so
 * nothing here depends on what the template calls its slot.
 *
 * Outside a render on purpose: this answers "what is in the block above" at
 * the moment of a backspace, and nobody subscribes to it.
 */
export function blockText(pagesPath: Path, blockId: string): string {
	const root = blockUiPath(pagesPath, blockId);
	const node = nodeAt(root);
	if (!node) return "";
	if (node.type === "ProseRef") return String(node.props.value ?? "");
	const found = findOfType(node, "ProseRef", root);
	if (!found) return "";
	const prose = nodeAt(found);
	return String(prose?.props.value ?? "");
}
