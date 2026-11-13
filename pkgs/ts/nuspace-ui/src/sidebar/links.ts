// The sidebar's one link of its own: a pane row. Its anchor's href is its
// strip's item url, and only the row knows which pane it stands for
// (`data-sidebar-pane`): a plain click or Enter opens the strip with that
// pane focused and on screen. Every other link, Planes tree and nav rows and
// desk item rows included, is the shell's rule (../desk/open.ts `linkRule`),
// which opens a plane url solo outside a pane, to the side with Option Cmd,
// and an item url as that item.
//
// A navigated desk row's icon is a link of its own too: its href is the
// original plane's url and it carries `data-sidebar-reset`. A plain click or
// Enter resets the item to its original, in place.
//
// The rows are real anchors, so a Cmd click and a middle click stay the
// browser's (a new tab). Mounted on the sidebar itself (`useSidebarLinks`),
// inside the shell's own catcher: the kit's catcher cancels a link it took,
// and the shell's then leaves it alone, so a sidebar row is asked once.

import { type AnchorRule, useAnchorCatcher } from "@nustackdev/ui-kit";
import type { RefObject } from "react";
import { knownDesks, openPane, resetItem, shapeOfHref } from "../core/router";
import { linkRule } from "../desk/open";

/** The attribute a pane row carries: the plane its pane shows. */
export const PANE_ATTR = "data-sidebar-pane";

/** The attribute a navigated row's icon carries: `resetAttr` of its item. */
export const RESET_ATTR = "data-sidebar-reset";

/** The `RESET_ATTR` value of desk `desk`'s item `item` (its pane showing `plane`, in a strip). */
export function resetAttr(desk: string, item: string, plane = ""): string {
	return JSON.stringify([desk, item, plane]);
}

export const sidebarRule: AnchorRule = (href, gesture, anchor, event) => {
	const reset = anchor.getAttribute(RESET_ATTR);
	if (reset) {
		const [desk, item, plane] = JSON.parse(reset) as [string, string, string];
		resetItem(desk, item, plane);
		return true;
	}
	const pane = anchor.closest(`[${PANE_ATTR}]`)?.getAttribute(PANE_ATTR);
	const hit = pane ? shapeOfHref(href, knownDesks()) : null;
	if (pane && hit?.shape.kind === "item") {
		openPane(hit.shape.desk, hit.shape.item, pane);
		return true;
	}
	return linkRule(href, gesture, anchor, event);
};

/** Route the sidebar's links under `ref` through `sidebarRule`. */
export function useSidebarLinks(ref: RefObject<HTMLElement | null>): void {
	useAnchorCatcher(ref, sidebarRule);
}
