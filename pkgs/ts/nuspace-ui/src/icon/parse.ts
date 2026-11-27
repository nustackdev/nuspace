// A plane's icon, and the default it falls back to.
//
// `meta.icon` is a stored icon string, spelled the kit's way ("lucide:<name>",
// "emoji:<char>", a bare lucide name, "" for none; the kit's `parseIcon`
// reads it). What nuspace adds is the default: a plane always shows an icon,
// so a value that reads as none shows the page one.
// Mirrors `nuspace.ops.plane.plane_icon` on the server.

import { type IconValue, parseIcon } from "@nustackdev/ui-kit";

// The mobile shell still imports the reader from here.
export { parseIcon };

/** The lucide name a plane shows when neither it nor its registered Plane names an icon. */
export const DEFAULT_ICON_NAME = "file-text";

/** What a plane shows when neither it nor its registered Plane names an icon. */
export const DEFAULT_ICON: IconValue = { kind: "lucide", name: DEFAULT_ICON_NAME };

/** Where the picker keeps this browser's recent picks: nuspace's own list, the key it always had. */
export const RECENT_ICONS = "nuspace.icons.recent";

/**
 * What a plane shows: its own `meta.icon`, which every plane is made with.
 * The default only guards a value that does not read as an icon, so a bad
 * one never breaks a row. Never null.
 */
export function planeIcon(own: unknown): IconValue {
	return parseIcon(own) ?? DEFAULT_ICON;
}
