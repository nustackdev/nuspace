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
// ## The address, in one place
//
//     <the ViewerRef node> / sections / <section id> / ...the section's refs
//
// `nuspace/web/utils.py` is the other half of it and nothing else on either
// side spells it out. Moving it here without moving it there is the one way to
// break drawing.
//
// ==========================================================================

import type { Path, TreeNode } from "@nustackdev/ui-core";
import { nodeAt, useChildren } from "@nustackdev/ui-kit";

/** The segment every section hangs under. */
export const SECTIONS = "sections";

/** Where one block's refs live, relative to the ViewerRef node. */
export function blockUiPath(viewerPath: Path, blockId: string): Path {
	return [...viewerPath, SECTIONS, blockId];
}

/**
 * The kv prefix a block's own program writes under, as text.
 *
 * A string and not a path because this is the spelling that goes into python
 * source, where it is a ref chain typed by hand: somebody writing the next
 * block reaches into this one through it. The gutter's copy button hands out
 * the bare id instead -- that is what every op on the wire is keyed by -- so
 * this is currently the assumption's one written form and nothing else.
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
export function blockText(viewerPath: Path, blockId: string): string {
	const root = blockUiPath(viewerPath, blockId);
	const node = nodeAt(root);
	if (!node) return "";
	if (node.type === "ProseRef") return String(node.props.value ?? "");
	const found = findOfType(node, "ProseRef", root);
	if (!found) return "";
	const prose = nodeAt(found);
	return String(prose?.props.value ?? "");
}
