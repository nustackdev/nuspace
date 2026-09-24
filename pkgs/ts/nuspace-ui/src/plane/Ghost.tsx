// The ghost input: the one thing on a plane that is not a cell.
//
// A ghost is a line you can put a caret in that has not decided what it is
// yet. It holds no value, owns no id, and nothing exists in the store because
// of it. Press `/` (or just start typing) and it offers the registered
// snippets; pick one and it becomes a cell made from that snippet. Enter on
// an empty ghost makes a blank program.
//
// There is always one at the end of the plane, which is what makes an empty
// plane writeable without hunting for a control, and the gutter `+` summons a
// second one after any row. The summoned one is transient: it resolves into a
// cell or it is gone the moment it loses focus with nothing in it. The
// wiring for both is ./useGhosts.ts.

import type * as React from "react";
import { useEffect } from "react";
import { docGhost } from "../design";
import type { ExitDir } from "./types";

/** What a ghost offers before anything has happened in it. */
const GHOST_HINT = "/ for cells";
/** ...and once the menu is open, which is the whole of what changed. */
const GHOST_SEARCH = "Type to search";

export type GhostProps = {
	hostRef: React.RefObject<HTMLInputElement | null>;
	/** A summoned ghost takes the caret; the end-of-plane one waits for it. */
	autoFocus: boolean;
	/** The slash query while the menu is open on THIS ghost. Null when not. */
	query: string | null;
	/** The caret arrived. */
	onWake: () => void;
	/** Enter on an empty ghost: a blank program. */
	onBlank: () => void;
	onOpenSlash: (anchor: { x: number; y: number }, query: string) => void;
	onQuery: (query: string) => void;
	/** Return true if the menu consumed the key. */
	onKey: (key: string) => boolean;
	/** Put the menu away and leave the ghost standing. */
	onCloseSlash: () => void;
	onEscape: () => void;
	onLeave: (dir: ExitDir) => void;
	onDismiss: () => void;
};

/**
 * The ghost input.
 *
 * A one-line text input that never holds anything but the slash query. `/`
 * opens the menu with an empty query; any other character opens it with that
 * character as the query. Enter with the menu closed makes a blank program.
 *
 * An `<input>` and not a contenteditable on purpose: it is one line, it holds
 * no marks, it is in the tab order for free, and screen readers already know
 * what it is.
 */
export function Ghost({
	hostRef,
	autoFocus,
	query,
	onWake,
	onBlank,
	onOpenSlash,
	onQuery,
	onKey,
	onCloseSlash,
	onEscape,
	onLeave,
	onDismiss,
}: GhostProps) {
	const open = query !== null;

	// biome-ignore lint/correctness/useExhaustiveDependencies: hostRef is a ref object and never changes identity
	useEffect(() => {
		if (autoFocus) hostRef.current?.focus();
	}, [autoFocus]);

	const anchorOf = (el: HTMLElement) => {
		const r = el.getBoundingClientRect();
		return { x: r.left, y: r.bottom };
	};

	return (
		<input
			ref={hostRef}
			type="text"
			aria-label="New cell"
			className={docGhost}
			placeholder={open ? GHOST_SEARCH : GHOST_HINT}
			value={query ?? ""}
			onFocus={onWake}
			onChange={(e) => {
				const next = e.currentTarget.value;
				if (open) {
					onQuery(next);
					return;
				}
				if (next) onOpenSlash(anchorOf(e.currentTarget), next);
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
					onOpenSlash(anchorOf(e.currentTarget), "");
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					onBlank();
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
