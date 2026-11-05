// The text sugar: a closed list of shortcuts for writing, on top of a plane
// that works without any of them.
//
// The core is a plane of cells, an input line, and `/` there to pick the
// cell to insert (../Ghost.tsx, ../useSlash.ts). Humans mostly write text,
// so a few gestures lean that way. These, and nothing else:
//
//   R1  the input line: any key but `/`, Enter included, starts a text cell
//       holding what was typed (./Draft.tsx, wired in ../useGhosts.ts)
//   R2  Backspace in a blank text cell deletes it, the caret going to the
//       end of the cell above, or of the title for the top one
//   R5  Enter in the title starts an empty text cell at the top. Its way
//       back is R2.
//   R6  `/` in a blank text cell opens the cell menu in its place, and the
//       pick replaces it. Put away, the cell comes back as it was.
//   R7  Cmd/Ctrl+Enter in a text cell opens an input line below it, Escape
//       there bringing the caret back. In a table it is the table's.
//   R8  the arrows slide between neighbouring text cells: Up on the first
//       line or Left at the start lands at the end of the text cell above,
//       Down on the last line or Right at the end at the start of the one
//       below. The title counts as the line above the top cell, both ways.
//       Anything else in the way, the arrows stay the editor's.
//   R9  a text selection dragged out of its cell becomes a cell selection,
//       from that cell to the one under the pointer (../useBoxSelect.ts)
//   R10 the same from the keyboard: Shift+arrow with the selection's end at
//       the text's edge selects this cell and the next one that way, any
//       kind, and Shift+arrow goes on extending as cell selection does
//
// Two rules hold the list: each one has its way back, and none reads the
// text's markdown. Blank is the only question asked of a cell (./surface.ts).
// Merging and splitting cells are left out for now, and so is joining into
// the title or splitting it.
//
// A cell is a text cell when its `made_by` is TEXT and that Cell is
// registered. Its keys are caught on the cell's row in the capture phase,
// before the editor inside sees them: the editor marks Enter and Backspace
// handled whatever it does with them, so it cannot be asked first. With no
// text Cell, none of it happens.

import { formatShortcut } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useCallback } from "react";
import type { PlaneModel } from "../model";
import type { FocusReq } from "../state";
import { type Cell, type CellSpec, hasText, TEXT } from "../types";
import {
	caretAtEdge,
	caretInTable,
	caretOnEdgeLine,
	cellSurface,
	keepCaret,
	placeCaret,
	surfaceBlank,
} from "./surface";

/** The input line's hint with the sugar on. Matches the text cell's own. */
export const WRITE_HINT = "Write, or press / for cells";

/** R7's hint, on a text cell's empty last line (../../index.css). */
export const NEW_CELL_HINT = `${formatShortcut(["mod", "enter"])} new cell below`;

/** A rule heard on a text cell's row. */
type RowRule = {
	id: string;
	key: string;
	/** Cmd or Ctrl held. */
	mod: boolean;
	/** Shift may be held ("any": `/` needs it on some layouts), or must be.
	 *  Left out, it must not be. */
	shift?: "any" | "held";
	/** Whether it applies, asked of the cell's surface. */
	when?: (surface: HTMLElement, id: string) => boolean;
	run: (id: string) => void;
};

export function useTextSugar(
	{ cells, editor, notify, index, patch, rootRef }: PlaneModel,
	cellSpecs: CellSpec[],
	{
		focusCell,
		startDraft,
		openGhost,
		standIn,
		titleEnd,
	}: {
		focusCell: (cell: Cell, req: Omit<FocusReq, "cellId">, editing: string[]) => void;
		startDraft: ((after: string | null, text: string) => boolean) | null;
		openGhost: (after: string | null, home: (() => void) | null) => void;
		standIn: (id: string, home: () => void) => void;
		/** The caret to the end of the title, where there is one. */
		titleEnd?: React.RefObject<(() => void) | null>;
	},
) {
	const on = hasText(cellSpecs);

	const isText = useCallback((cell: Cell) => on && cell.made_by === TEXT, [on]);

	/** Take the caret off a cell that is going away: back to the one above. */
	const leaveUp = useCallback(
		(id: string) => {
			const prev = cells[index(id) - 1];
			if (!prev) {
				if (titleEnd?.current) titleEnd.current();
				else rootRef.current?.focus({ preventScroll: true });
				return;
			}
			const surface = cellSurface(rootRef.current, prev.id);
			if (surface) placeCaret(surface, "end");
			else focusCell(prev, { place: "end" }, editor.editing);
		},
		[cells, editor.editing, focusCell, index, rootRef, titleEnd],
	);

	/** The text cell next to `id` that way, or null when that one is not text. */
	const textAt = (id: string, d: -1 | 1): Cell | null => {
		const next = cells[index(id) + d];
		return next && isText(next) ? next : null;
	};

	/** Delete cell `id` here: hidden until the server drops it, source closed. */
	const remove = (id: string) => {
		notify("cell.delete", { cell_id: id });
		patch((e) => ({
			editing: e.editing.filter((x) => x !== id),
			leaving: [...e.leaving, id],
		}));
	};

	/** Up from the top cell: the title is above it, where there is one. */
	const toTitle = (id: string, d: -1 | 1) => d < 0 && index(id) === 0 && !!titleEnd?.current;

	/** R8: the caret into the text cell `d` away, or up into the title. */
	const slide = (d: -1 | 1) => (id: string) => {
		if (toTitle(id, d)) {
			titleEnd?.current?.();
			return;
		}
		const next = textAt(id, d);
		const surface = next && cellSurface(rootRef.current, next.id);
		if (surface) placeCaret(surface, d < 0 ? "end" : "start");
	};

	/** R8 applies at this edge, out of a table, with a text cell or the title that way. */
	const edge =
		(d: -1 | 1, at: (surface: HTMLElement) => boolean) => (surface: HTMLElement, id: string) =>
			!caretInTable(surface) && at(surface) && (textAt(id, d) !== null || toTitle(id, d));

	/** R10: from this text cell's text into cell selection, it and the cell
	 *  `d` away selected, anchored here. */
	const spill = (d: -1 | 1) => (id: string) => {
		const next = cells[index(id) + d];
		if (!next) return;
		document.getSelection()?.removeAllRanges();
		patch({ selected: d < 0 ? [next.id, id] : [id, next.id], anchor: id, focus: null });
		rootRef.current?.focus({ preventScroll: true });
	};

	/** R10 applies: the selection's head at this edge, a cell that way. */
	const spillEdge =
		(d: -1 | 1, at: (surface: HTMLElement) => boolean) => (surface: HTMLElement, id: string) =>
			!caretInTable(surface, true) && at(surface) && cells[index(id) + d] !== undefined;

	const rules: RowRule[] = [
		{
			id: "R2",
			key: "Backspace",
			mod: false,
			when: surfaceBlank,
			run: (id) => {
				leaveUp(id);
				remove(id);
			},
		},

		{
			id: "R6",
			key: "/",
			mod: false,
			shift: "any",
			when: surfaceBlank,
			run: (id) =>
				standIn(id, () => {
					const surface = cellSurface(rootRef.current, id);
					if (surface) placeCaret(surface, "start");
				}),
		},
		{
			id: "R7",
			key: "Enter",
			mod: true,
			when: (surface) => !caretInTable(surface),
			run: (id) => openGhost(id, keepCaret(rootRef.current, id)),
		},
		{
			id: "R8",
			key: "ArrowUp",
			mod: false,
			when: edge(-1, (s) => caretOnEdgeLine(s, "first")),
			run: slide(-1),
		},
		{
			id: "R8",
			key: "ArrowLeft",
			mod: false,
			when: edge(-1, (s) => caretAtEdge(s, "start")),
			run: slide(-1),
		},
		{
			id: "R8",
			key: "ArrowDown",
			mod: false,
			when: edge(1, (s) => caretOnEdgeLine(s, "last")),
			run: slide(1),
		},
		{
			id: "R8",
			key: "ArrowRight",
			mod: false,
			when: edge(1, (s) => caretAtEdge(s, "end")),
			run: slide(1),
		},
		{
			id: "R10",
			key: "ArrowUp",
			mod: false,
			shift: "held",
			when: spillEdge(-1, (s) => caretOnEdgeLine(s, "first", true)),
			run: spill(-1),
		},
		{
			id: "R10",
			key: "ArrowLeft",
			mod: false,
			shift: "held",
			when: spillEdge(-1, (s) => caretAtEdge(s, "start", true)),
			run: spill(-1),
		},
		{
			id: "R10",
			key: "ArrowDown",
			mod: false,
			shift: "held",
			when: spillEdge(1, (s) => caretOnEdgeLine(s, "last", true)),
			run: spill(1),
		},
		{
			id: "R10",
			key: "ArrowRight",
			mod: false,
			shift: "held",
			when: spillEdge(1, (s) => caretAtEdge(s, "end", true)),
			run: spill(1),
		},
	];

	/** A text cell's keys, caught on its row before its editor sees them. */
	const textKey = (e: React.KeyboardEvent, id: string) => {
		if (e.nativeEvent.isComposing || e.altKey) return;
		const surface = cellSurface(rootRef.current, id);
		if (!surface?.contains(e.target as Node)) return;
		const mod = e.metaKey || e.ctrlKey;
		const rule = rules.find(
			(r) =>
				r.key === e.key &&
				r.mod === mod &&
				(r.shift === "any" || (r.shift === "held") === e.shiftKey) &&
				(!r.when || r.when(surface, id)),
		);
		if (!rule) return;
		e.preventDefault();
		e.stopPropagation();
		rule.run(id);
	};

	/** R5, Enter in the title. False with no text Cell, or a draft already
	 *  on its way, and the title does what it did before. */
	const titleEnter = useCallback(() => startDraft?.(null, "") ?? false, [startDraft]);

	/** R8 from the title: Down at its end puts the caret at the start of a
	 *  text cell on top. False for anything else, which gets selected. */
	const titleDown = useCallback((): boolean => {
		const first = cells[0];
		const surface = first && isText(first) && cellSurface(rootRef.current, first.id);
		if (!surface) return false;
		placeCaret(surface, "start");
		return true;
	}, [cells, isText, rootRef]);

	return { isText, textKey, titleEnter, titleDown };
}
