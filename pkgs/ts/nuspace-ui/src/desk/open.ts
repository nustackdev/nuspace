// Opening a plane to the side: Option Cmd click on a link (the kit's catcher
// hands it over as "alt-mod"), or a plane menu's "Open to the side".
//
// Option alone is a plain click: browsers take it for their own (Zen's
// Glance, a download in Chrome and Safari). Zen's Glance also takes any odd
// count of modifiers with Option, so a gesture added here has to hold an
// even count. A new desk has no gesture, only its menu item.
//
// To the side puts the plane next to where the click came from. On a solo
// plane it makes a new desk of the two, side by side. On a desk item it is a
// new column right of the pane the link sits in, or of the focused pane when
// the link is outside any pane (a sidebar row). A plane the strip shows
// already is focused and brought on screen instead, never shown twice. On an
// empty desk it is the desk's first item. The new pane takes focus.
//
// Both are the drag table's moves (./dnd.ts), as if the plane were dropped
// there, so a click and a drop land the same way. `linkRule` is the shell's
// and the sidebar's anchor rule: this gesture, the rest is the router's (../core/router.ts `paneRule`).

import type { AnchorRule } from "@nustackdev/ui-kit";
import {
	currentRoute,
	type Link,
	openDesk,
	openPane,
	openPlane,
	paneRule,
	planeLinkOf,
} from "../core/router";
import { canDrop, dropOn, dropOnSolo, type Payload, type Target } from "./dnd";
import * as M from "./model";

/** Open `link` to the side of the pane showing `pane`, or of the focused one when "" (see the top). */
export function openToTheSide(link: Link, pane = ""): void {
	if (!link.plane) return;
	const route = currentRoute();
	const payload: Payload = { kind: "plane", link };
	if (route.kind === "solo") {
		if (route.plane === link.plane) openPlane(link);
		else dropOnSolo(payload, { plane: route.plane, params: route.params }, "right");
		return;
	}
	if (route.kind === "desk") {
		dropOn(payload, { kind: "end", desk: route.desk });
		openDesk(route.desk);
		return;
	}
	if (route.kind !== "item") {
		openPlane(link);
		return;
	}
	const { desk, item } = route;
	if (item.kind === "strip" && M.locate(item, link.plane)) {
		openPane(desk, item.id, link.plane);
		return;
	}
	const from = item.kind === "strip" && pane && M.locate(item, pane) ? pane : route.focus;
	const target: Target =
		item.kind === "plane"
			? { kind: "onto", desk, item: item.id, edge: "right" }
			: { kind: "strip", desk, item: item.id, drop: { plane: from, edge: "right" } };
	if (!canDrop(payload, target)) return;
	dropOn(payload, target);
	openPane(desk, item.id, link.plane);
}

/** The shell's and the sidebar's anchor rule: Option Cmd to the side, the rest the router's. */
export const linkRule: AnchorRule = (href, gesture, anchor, event) => {
	const link = gesture === "alt-mod" ? planeLinkOf(href) : null;
	if (!link) return paneRule(href, gesture, anchor, event);
	openToTheSide(link, anchor.closest("[data-pane]")?.getAttribute("data-pane") ?? "");
	return true;
};
