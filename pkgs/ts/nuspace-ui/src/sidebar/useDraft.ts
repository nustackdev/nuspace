// Inline rename. It happens in the row itself, on a kit `Input`:
// `window.prompt` freezes the tab, cannot be themed, and is not so much a
// dialog as the absence of one.

import { useCallback, useState } from "react";
import type { Notify } from "./ops";
import type { VisibleRow } from "./tree";

/** A rename in flight, on the row `key`. */
export type Draft = {
	key: string;
	id: string;
	initial: string;
};

export function useDraft({
	notify,
	focusKey,
}: {
	notify: Notify;
	/** Where the caret goes back to when an edit ends. */
	focusKey: (key: string) => void;
}) {
	const [draft, setDraft] = useState<Draft | null>(null);

	const startRename = useCallback((row: VisibleRow) => {
		setDraft({ key: row.key, id: row.id, initial: row.title });
	}, []);

	const commitDraft = useCallback(
		(title: string) => {
			const d = draft;
			setDraft(null);
			if (!d) return;
			const next = title.trim();
			if (!next || next === d.initial.trim()) return;
			notify("plane.rename", { plane_id: d.id, title: next });
		},
		[draft, notify],
	);

	const cancelDraft = useCallback(() => {
		const d = draft;
		setDraft(null);
		if (d) focusKey(d.key);
	}, [draft, focusKey]);

	return { draft, startRename, commitDraft, cancelDraft };
}
