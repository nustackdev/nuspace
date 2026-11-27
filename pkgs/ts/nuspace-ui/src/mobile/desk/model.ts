// The desk screen's pure parts: the pages a desk item shows, which one a
// scroll stands on, and the counter.
//
// A desk item's pages are its panes in reading order: column by column, top
// to bottom, the order the router's routes and the sidebar's strip row use.
// A plane item is one page.

import type { Item, Link } from "../../desk/model";
import { shownLinks } from "../../desk/model";

/** The pages item `item` shows, in reading order. */
export function pagesOf(item: Item): Link[] {
	return shownLinks(item);
}

/** The page showing plane `plane`, 0 when no page does. */
export function pageOf(pages: readonly Link[], plane: string): number {
	const at = pages.findIndex((p) => p.plane === plane);
	return Math.max(0, at);
}

/** The page a pager scrolled to `left` stands on, `width` a page, `count` pages. */
export function pageAt(left: number, width: number, count: number): number {
	if (count <= 0 || width <= 0) return 0;
	return Math.min(count - 1, Math.max(0, Math.round(left / width)));
}

/** Where the pager stands, "2/3"; null for a single page, which has no pager. */
export function pageCount(index: number, count: number): string | null {
	return count > 1 ? `${index + 1}/${count}` : null;
}
