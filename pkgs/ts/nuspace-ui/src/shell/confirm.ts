// Asking before something that cannot be undone.
//
// Anything can ask, from a menu item or a plain function, so the question is
// a module level store like ../sidebar/add.ts rather than a prop, and the one
// dialog that draws it (./ConfirmDialog.tsx) is mounted once, at the root. Asking
// again while a question is open answers the first one no.

import { useSyncExternalStore } from "react";

export type Question = {
	title: string;
	description: string;
	/** The destructive button's words, eg "Delete". */
	action: string;
};

type Open = Question & { answer: (yes: boolean) => void };

let open: Open | null = null;
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

/** Ask `q`. Resolves true on the action, false on cancel or dismiss. */
export function confirm(q: Question): Promise<boolean> {
	open?.answer(false);
	return new Promise((resolve) => {
		open = { ...q, answer: resolve };
		emit();
	});
}

/** Answer the open question and close it. */
export function answer(yes: boolean): void {
	if (!open) return;
	const q = open;
	open = null;
	q.answer(yes);
	emit();
}

/** The open question, null while none is. */
export function useQuestion(): Open | null {
	return useSyncExternalStore(
		subscribe,
		() => open,
		() => open,
	);
}
