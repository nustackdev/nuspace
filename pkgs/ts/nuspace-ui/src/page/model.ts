// What every piece of a page's behaviour works against.
//
// The page is one keyboard owner with one editor state, split across a few
// hooks by concern (focus routing, structure, keys, drag, slash, ghosts). They
// all need the same handful of things, so the page builds this once per
// render and hands it to each. Nothing in here is state of its own: the
// editor state is the store's (./state.ts), the refs are the page's DOM.

import type * as React from "react";
import type { Notify } from "./ops";
import type { EditorPatch, EditorState } from "./state";
import type { Block } from "./types";

export type PageModel = {
	pageId: string;
	blocks: Block[];
	editor: EditorState;
	/** Patch this pane's editor state. Stable per page. */
	patch: (p: EditorPatch) => void;
	notify: Notify;
	/** A block's position in `blocks`, -1 when it is not there. */
	index: (id: string) => number;
	/** The page root, which takes keyboard focus in block-selection mode. */
	rootRef: React.RefObject<HTMLDivElement | null>;
	/** Every block's row element, by id, for scrolling and drop targeting. */
	elRefs: React.RefObject<Map<string, HTMLElement>>;
	/** The two ghost inputs, for vertical travel to aim at. `plusGhost` is
	 *  the one a gutter `+` summoned, and is null far more often than not. */
	endGhost: React.RefObject<HTMLInputElement | null>;
	plusGhost: React.RefObject<HTMLInputElement | null>;
};
