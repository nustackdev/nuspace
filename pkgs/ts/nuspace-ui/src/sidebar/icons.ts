// A registered Plane's icon, by lucide name.
//
// The server names an icon as a string, so the browser needs a map from the
// name to a component. A small explicit one, for the icons the shipped Planes
// use: importing lucide's whole set to look names up would put every icon in
// the bundle. A name not in the map, or "", is the default document icon.

import { Activity, Cpu, FileText, Folder, Layers, type LucideIcon } from "lucide-react";
import type { Registered } from "./types";

const ICONS: Record<string, LucideIcon> = {
	"file-text": FileText,
	activity: Activity,
	cpu: Cpu,
	layers: Layers,
	folder: Folder,
};

/** The component for a lucide icon name. Kebab or Pascal case. */
export function iconNamed(name: string): LucideIcon {
	const kebab = name.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
	return ICONS[kebab] ?? FileText;
}

/** The icon of the registered Plane a row was made from, the default when none. */
export function iconFor(registered: Registered[], madeBy: string): LucideIcon {
	return iconNamed(registered.find((r) => r.name === madeBy)?.icon ?? "");
}
