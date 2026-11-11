// The nav section's planes: home, search and settings, found through the
// roles (../core/desks.ts), never by a fixed id. Each is a plane like any
// other; the role says which. The Planes tree leaves them out, by role.
//
// Each has a key from anywhere in the window: home cmd/ctrl+shift+H (the
// browsers' own home key, taken over here), search cmd/ctrl+K, settings
// cmd/ctrl+comma (the one every app uses). Home and settings on capture, so
// they work from inside a cell's editor too, which stops the keys it answers.
// Before the roles land a key does nothing.

import type { LucideIcon } from "lucide-react";
import { House, Search, Settings } from "lucide-react";
import { useEffect } from "react";
import { currentRoles, type Role, type Roles } from "../core/desks";
import { openPlane } from "../core/router";

/** The home shortcut by key name; the kit `Shortcut` spells it. */
export const HOME_KEYS = ["mod", "shift", "H"] as const;

/** The search shortcut by key name. */
export const SEARCH_KEYS = ["mod", "K"] as const;

/** The settings shortcut by key name. */
export const SETTINGS_KEYS = ["mod", ","] as const;

export type NavItem = { role: Role; label: string; icon: LucideIcon; keys: readonly string[] };

/** The nav section's rows, in order. */
export const NAV_ITEMS: readonly NavItem[] = [
	{ role: "home", label: "Home", icon: House, keys: HOME_KEYS },
	{ role: "search", label: "Search", icon: Search, keys: SEARCH_KEYS },
	{ role: "settings", label: "Settings", icon: Settings, keys: SETTINGS_KEYS },
];

/** The planes the roles point at: what the Planes tree leaves out. */
export function rolePlanes(roles: Roles | null): ReadonlySet<string> {
	return new Set(roles ? Object.values(roles).filter(Boolean) : []);
}

/** Open a role's plane solo. */
export function openRole(role: Role): void {
	const plane = currentRoles()?.[role];
	if (plane) openPlane(plane);
}

/** Which role a key press asks for, or null. */
function roleOf(e: KeyboardEvent): Role | null {
	if (!(e.metaKey || e.ctrlKey) || e.altKey) return null;
	const key = e.key.toLowerCase();
	if (e.shiftKey) return key === "h" ? "home" : null;
	if (key === "k") return "search";
	if (key === ",") return "settings";
	return null;
}

/** The three nav keys, from anywhere in the window. Mount it once. */
export function useNavShortcuts(): void {
	useEffect(() => {
		// Search bubbles, as it always has: an editor that answers cmd/ctrl+K keeps it.
		const on = (capture: boolean) => (e: KeyboardEvent) => {
			const role = roleOf(e);
			if (!role || (role === "search") === capture) return;
			e.preventDefault();
			openRole(role);
		};
		const captured = on(true);
		const bubbled = on(false);
		window.addEventListener("keydown", captured, true);
		window.addEventListener("keydown", bubbled);
		return () => {
			window.removeEventListener("keydown", captured, true);
			window.removeEventListener("keydown", bubbled);
		};
	}, []);
}
