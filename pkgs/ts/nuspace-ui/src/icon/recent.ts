// The icons this viewer picked last, newest first, for the picker's Recent
// row. Per browser, in localStorage, and a convenience only: storage that is
// blocked, full or holding junk reads as nothing picked yet.

import { parseIcon } from "./parse";

const KEY = "nuspace.icons.recent";

/** Two rows of the picker's grid. */
export const RECENT_MAX = 18;

export function readRecent(): string[] {
	try {
		const raw = window.localStorage.getItem(KEY);
		const list: unknown = raw ? JSON.parse(raw) : [];
		if (!Array.isArray(list)) return [];
		return list
			.filter((v): v is string => typeof v === "string" && parseIcon(v) !== null)
			.slice(0, RECENT_MAX);
	} catch {
		return [];
	}
}

export function pushRecent(icon: string): void {
	try {
		const next = [icon, ...readRecent().filter((v) => v !== icon)].slice(0, RECENT_MAX);
		window.localStorage.setItem(KEY, JSON.stringify(next));
	} catch {
		// Nowhere to keep it. The pick itself already happened.
	}
}
