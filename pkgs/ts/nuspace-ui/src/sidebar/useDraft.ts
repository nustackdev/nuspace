// Inline rename and create. Both happen in the row itself, on a kit `Input`:
// `window.prompt` blocks the tab, cannot be themed, and is not so much a dialog
// as the absence of one.

import { useCallback, useState } from "react";
import { mintId } from "../app/ids";
import { replacePane } from "../app/router";
import type { Notify } from "./ops";
import type { VisibleRow } from "./tree";

/** An inline edit in flight. `create` renders a phantom row under `key`. */
export type Draft = {
	kind: "rename" | "create";
	key: string;
	id: string;
	group: string;
	initial: string;
};

export function useDraft({
	reveal,
	notify,
	focusKey,
}: {
	reveal: (key: string) => void;
	notify: Notify;
	/** Where the caret goes back to when an edit is cancelled. */
	focusKey: (key: string) => void;
}) {
	const [draft, setDraft] = useState<Draft | null>(null);

	const startRename = useCallback((row: VisibleRow) => {
		setDraft({
			kind: "rename",
			key: row.key,
			id: row.id,
			group: row.group,
			initial: row.title,
		});
	}, []);

	const startCreate = useCallback(
		(row: VisibleRow) => {
			reveal(row.key);
			setDraft({
				kind: "create",
				key: row.key,
				id: row.id,
				group: row.group,
				initial: "Untitled",
			});
		},
		[reveal],
	);

	const commitDraft = useCallback(
		(title: string) => {
			const d = draft;
			setDraft(null);
			if (!d) return;
			const next = title.trim();
			if (!next) return;
			if (d.kind === "rename") {
				if (next === d.initial.trim()) return;
				notify("page.rename", { page_id: d.id, title: next });
			} else {
				// The id is minted here, so the new Plane can be routed to the
				// moment the server confirms it rather than guessed at. `group`
				// is what decides what gets built; `parent_id` is where the row
				// would sit, and nothing nests yet.
				// Then open it in the focused pane, as a plain click would. The
				// frames go out in order, so the server has made it by the time
				// `pages.open` names it.
				const pageId = mintId("p");
				notify("page.create", {
					page_id: pageId,
					parent_id: "",
					group: d.group,
					title: next,
				});
				replacePane(pageId);
			}
		},
		[draft, notify],
	);

	const cancelDraft = useCallback(() => {
		const d = draft;
		setDraft(null);
		if (d) focusKey(d.key);
	}, [draft, focusKey]);

	return { draft, startRename, startCreate, commitDraft, cancelDraft };
}
