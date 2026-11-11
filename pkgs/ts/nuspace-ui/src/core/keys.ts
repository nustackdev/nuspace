// The keyboard shortcuts sheet's state: whether it is open, and the key that
// opens it. What it lists is ../shell/keys.ts.
//
// Opened from the sidebar's footer or with cmd/ctrl+/, from anywhere, so its
// state is a module level store like ./confirm.ts, and the one dialog that
// draws it (../shell/KeysDialog.tsx) is mounted once, at the root.
//
// In core, under the sidebar that opens the sheet and the shell that lists
// the sidebar's keys, so neither imports the other's folder for it.

import { useEffect, useSyncExternalStore } from "react";

/** The shortcut by key name; the kit `Shortcut` spells it. */
export const KEYS_KEYS = ["mod", "/"] as const;

let open = false;
const subscribers = new Set<() => void>();

function emit(): void {
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

export function setKeysOpen(next: boolean): void {
	if (open === next) return;
	open = next;
	emit();
}

export function useKeysOpen(): boolean {
	return useSyncExternalStore(
		subscribe,
		() => open,
		() => open,
	);
}

/** Cmd/ctrl+/ flips the sheet from anywhere in the window. Mount it once. */
export function useKeysShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key !== "/" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
			e.preventDefault();
			setKeysOpen(!open);
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);
}
