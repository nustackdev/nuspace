// Tab bar class recipes: the strip of tabs over a split, one per pane.
//
// Only drawn with two or more panes, and then it replaces every pane's own bar
// (./pane.ts): one title, one `...` and one close per pane, in one place.
//
// Flat, hairline chrome, `h-chrome` tall so its bottom rule runs straight on
// from the rail header's. Tabs are a fixed `w-tab` and cut their title off
// with an ellipsis.
//
// Focus is a surface, not a line. The bar and every tab but the active one
// sit a step down on `bg-sunken`, like the unfocused panes under them; the
// active tab keeps the canvas, and so does its pane (shell.ts). One
// continuous bottom rule runs under the whole bar, the active tab included,
// level with the rail header's, and a rule separates every tab. Both are
// `border-default`, not the rail's `border-subtle`: in light, subtle is the
// same gray as `bg-sunken`, so on the inactive tabs it vanished.
//
// Everything resolves to kit L2/L4 semantic names or the doc-* names in
// ./tokens.css. No raw hex, nothing off the 4px grid.
//
// Source docs (do not paraphrase without re-reading):
//   go/projects/nustackdev/design/primitives.md     §Tabs
//   go/projects/nustackdev/design/space-radius.md   §1 grid, §2 radius
//   go/projects/nustackdev/design/palette.md        §2.1 surfaces, §2.2 text tiers
//   go/projects/nustackdev/design/motion.md         §3 hover, focus ring
//   go/projects/nustackdev/design/a11y.md           §3 Tabs keyboard, focus ring

import { cn } from "@nustackdev/ui-kit";

/**
 * The bar. Scrolls sideways when the tabs overflow, with no scrollbar drawn,
 * the same way the strip of panes under it does.
 */
export const tabBar = cn(
	"flex h-chrome shrink-0 items-stretch bg-bg-sunken",
	"border-b border-border-default",
	"overflow-x-auto overflow-y-hidden overscroll-x-contain",
	"[scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
);

/**
 * One tab: the title and its two buttons on one fixed-width cell, a hairline
 * on its right edge. The cell paints hover, so the wash spans the buttons too.
 *
 * The active one is the canvas, the same surface as its pane; the rest let
 * the bar's sunken surface through. `duration-fast`; the kit's reduced-motion
 * rule flattens it to instant.
 */
export function tabCell(active: boolean): string {
	return cn(
		"group/tab relative flex w-tab shrink-0 items-center gap-0.5",
		"border-r border-border-default pr-1",
		"transition-colors duration-fast ease-out",
		active
			? "bg-bg-canvas text-text-primary"
			: "text-text-secondary hover:bg-doc-hover hover:text-text-primary",
	);
}

/**
 * The tab itself (role=tab): the title, filling the cell. The ring is inset,
 * because the bar's own overflow clips the kit's 2px offset.
 */
export const tabTrigger = cn(
	"flex h-full min-w-0 flex-1 cursor-default select-none items-center pl-3",
	"text-left text-sm",
	"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
);

export const tabTitle = "min-w-0 flex-1 truncate";

/**
 * The `...` and close. Revealed on hover, on keyboard focus inside the tab,
 * while the menu is open, and always on the active tab.
 */
export function tabActions(active: boolean): string {
	return cn(
		"flex shrink-0 items-center gap-0.5",
		"transition-opacity duration-fast ease-out",
		active
			? "opacity-100"
			: "opacity-0 group-hover/tab:opacity-100 group-focus-within/tab:opacity-100 has-[[data-state=open]]:opacity-100",
	);
}

/** The inline rename box, where the title was. */
export const tabInputBox = "flex h-full min-w-0 flex-1 items-center pl-2";

export const tabInput = cn("h-6 min-w-0 flex-1 px-1 py-0 text-sm", "focus-visible:ring-offset-0");
