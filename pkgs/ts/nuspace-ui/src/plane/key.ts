// What a key is allowed to be, and copying one, for the identity block
// (./Identity.tsx).
//
// Only the spelling is checked here, with the server's own rule (key chars,
// `nuspace/utils/interactions.py` `KEY_CHARS`). A key already taken is the
// server's to refuse, and its refusal toasts like any other failed edit.

import { toast } from "@nustackdev/ui-kit";
import { copyText } from "../core/clipboard";

/** Key chars: letters, digits, `_` and `-`, one at least. Case is kept. */
const KEY_CHARS = /^[A-Za-z0-9_-]+$/;

/** What is wrong with `key` as a key, null when nothing is. */
export function keyProblem(key: string): string | null {
	if (key === "") return "A key can't be empty";
	if (!KEY_CHARS.test(key)) return "Use letters, digits, _ and -";
	return null;
}

/** Copy `text` and say so in a toast. */
export async function copyWithToast(text: string): Promise<void> {
	if (await copyText(text)) toast({ title: "Copied", description: text });
	else toast({ tone: "danger", title: "Could not copy", description: text });
}
