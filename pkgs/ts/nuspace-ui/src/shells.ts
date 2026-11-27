// Two shells, one per kind of hand. A touch device (the kit's `touchDevice`:
// a coarse pointer that cannot hover) gets the mobile shell, everything else
// the desktop one. Picked once, when the page loads: no switching while it is
// open, no override, a reload picks again.
//
// Each shell is its own dynamic import, so desktop never downloads the mobile
// shell and a phone never downloads desktop's drag and drop. Below the shells
// everything is shared: the connection, the router, the desk and pane state,
// the refs (../refs/register.ts registers the shared node types). Each shell
// registers the two node types it draws itself (ViewerRef, SidebarRef) when
// its module loads, which is before its root opens the socket.

import type { ComponentType } from "react";

export type ShellKind = "desktop" | "mobile";

/** Which shell a device gets. */
export function shellFor(touch: boolean): ShellKind {
	return touch ? "mobile" : "desktop";
}

/** Load a shell's root, its own chunk. */
export function loadShell(kind: ShellKind): Promise<ComponentType> {
	return kind === "mobile"
		? import("./mobile/App").then((m) => m.MobileApp)
		: import("./App").then((m) => m.App);
}
