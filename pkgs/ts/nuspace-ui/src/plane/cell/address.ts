// ============================== THE SEAM ==================================
//
// Where a cell's ui lives in the tree, and it is the ONE place that knows.
//
// ## What this replaces
//
// A cell used to carry a `fields` list: the server statically walked the
// cell's term looking for refs whose segment was a literal string with the
// cell prefix on it, wrote what it found to kv as json, and the browser
// read it back and built a slice per entry. Anything computed was silently
// skipped, so a dynamic ref never appeared at all.
//
// None of that exists now. A cell's refs are re-rooted under the plane and
// the cell they belong to, and the first write to one autovivifies it. So
// a cell's ui is simply the subtree at the cell's own address, and
// rendering it is `NodeView` on that path -- the same call the shell makes
// for a surface.
//
// ## The address, in one place
//
//     <the ViewerRef node> / cells / <cell id> / ...the cell's refs
//
// `nuspace/web/utils.py` is the other half of it and nothing else on either
// side spells it out. Moving it here without moving it there is the one way to
// break drawing.
//
// ==========================================================================

import type { Path } from "@nustackdev/ui-core";
import { useChildren } from "@nustackdev/ui-kit";

/** The segment every cell hangs under. */
export const CELLS = "cells";

/** Where one cell's refs live, relative to the ViewerRef node. */
export function cellUiPath(viewerPath: Path, cellId: string): Path {
	return [...viewerPath, CELLS, cellId];
}

/**
 * The kv prefix a cell's own program writes under, as text.
 *
 * A string and not a path because this is the spelling that goes into python
 * source, where it is a ref chain typed by hand: somebody writing the next
 * cell reaches into this one through it. The gutter's copy button hands out
 * the bare id instead -- that is what every op on the wire is keyed by -- so
 * this is currently the assumption's one written form and nothing else.
 */
export function cellPrefix(cellId: string): string {
	return `${CELLS}.${cellId}`;
}

/** Whether a cell mounted any ui at all. False means it runs headless. */
export function useCellHasUi(uiPath: Path): boolean {
	return useChildren(uiPath).length > 0;
}
