// The ghost input: the one thing on a plane that is not a cell.
//
// A ghost is a line you can put a caret in that has not decided what it is
// yet. It holds no value, owns no id, and nothing exists in the store because
// of it. Press `/` and it offers the registered Cells; pick one and it
// becomes a cell made from that Cell. That is the whole of it, the core.
//
// The text sugar (./sugar) adds the rest: typing, Enter included, becomes a
// text cell with the typing in it. Without a text Cell the typing searches
// the Cells instead.
//
// There is always one at the end of the plane, which is what makes an empty
// plane writeable without hunting for a control, and a second one can be
// summoned after any row: by the gutter `+`, or Cmd+Enter in a text cell. The
// summoned one is transient: it resolves into a cell or it is gone the moment
// it loses focus with nothing in it. It can also stand in for an empty text
// cell, on `/` there (see `replace` in ./state.ts). The wiring is
// ./useGhosts.ts.

import type * as React from "react";
import { useEffect } from "react";
import { docGhost } from "../../design";
import type { SlashAnchor } from "../state";
import type { ExitDir } from "../types";

/** What a ghost offers before anything has happened in it, sugar off. */
const GHOST_HINT = "Press / for cells";
/** ...and once the menu is open, which is the whole of what changed. */
const GHOST_SEARCH = "Type to search";

export type GhostProps = {
	hostRef: React.RefObject<HTMLInputElement | null>;
	/** A summoned ghost takes the caret; the end-of-plane one waits for it. */
	autoFocus: boolean;
	/** Open the menu as it mounts: a stand-in, which is there for the menu. */
	openMenu?: boolean;
	/** The placeholder with the menu closed. */
	hint?: string;
	/** The slash query while the menu is open on THIS ghost. Null when not. */
	query: string | null;
	/** The caret arrived. */
	onWake: () => void;
	onOpenSlash: (anchor: SlashAnchor, query: string) => void;
	/** Typing with the menu closed, Enter as "", starts a draft. Null:
	 *  typing opens the menu and Enter does nothing. */
	onType: ((text: string) => void) | null;
	onQuery: (query: string) => void;
	/** Return true if the menu consumed the key. */
	onKey: (key: string) => boolean;
	/** Put the menu away and leave the ghost standing. */
	onCloseSlash: () => void;
	onEscape: () => void;
	onLeave: (dir: ExitDir) => void;
	onDismiss: () => void;
	/** Show the hint without a caret: the plane is empty, so this line is all there is. */
	hinted?: boolean;
};

/**
 * The ghost input.
 *
 * A one-line text input that never holds anything but the slash query. `/`
 * opens the menu with an empty query; any other character starts a draft, or
 * with nothing to draft opens the menu with that character as the query.
 *
 * An `<input>` and not a contenteditable on purpose: it is one line, it holds
 * no marks, it is in the tab order for free, and screen readers already know
 * what it is.
 */
export function Ghost({
	hostRef,
	autoFocus,
	openMenu = false,
	hint = GHOST_HINT,
	query,
	onWake,
	onOpenSlash,
	onType,
	onQuery,
	onKey,
	onCloseSlash,
	onEscape,
	onLeave,
	onDismiss,
	hinted = false,
}: GhostProps) {
	const open = query !== null;

	// biome-ignore lint/correctness/useExhaustiveDependencies: on mount and when summoned, never per render
	useEffect(() => {
		const el = hostRef.current;
		if (!autoFocus || !el) return;
		el.focus();
		if (openMenu) onOpenSlash(el, "");
	}, [autoFocus]);

	return (
		<input
			ref={hostRef}
			type="text"
			aria-label="New cell"
			className={docGhost(hinted)}
			placeholder={open ? GHOST_SEARCH : hint}
			value={query ?? ""}
			onFocus={onWake}
			onChange={(e) => {
				const next = e.currentTarget.value;
				if (open) {
					onQuery(next);
					return;
				}
				if (next && onType) onType(next);
				else if (next) onOpenSlash(e.currentTarget, next);
			}}
			onKeyDown={(e) => {
				// The ghost owns its keyboard outright, for the reason a focused
				// cell does: the plane must not also act on a key answered here.
				e.stopPropagation();
				if (open && onKey(e.key)) {
					e.preventDefault();
					return;
				}
				if (open) {
					// Backspacing off the end of the query puts the menu away.
					if (e.key === "Backspace" && query === "") {
						e.preventDefault();
						onCloseSlash();
					}
					return;
				}
				if (e.key === "Escape") {
					e.preventDefault();
					onEscape();
					return;
				}
				if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
					// Consumed: the `/` is the gesture, not the query.
					e.preventDefault();
					onOpenSlash(e.currentTarget, "");
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					onType?.("");
					return;
				}
				if (e.key === "ArrowUp" || e.key === "ArrowLeft" || e.key === "Backspace") {
					e.preventDefault();
					onLeave("up");
					return;
				}
				if (e.key === "ArrowDown" || e.key === "ArrowRight") {
					e.preventDefault();
					onLeave("down");
				}
			}}
			onBlur={() => {
				// Nothing was picked, or the pick would have unmounted this. A
				// menu pick keeps the caret here (mousedown is prevented), so a
				// blur is always a departure and never a selection.
				onDismiss();
			}}
		/>
	);
}
