// Search is a Plane: the host seeds it (`search`), and its form cell asks by
// content kind. The rail's search entry and cmd/ctrl+K, from anywhere in the
// window, open it and put the keyboard in its form.

import { useEffect } from "react";
import { replacePane } from "../core/router";

/** The search Plane's id, fixed by the host. */
export const SEARCH_PLANE = "search";

/** The form cell's id on it: the host seeds it as `<plane>_form`. */
export const SEARCH_FORM = `${SEARCH_PLANE}_form`;

/** The shortcut by key name, for the entry's hint; the kit `Shortcut` spells it. */
export const SEARCH_KEYS = ["mod", "K"] as const;

/** How long to wait for the form to be drawn before giving up on focusing it. */
const FOCUS_WAIT_MS = 2000;

/** The form's first text box, or its first control, once it is drawn. */
function formControl(): HTMLElement | null {
	const form = document.querySelector<HTMLElement>(`[data-cell="${SEARCH_FORM}"]`);
	if (!form) return null;
	return (
		form.querySelector<HTMLElement>("input:not([type=hidden])") ??
		form.querySelector<HTMLElement>("button, [tabindex]:not([tabindex='-1'])")
	);
}

/** Focus the form when it shows up: it may still be on its way from the server. */
function focusForm(): void {
	const until = performance.now() + FOCUS_WAIT_MS;
	const tick = () => {
		const control = formControl();
		if (control) control.focus();
		else if (performance.now() < until) requestAnimationFrame(tick);
	};
	requestAnimationFrame(tick);
}

/** Open the search Plane in the focused pane, or focus it where it is open, then its form. */
export function openSearch(): void {
	replacePane(SEARCH_PLANE);
	focusForm();
}

/** Cmd/ctrl+K opens search from anywhere in the window. Mount it once. */
export function useSearchShortcut(): void {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.key.toLowerCase() !== "k" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) {
				return;
			}
			e.preventDefault();
			openSearch();
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);
}
