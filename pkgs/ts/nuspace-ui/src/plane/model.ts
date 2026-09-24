// What every piece of a plane's behaviour works against.
//
// The plane is one keyboard owner with one editor state, split across a few
// hooks by concern (focus routing, structure, keys, drag, slash, ghosts). They
// all need the same handful of things, so the plane builds this once per
// render and hands it to each. Nothing in here is state of its own: the
// editor state is the store's (./state.ts), the refs are the plane's DOM.

import type * as React from "react";
import type { Notify } from "./ops";
import type { EditorPatch, EditorState } from "./state";
import type { Cell } from "./types";

export type PlaneModel = {
	planeId: string;
	cells: Cell[];
	editor: EditorState;
	/** Patch this pane's editor state. Stable per plane. */
	patch: (p: EditorPatch) => void;
	notify: Notify;
	/** A cell's position in `cells`, -1 when it is not there. */
	index: (id: string) => number;
	/** The plane root, which takes keyboard focus in cell-selection mode. */
	rootRef: React.RefObject<HTMLDivElement | null>;
	/** Every cell's row element, by id, for scrolling and drop targeting. */
	elRefs: React.RefObject<Map<string, HTMLElement>>;
	/** The two ghost inputs, for vertical travel to aim at. `plusGhost` is
	 *  the one a gutter `+` summoned, and is null far more often than not. */
	endGhost: React.RefObject<HTMLInputElement | null>;
	plusGhost: React.RefObject<HTMLInputElement | null>;
};
