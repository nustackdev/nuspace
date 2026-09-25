// Type to create: a letter typed into a ghost, carried into a new text cell.
//
// The letter starts a cell from the first snippet flagged `on_type` and turns
// the ghost into a draft: plain text, held here in the browser, that keeps
// taking keys while the cell makes its round trip. When the cell's editor is
// ready the draft's text is typed into it through the browser's own insert,
// so the editor's normal change path is what saves it, and the draft goes.
//
// Ready is two real signals, never a timer:
//
//   - the cell's ui subtree holds a node with a string `value`, which is the
//     program's first write landing, and
//   - the cell's row holds an editable surface, which is the editor mounted
//     over that value.
//
// Either can come last, so both the tree store and the DOM are watched. The
// cell is found by the id minted here and nothing else, so another person's
// new cell never matches.
//
// Left out on purpose: an editor that never mounts leaves the draft standing,
// a reload loses it, and there is one draft at a time.

import type { Path, TreeNode } from "@nustackdev/ui-core";
import { nodeAt, pathKey, tree } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { docDraft } from "../design";
import { cellUiPath } from "./cell/address";
import type { PlaneModel } from "./model";
import type { SlashSnippet } from "./types";

/** What counts as a cell's editable text surface. The first one wins. */
const EDITABLE = '[contenteditable="true"], textarea, input';

export type DraftState = {
	/** The cell it is waiting for, minted when the letter was typed. */
	id: string;
	/** Where the ghost was: the cell it sat after, null on an empty plane. */
	after: string | null;
	/** What it opened with. The box holds the rest. */
	text: string;
};

/** Whether anything in this subtree holds a string `value`. */
function holdsValue(node: TreeNode | null): boolean {
	if (!node) return false;
	if (typeof node.props.value === "string") return true;
	for (const child of node.children.values()) if (holdsValue(child)) return true;
	return false;
}

export function useDraft(
	{ rootRef, patch }: PlaneModel,
	viewerPath: Path,
	snippets: SlashSnippet[],
	createAfter: (afterId: string | null, name: string, land?: boolean) => string,
) {
	const [draft, setDraft] = useState<DraftState | null>(null);
	const boxRef = useRef<HTMLTextAreaElement | null>(null);
	const name = snippets.find((s) => s.onType)?.name;

	/** Null when no snippet is flagged: the ghost opens the menu as before. */
	const startDraft =
		name === undefined
			? null
			: (after: string | null, text: string) => {
					patch({ ghost: null, slash: null });
					if (draft) return;
					// The draft owns the caret, so the cell is not landed on.
					setDraft({ id: createAfter(after, name, false), after, text });
				};

	const viewerKey = pathKey(viewerPath);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	useEffect(() => {
		if (!draft) return;
		const path = cellUiPath(viewerPath, draft.id);
		let done = false;
		const handoff = () => {
			const row = rootRef.current?.querySelector(`[data-cell="${draft.id}"]`);
			const surface = row?.querySelector<HTMLElement>(EDITABLE);
			if (done || !surface || !holdsValue(nodeAt(path))) return;
			done = true;
			const box = boxRef.current;
			const text = box ? box.value : draft.text;
			const prev = document.activeElement;
			const kept = box !== null && prev === box;
			// Drop the draft and show the cell now, so the surface can take focus.
			flushSync(() => setDraft(null));
			surface.focus();
			document.execCommand("insertText", false, text);
			if (kept) return;
			// The caret went somewhere else meanwhile: the text lands, the caret
			// goes back. Leaving the editor is also what saves it.
			if (prev instanceof HTMLElement && prev !== document.body) prev.focus();
			else surface.blur();
		};
		const seen = new MutationObserver(handoff);
		if (rootRef.current) seen.observe(rootRef.current, { childList: true, subtree: true });
		const unsubscribe = tree.subscribe(handoff);
		return () => {
			seen.disconnect();
			unsubscribe();
		};
	}, [draft, viewerKey, rootRef]);

	return { draft, boxRef, startDraft };
}

/** The draft's box. Uncontrolled: it stays mounted until the handoff reads it. */
export function Draft({
	boxRef,
	text,
}: {
	boxRef: React.RefObject<HTMLTextAreaElement | null>;
	text: string;
}) {
	// biome-ignore lint/correctness/useExhaustiveDependencies: once, on mount
	useEffect(() => {
		const box = boxRef.current;
		if (!box) return;
		box.focus();
		box.setSelectionRange(box.value.length, box.value.length);
	}, []);

	return (
		<textarea
			ref={boxRef}
			aria-label="New text cell"
			rows={1}
			className={docDraft}
			defaultValue={text}
			// Its keys are its own, as a ghost's are.
			onKeyDown={(e) => e.stopPropagation()}
		/>
	);
}
