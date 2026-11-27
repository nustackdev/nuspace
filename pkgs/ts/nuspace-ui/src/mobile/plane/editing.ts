// Editing a plane's cells: the mode where a tap on a cell opens its options
// sheet (./CellSheet.tsx) instead of reaching what the cell draws.
//
// Outside it a cell is only its content, and the phone's own long-press
// (select, copy, look up) and whatever the cell does with a touch stay
// theirs. Inside it each cell's content is inert and the whole cell is one
// tap target. The dock's + sheet goes in (../dock/ControlSheet.tsx), the
// dock's Done or back comes out.
//
// Like the sidebar it is a mark on the history entry (../entry.ts), its
// value the plane being edited: entering pushes the entry the tab is on
// again with the mark, so back leaves the mode, forward comes back to it,
// and a mode can never outlive the plane it was for. A reload while editing
// drops the mark in place (`settleEditing`).

import { type Entry, History, useEntry } from "@nustackdev/ui-kit";
import { markOf, withMark } from "../entry";

/** The key the editing entry carries in its history state: the plane's id. */
export const EDITING_STATE = "nuEditCells";

/** The plane whose cells `entry` edits; null when it edits none. */
export function editingOf(entry: Pick<Entry, "state">): string | null {
	const plane = markOf(entry, EDITING_STATE);
	return typeof plane === "string" && plane ? plane : null;
}

/** The plane whose cells are being edited, re-rendering as the mode comes and goes. */
export function useEditing(): string | null {
	return editingOf(useEntry());
}

/** Edit `plane`'s cells: the entry pushed again with the mark. Editing it already: nothing. */
export function editCells(plane: string): void {
	const now = History.current();
	const was = editingOf(now);
	if (was === plane) return;
	const state = withMark(now.state, EDITING_STATE, plane);
	// Another plane's mode turns into this one's, no second entry.
	if (was) History.replace(now.url, state);
	else History.push(now.url, state);
}

/** Leave the mode: one entry back. Not editing: nothing. */
export function doneEditing(): void {
	if (editingOf(History.current())) History.back();
}

/** A page that opened on an editing entry (a reload while editing): the mark dropped in place. */
export function settleEditing(): void {
	const now = History.current();
	if (editingOf(now)) History.replace(now.url, withMark(now.state, EDITING_STATE, null));
}
