// A plane's icon, as the server stores it and as the browser draws it.
//
// The one place a spelling is read. `meta.icon` is a string:
//
//   "lucide:<name>"   one of our icon pack's glyphs (./pack.ts)
//   "emoji:<char>"    an emoji, drawn as text
//   "" or absent      the default
//
// A bare name, no prefix, is a lucide one: that is how a registered Plane
// names its icon. A lucide name the pack does not have, or any other prefix,
// reads as no icon, so the caller falls back to the next one in line.
// Mirrors `nuspace.ops.plane.plane_icon` on the server.

import { DEFAULT_ICON_NAME, packIcon } from "./pack";

export const LUCIDE = "lucide:";
export const EMOJI = "emoji:";

export type Icon = { kind: "lucide"; name: string } | { kind: "emoji"; char: string };

/** What a plane shows when neither it nor its registered Plane names an icon. */
export const DEFAULT_ICON: Icon = { kind: "lucide", name: DEFAULT_ICON_NAME };

/** `FileText`, `fileText` and `file-text` are one name; so are `Gamepad2` and `gamepad-2`. */
function kebab(name: string): string {
	return name
		.trim()
		.replace(/([a-z0-9])([A-Z])/g, "$1-$2")
		.replace(/([a-zA-Z])(\d)/g, "$1-$2")
		.toLowerCase();
}

/** The icon a stored value names, or null for none (empty, unknown, not a string). */
export function parseIcon(raw: unknown): Icon | null {
	if (typeof raw !== "string") return null;
	const value = raw.trim();
	if (!value) return null;
	if (value.startsWith(EMOJI)) {
		const char = value.slice(EMOJI.length).trim();
		return char ? { kind: "emoji", char } : null;
	}
	let name = value;
	if (value.startsWith(LUCIDE)) name = value.slice(LUCIDE.length);
	else if (value.includes(":")) return null;
	const known = packIcon(kebab(name));
	return known ? { kind: "lucide", name: known.name } : null;
}

/** The stored spelling of an icon, "" for none. */
export function formatIcon(icon: Icon | null): string {
	if (!icon) return "";
	return icon.kind === "emoji" ? `${EMOJI}${icon.char}` : `${LUCIDE}${icon.name}`;
}

/**
 * What a plane shows: its own `meta.icon`, else its registered Plane's icon,
 * else the default. Never null.
 */
export function planeIcon(own: unknown, registered = ""): Icon {
	return parseIcon(own) ?? parseIcon(registered) ?? DEFAULT_ICON;
}
