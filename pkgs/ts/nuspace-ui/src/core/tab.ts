// The browser tab: its title and its favicon follow the focused pane.
//
// With a plane open the tab carries that plane's title (the pane's own
// fallback when it has none) and, when its icon is an emoji, that emoji as
// the favicon. A lucide icon, or none, keeps the nu logo. No plane open, or
// one the pane cannot draw: the defaults index.html ships. A plane still
// loading changes nothing, so a switch goes from one plane straight to the
// next, like a browser keeping the old title until the new page lands.
// With a split it is the focused pane's plane, the one a sidebar click
// replaces.
//
// The emoji is an SVG data URL written onto the icon links index.html
// declares, and each link keeps its original href on a data attribute so
// going back to the logo is a copy, not a guess. The DOM is only touched when
// what the tab shows changes, so typing in a cell never repaints the favicon.

import { getNode, type Path } from "@nustackdev/ui-core";
import { useTree } from "@nustackdev/ui-kit";
import { useEffect } from "react";
import { planeIcon } from "../icon/parse";
import { TITLE_FALLBACK } from "../pane/Pane";
import type { ActivePlane } from "../plane/types";
import { useRegisteredIcon } from "../sidebar/state";
import { useFocusedRoute } from "./router";

/** The product name, the title with nothing open. */
export const DEFAULT_TITLE = "nuspace";

export type Tab = {
	title: string;
	/** The favicon's emoji, null for the nu logo. */
	emoji: string | null;
};

export const DEFAULT_TAB: Tab = { title: DEFAULT_TITLE, emoji: null };

/**
 * What the tab shows for the focused pane's plane, null when there is none
 * to show (nothing open, still loading, absent). `registered` is its
 * registered Plane's icon.
 */
export function tabOf(plane: { title: string; icon: unknown } | null, registered = ""): Tab {
	if (!plane) return DEFAULT_TAB;
	const icon = planeIcon(plane.icon, registered);
	return {
		title: plane.title || TITLE_FALLBACK,
		emoji: icon.kind === "emoji" ? icon.char : null,
	};
}

function escapeXml(text: string): string {
	return text.replace(/[<>&"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

/** An emoji as a favicon: one <text> filling a square SVG, as a data URL. */
export function emojiFavicon(char: string): string {
	const svg =
		'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
		'<text x="50" y="50" font-size="88" text-anchor="middle" dominant-baseline="central">' +
		`${escapeXml(char)}</text></svg>`;
	return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

// -- The DOM -----------------------------------------------------------------

let shown: Tab = DEFAULT_TAB;

function iconLinks(): HTMLLinkElement[] {
	return Array.from(document.head.querySelectorAll<HTMLLinkElement>('link[rel="icon"]'));
}

/** Point every icon link at the emoji, or back at the logo when null. */
function paintFavicon(emoji: string | null): void {
	const href = emoji ? emojiFavicon(emoji) : null;
	for (const link of iconLinks()) {
		if (link.dataset.logo === undefined) {
			link.dataset.logo = link.getAttribute("href") ?? "";
			link.dataset.logoType = link.type;
			link.dataset.logoSizes = link.getAttribute("sizes") ?? "";
		}
		if (href) {
			link.type = "image/svg+xml";
			link.setAttribute("sizes", "any");
			link.href = href;
		} else {
			link.type = link.dataset.logoType ?? "";
			if (link.dataset.logoSizes) link.setAttribute("sizes", link.dataset.logoSizes);
			else link.removeAttribute("sizes");
			link.setAttribute("href", link.dataset.logo);
		}
	}
}

/** Show `tab`. A no-op for whatever part of it is already showing. */
export function applyTab(tab: Tab): void {
	if (tab.title !== shown.title) document.title = tab.title;
	if (tab.emoji !== shown.emoji) paintFavicon(tab.emoji);
	shown = tab;
}

// -- The hook ----------------------------------------------------------------

/**
 * The focused pane's plane, off the viewer node. Null when there is none to
 * show (nothing open, absent), undefined while it is still loading.
 */
function focusedPlane(root: Parameters<typeof getNode>[0], viewer: Path | null, id: string) {
	if (!viewer || !id) return null;
	const props = getNode(root, viewer)?.props;
	if ((props?.absent as Record<string, unknown> | undefined)?.[id]) return null;
	return (props?.planes as Record<string, ActivePlane> | undefined)?.[id];
}

/**
 * Keep the tab in step with the focused pane. Used once, by the shell.
 * Selects strings, so a cell edit re-renders nothing here.
 */
export function useTab(viewer: Path | null, sidebar: Path | null): void {
	const focused = useFocusedRoute();
	// undefined: still loading, leave the tab as it is. null: the defaults.
	const title = useTree((s) => {
		const plane = focusedPlane(s.root, viewer, focused);
		return plane === undefined ? undefined : (plane?.title ?? null);
	});
	const icon = useTree((s) => focusedPlane(s.root, viewer, focused)?.meta.icon ?? "");
	const registered = useRegisteredIcon(sidebar, focused);
	const loading = title === undefined;
	const tab = tabOf(title == null ? null : { title, icon }, registered);
	const shownTitle = tab.title;
	const emoji = tab.emoji;

	useEffect(() => {
		if (!loading) applyTab({ title: shownTitle, emoji });
	}, [loading, shownTitle, emoji]);
}
