// The browser tab: its title and its favicon say what the tab shows.
//
// The tab follows the plane the canvas focuses: a solo plane, a plane
// item's shown plane, or a strip's focused pane. It reads that pane's head
// off the pane's own node (../pane/state.ts), nothing else. On a desk item the desk's
// name follows the plane's title (`Logs · Favorites`); an empty desk, or a
// plane the pane cannot draw, shows the desk's name alone.
//
// With a plane shown the tab carries that plane's title (the pane's own
// fallback when it has none) and, when its icon is an emoji, that emoji as
// the favicon. A lucide icon, or none, keeps the nu logo. No plane open, or
// one the pane cannot draw: the defaults index.html ships. A plane still
// loading changes nothing, so a switch goes from one plane straight to the
// next, like a browser keeping the old title until the new page lands.
//
// The emoji is an SVG data URL written onto fresh copies of the icon links
// index.html declares, and each link keeps its original href on a data attribute so
// going back to the logo is a copy, not a guess. The DOM is only touched when
// what the tab shows changes, so typing in a cell never repaints the favicon.

import { getNode, type Path } from "@nustackdev/ui-core";
import { useTree } from "@nustackdev/ui-kit";
import { useEffect } from "react";
import { useFocusedRoute, useRoute } from "../core/router";
import { planeIcon } from "../icon/parse";
import { TITLE_FALLBACK } from "../pane/Pane";
import { panePath } from "../pane/state";
import type { PaneHead } from "../plane/types";

/** The product name, the title with nothing open. */
export const DEFAULT_TITLE = "nuspace";

/** Between a plane's title and its desk's name. */
export const TITLE_SEP = " · ";

export type Tab = {
	title: string;
	/** The favicon's emoji, null for the nu logo. */
	emoji: string | null;
};

export const DEFAULT_TAB: Tab = { title: DEFAULT_TITLE, emoji: null };

/**
 * What the tab shows for the focused pane's plane, null when there is none
 * to show (nothing open, still loading, absent).
 */
export function tabOf(plane: { title: string; icon: unknown } | null): Tab {
	if (!plane) return DEFAULT_TAB;
	const icon = planeIcon(plane.icon);
	return {
		title: plane.title || TITLE_FALLBACK,
		emoji: icon.kind === "emoji" ? icon.char : null,
	};
}

/**
 * What the tab shows for the focused plane on desk `desk` ("" off a desk):
 * the desk's name after the plane's title. With no plane to show (an empty
 * desk, an absent plane), the desk's name alone, else the defaults.
 */
export function tabFor(plane: { title: string; icon: unknown } | null, desk: string): Tab {
	if (!plane) return desk ? { title: desk, emoji: null } : DEFAULT_TAB;
	const tab = tabOf(plane);
	return desk ? { ...tab, title: `${tab.title}${TITLE_SEP}${desk}` } : tab;
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

/**
 * Point every icon link at the emoji, or back at the logo when null.
 *
 * Each link is replaced, not edited: Chrome does not always repaint the tab
 * when a live link's href changes, most of all on the way back to the logo
 * it already has cached.
 */
function paintFavicon(emoji: string | null): void {
	const href = emoji ? emojiFavicon(emoji) : null;
	for (const old of iconLinks()) {
		const link = old.cloneNode() as HTMLLinkElement;
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
		old.replaceWith(link);
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
 * The focused pane's head, off its own node. Null when there is none to
 * show (nothing open, absent), undefined while it is still loading.
 */
function focusedHead(
	root: Parameters<typeof getNode>[0],
	viewer: Path | null,
	id: string,
): PaneHead | null | undefined {
	if (!viewer || !id) return null;
	const props = getNode(root, panePath(viewer, id))?.props;
	if (props?.absent) return null;
	return props?.head as PaneHead | undefined;
}

/**
 * Keep the tab in step with what the canvas shows. Used once, by the shell.
 * Selects strings, so a cell edit re-renders nothing here.
 */
export function useTab(viewer: Path | null): void {
	const route = useRoute();
	const desk = route.kind === "item" || route.kind === "desk" ? route.name || DEFAULT_TITLE : "";
	const empty = route.kind === "desk";
	const focused = useFocusedRoute();
	// undefined: still loading, leave the tab as it is. null: the defaults.
	const title = useTree((s) => {
		const head = focusedHead(s.root, viewer, focused);
		return head === undefined ? undefined : (head?.title ?? null);
	});
	const icon = useTree((s) => focusedHead(s.root, viewer, focused)?.meta.icon ?? "");
	const loading = !empty && title === undefined;
	const tab = tabFor(empty || title == null ? null : { title, icon }, desk);
	const shownTitle = tab.title;
	const emoji = tab.emoji;

	useEffect(() => {
		if (!loading) applyTab({ title: shownTitle, emoji });
	}, [loading, shownTitle, emoji]);
}
