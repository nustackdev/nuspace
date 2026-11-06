// The plane's one surface: what a sugar set acts through, and what the pane
// holds.
//
// The plane core is kind-blind. It knows cells in order, the classes each
// one keeps, and the interaction state it owns in `local` (./state.ts):
// selection, focus requests, the input lines, the menu. Everything a layer
// above it may do to a plane is here and nowhere else, so a sugar never
// reaches past it into the core's hooks, and the core never learns what a
// sugar does with it.
//
// Every write to structure is an op (./ops.ts), with the id minted here, so
// the caret aims at a known cell rather than one guessed from a position.
// Focus and selection are local state only: a focus request parks until the
// cell can take it (./focus/useFocusRouting.ts).
//
// `PlaneHandle` is the other direction: what the pane above hands down into
// the plane, one object instead of a ref per gesture. The title reports its
// intents through it, and a press anywhere in the pane can start a box
// selection over the cells.
//
// `PlaneModel` is what the core's own hooks share. Not part of the surface:
// sugar never sees it.

import type { DocumentHandle, FocusAt } from "@nustackdev/ui-kit";
import type * as React from "react";
import type { TitleIntent } from "./intents";
import type { Notify } from "./ops";
import type { EditorPatch, EditorState } from "./state";
import type { Cell } from "./types";

/** Where a new cell goes: after that cell, at the top when null. */
export type Place = { after: string | null };

/**
 * Where the caret goes. A cell's document (or its open source) at an edge,
 * under a screen x on its first or last line, or where its own caret already
 * is ("kept"); or the title above the plane.
 */
export type FocusTarget = { cell: string; at: FocusAt } | { title: "start" | "end" };

/**
 * What the caret meets leaving a cell one way, as the plane is now. Kind
 * blind: which classes the cell there keeps is the asker's to look up.
 */
export type Beside = {
	/** The next cell that way, past any being deleted. Null when there is none. */
	cell: string | null;
	/** An input line sits in between: the summoned one, or the end line under the last cell. */
	line: boolean;
	/** Up from the top cell, with nothing in between: the title, where the host has one. */
	title: boolean;
};

/** A focus request for a cell being created, and what it carries. */
export type FocusRequest = {
	at: FocusAt;
	/** Typed in once the document has the caret, as the person's own keys. */
	text?: string;
	/** Appended to the document before it is focused. */
	markdown?: string;
	/** Hears the request consumed, with the document that took it. */
	landed?: (doc: DocumentHandle) => void;
};

export interface PlaneApi {
	// -- read
	/** The cells in order, each with the classes it keeps. Live as of this call's render. */
	readonly cells: readonly { id: string; classes: readonly string[] }[];
	/** A cell's position, -1 when it is not there. */
	index(id: string): number;
	/** The cell's document, from the kit registry. Null while it has none. */
	document(id: string): DocumentHandle | null;
	/** The installed spec that is `cls`'s default, null when none is. */
	defaultSpec(cls: string): string | null;
	/** What is next to cell `id` that way: a cell, an input line, the title. */
	beside(id: string, dir: "up" | "down"): Beside;

	// -- structure: every write is an op
	/**
	 * A cell made from `spec` at `at`. Returns its minted id. With `focus`,
	 * the request (and what it carries) waits for its document; without, a
	 * cell from a spec is landed on selected, an empty program opens its source.
	 */
	create(at: Place, spec: string, focus?: FocusRequest): string;
	/**
	 * The one delete path. The cells go (hidden until the server drops them)
	 * and the caret goes to `focus`. Left out, the cell above the first one
	 * is selected; null leaves focus and selection where they are.
	 */
	remove(ids: string[], focus?: FocusTarget | null): void;
	/** The whole new order of the plane's cells. */
	reorder(ids: string[]): void;

	// -- focus and selection: local state only
	/** A focus request, taken up when the cell is ready. */
	focus(target: FocusTarget): void;
	/** Cell selection: these cells, extended from `anchor` (the first by default). */
	select(ids: string[], anchor?: string): void;

	// -- input line and menu
	/** An input line after `after` (null: the top), the caret in it. Escape goes to `home`. */
	openInput(after: string | null, home?: FocusTarget): void;
	/** The menu in that cell's place: a pick replaces it, Escape brings it back. */
	standIn(id: string): void;
}

/** What the pane holds of the plane under it. */
export interface PlaneHandle {
	/** The title above reports an intent. True when the plane acted on it. */
	title(intent: TitleIntent): boolean;
	/** A press landed in the pane: where a box selection over the cells starts. */
	press(e: React.PointerEvent): void;
}

/**
 * What every core hook works against, built once per render by the plane.
 * Nothing in here is state of its own: the editor state is the store's
 * (./state.ts), the refs are the plane's DOM.
 */
export type PlaneModel = {
	planeId: string;
	cells: Cell[];
	editor: EditorState;
	/** Patch this pane's editor state. Stable per plane. */
	patch: (p: EditorPatch) => void;
	/** This pane's editor state as it is now, for a handler that just patched. */
	read: () => EditorState;
	notify: Notify;
	/** A cell's position in `cells`, -1 when it is not there. */
	index: (id: string) => number;
	/** The cell's document, from the kit registry. */
	document: (id: string) => DocumentHandle | null;
	/** The plane root, which takes keyboard focus in cell-selection mode. */
	rootRef: React.RefObject<HTMLDivElement | null>;
	/** Every cell's row element, by id, for scrolling and drop targeting. */
	elRefs: React.RefObject<Map<string, HTMLElement>>;
	/** The two input lines, for vertical travel to aim at. `plusGhost` is
	 *  the summoned one, and is null far more often than not. */
	endGhost: React.RefObject<HTMLInputElement | null>;
	plusGhost: React.RefObject<HTMLInputElement | null>;
};
