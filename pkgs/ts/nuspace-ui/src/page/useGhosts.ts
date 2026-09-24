// Wiring for the two ghost inputs (./Ghost.tsx).
//
// Both ghosts run the same handlers. What differs is where they sit and
// whether they are allowed to go away: the end-of-page one is furniture, the
// summoned one is a passing offer. `after` is the block a ghost would create
// past -- null only on a page with no blocks -- and it doubles as the ghost's
// identity, which is how the slash state can name one when neither of them
// has an id of its own.

import { useCallback } from "react";
import type { GhostProps } from "./Ghost";
import type { PageModel } from "./model";
import type { FocusReq } from "./state";
import type { Block, ExitDir } from "./types";

export function useGhosts(
	{ blocks, editor, patch, index, rootRef, endGhost, plusGhost }: PageModel,
	{
		focusBlock,
		createAfter,
		slashKey,
	}: {
		focusBlock: (block: Block, req: Omit<FocusReq, "blockId">, editing: string[]) => void;
		createAfter: (afterId: string | null, name: string) => void;
		slashKey: (key: string) => boolean;
	},
) {
	/** Nothing was picked. Close the menu, and take the offer back. */
	const dismissGhost = useCallback(
		(transient: boolean) => patch(transient ? { ghost: null, slash: null } : { slash: null }),
		[patch],
	);

	/** Arrow out of a ghost into whichever block is that way, if any. */
	const leaveGhost = useCallback(
		(after: string | null, dir: ExitDir, transient: boolean) => {
			if (transient) patch({ ghost: null });
			const i = after ? index(after) : -1;
			const target = dir === "up" ? blocks[i] : blocks[i + 1];
			if (!target) return;
			focusBlock(target, { place: dir === "up" ? "end" : "start" }, editor.editing);
		},
		[blocks, editor.editing, focusBlock, index, patch],
	);

	/** Escape with no menu open selects the block the ghost hangs off, since
	 *  the ghost itself cannot be one. */
	const escapeGhost = useCallback(
		(after: string | null, transient: boolean) => {
			const block = after ? blocks[index(after)] : null;
			patch((e) => ({
				slash: null,
				ghost: transient ? null : e.ghost,
				selected: block ? [block.id] : [],
				anchor: block ? block.id : null,
				focus: null,
			}));
			rootRef.current?.focus({ preventScroll: true });
		},
		[blocks, index, patch, rootRef],
	);

	/**
	 * One ghost's props. `after` is both where it sits and who it is.
	 *
	 * A plain function rather than a memo: it takes arguments that only the
	 * render knows, and what it returns goes straight into an element.
	 */
	const ghostProps = (after: string | null, transient: boolean): GhostProps => ({
		hostRef: transient ? plusGhost : endGhost,
		autoFocus: transient,
		query: editor.slash && editor.slash.blockId === after ? editor.slash.query : null,
		onWake: () => {
			// Clicking a ghost leaves block-selection mode, exactly as
			// clicking into a block does.
			patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
		},
		onBlank: () => {
			patch({ slash: null, ghost: null });
			createAfter(after, "");
		},
		onOpenSlash: (anchor, query) =>
			patch({
				slash: { blockId: after, query, anchor, index: 0 },
				selected: [],
				anchor: null,
			}),
		onQuery: (query) => patch((e) => (e.slash ? { slash: { ...e.slash, query, index: 0 } } : {})),
		onKey: slashKey,
		onCloseSlash: () => patch({ slash: null }),
		onEscape: () => escapeGhost(after, transient),
		onLeave: (dir) => leaveGhost(after, dir, transient),
		onDismiss: () => dismissGhost(transient),
	});

	return ghostProps;
}
