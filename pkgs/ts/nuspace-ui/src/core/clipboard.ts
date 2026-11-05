// Copying an id, with the menu row it came from saying so.
//
// A menu row that copies stays open on its press and reads "Copied" for a
// moment: the menu is where the eye is, so the answer goes there too. A
// clipboard the browser refuses is quiet, as the row would be with no
// clipboard at all.

import { useCallback, useEffect, useState } from "react";

/** How long a row reads "Copied". */
const COPIED_MS = 1200;

/** `text` onto the clipboard. False when the browser would not. */
export async function copyText(text: string): Promise<boolean> {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		return false;
	}
}

/** Copy `text` on a menu row's select, keeping the menu open, and whether it just did. */
export function useCopyRow(text: string) {
	const [copied, setCopied] = useState(false);

	useEffect(() => {
		if (!copied) return;
		const t = window.setTimeout(() => setCopied(false), COPIED_MS);
		return () => window.clearTimeout(t);
	}, [copied]);

	const onSelect = useCallback(
		(e: Event) => {
			e.preventDefault();
			void copyText(text).then((ok) => {
				if (ok) setCopied(true);
			});
		},
		[text],
	);

	return { copied, onSelect };
}
