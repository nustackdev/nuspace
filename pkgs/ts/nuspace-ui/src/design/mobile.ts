// Mobile shell class recipes (../mobile).
//
// The phone's frame: one screen at a time, the visible height (`dvh`, not the
// screen behind the browser bars), nothing under the notch or the home
// indicator. Same ground and the same kit roles as desktop; only the frame
// differs. See go/projects/nustackdev/design/language/mobile.md.

import { cn } from "@nustackdev/ui-kit";

/** The window: the visible height, the safe areas left clear, no tap flash. */
export const mobileRoot = cn(
	"relative flex h-dvh flex-col overflow-hidden bg-nuspace-page text-text-primary",
	"pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)]",
	"[-webkit-tap-highlight-color:transparent] [touch-action:manipulation]",
);

/** The one screen the shell shows, the rest of the height. */
export const mobileMain = "relative flex min-h-0 min-w-0 flex-1 flex-col";

/** The plane on the screen: full width, its own scroller. */
export const mobileScreen = "relative flex min-h-0 min-w-0 flex-1";

/** A whole-screen note (pending, missing, booting). */
export const mobileMissing = "min-h-0 flex-1";

/**
 * The disconnect banner: a small pill floating over the top of the screen,
 * clear of the notch, there only while the connection is down. It takes no
 * taps, so whatever is under it still works.
 */
export const mobileBanner = cn(
	"pointer-events-none absolute inset-x-0 z-40 flex justify-center",
	"top-[calc(env(safe-area-inset-top)+8px)]",
);

/* ============================== Floating buttons ========================== */

/**
 * A floating button: 48px round, over everything but the sheets, clear of
 * the home indicator. The sidebar's bottom left, the plane's + bottom right,
 * both under the thumb.
 */
export function mobileFab(side: "left" | "right"): string {
	return cn(
		"fixed z-40 size-12 rounded-full shadow-floating",
		"bottom-[calc(env(safe-area-inset-bottom)+16px)]",
		side === "left"
			? "left-[calc(env(safe-area-inset-left)+16px)]"
			: "right-[calc(env(safe-area-inset-right)+16px)]",
		"[&_svg]:size-5",
	);
}

/* ============================== The sidebar screen ======================== */

/**
 * The sidebar screen: full screen over the plane, slid in from the left.
 * Closed, it waits off screen, hidden and out of the tab order, so it opens
 * without a mount. It takes the sideways drag itself (`pan-y`).
 */
export function mobileSidebar(open: boolean): string {
	return cn(
		"fixed inset-0 z-30 flex flex-col bg-bg-sunken text-text-primary",
		"pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)]",
		"touch-pan-y transition-[transform,visibility] duration-slow",
		open ? "visible translate-x-0 ease-out" : "invisible -translate-x-full ease-in",
	);
}

/**
 * Its top bar: drawn as a row (../mobile/sidebar/Row.tsx), the wordmark at
 * the icons' edge and the + in the trail lane. The body's gutter, so the bar's
 * + lines up with every row's.
 */
export const mobileSidebarHead = "flex h-14 shrink-0 items-center px-2";

/**
 * The rows under the bar, scrolled, clear of the floating button at the
 * bottom. `pan-y` again here: a scroller starts its own touch-action, so the
 * panel's does not reach the rows, and the browser would take the sideways
 * drag.
 */
export const mobileSidebarBody = cn(
	"flex min-h-0 flex-1 touch-pan-y flex-col gap-4 overflow-y-auto overscroll-contain px-2",
	"pb-[calc(env(safe-area-inset-bottom)+88px)]",
);

/** A section: its title, then its rows. */
export const mobileSection = "flex flex-col";

/*
 * The row anatomy, one for every line on the sidebar screen:
 *
 *   | pad 12 | indent 32 a level | lead 32 | label | trail 44 |
 *
 * The lead is a 20px icon and the 12px gap to the label, so a child's icon
 * sits under its parent's label. The trail is a 44px tap lane at the right
 * edge holding every chevron and every +, one column down the screen.
 */

/** The row's lanes, as the row's kind draws them. */
const ROW_KIND = {
	row: "min-h-11 rounded-lg text-base text-text-secondary",
	note: "min-h-11 text-sm text-text-muted",
	head: "min-h-11 text-sm font-medium text-text-muted",
	bar: "h-14 text-base",
} as const;

/**
 * One row, 44px: sized for the thumb for real. The same washes as desktop's
 * rows, pressed rather than hovered. No callout or text selection on a
 * long-press. Only rows (not notes or titles) take the wash.
 */
export function mobileRow(
	kind: keyof typeof ROW_KIND,
	selected: boolean,
	className?: string,
): string {
	return cn(
		"relative flex w-full min-w-0 items-center text-left select-none",
		"[-webkit-touch-callout:none]",
		ROW_KIND[kind],
		kind === "row" &&
			(selected ? "bg-bg-press text-text-primary active:bg-bg-press-strong" : "active:bg-bg-press"),
		className,
	);
}

/** Left pad for a row at `depth`, as an inline style: 12px, then one lead (32px) a level. */
export function mobileIndent(depth: number): { paddingLeft: string } {
	return { paddingLeft: `calc(0.75rem + ${depth} * 2rem)` };
}

/**
 * The lead lane: 32px, its icon 20px at the lane's start, whatever the icon
 * is. The lane sets the size, not the call site: a lucide glyph, a plane's
 * emoji (its box and its type) and a skeleton all come out 20px.
 */
export const mobileRowLead = cn(
	"flex w-8 shrink-0 items-center text-text-muted",
	"[&_svg]:size-5 [&>span]:size-5 [&>span]:text-[1.125rem]",
);

/** A row's label, truncating. */
export const mobileRowLabel = "min-w-0 flex-1 truncate";

/** The lead and label as one link, inside a row with its own trail button. */
export const mobileRowMain = "flex min-h-11 min-w-0 flex-1 items-center outline-hidden";

/** The trail lane: 44px at the row's right edge, the glyph centred. */
export const mobileRowTrail = "flex w-11 shrink-0 items-center justify-center self-stretch";

/** A tap target filling the trail lane (a + or a chevron button), its glyph 20px. */
export const mobileTrailButton = cn(
	"flex size-11 shrink-0 items-center justify-center rounded-lg",
	"text-text-muted active:bg-bg-press-strong [&_svg]:size-5",
);

/** The chevron of a folding row, turned down when open: one glyph and one turn for all. */
export function mobileChevron(open: boolean): string {
	return cn(
		"size-5 shrink-0 text-text-muted transition-transform duration-fast",
		open && "rotate-90",
	);
}

/* ============================== Sheets ==================================== */

/** A package's title between a sheet's rows. */
export const mobileSheetGroup =
	"pt-4 pb-1 text-sm font-medium text-text-muted select-none first:pt-0";

/** A muted line in a sheet. */
export const mobileSheetNote = "py-3 text-sm text-text-muted";

/** A sheet's form: room for the field's focus ring inside the scroller. */
export const mobileSheetForm = "pt-1";

/** The one input of a sheet (rename): touch sized, 16px text so iOS does not zoom. */
export const mobileSheetInput = "h-11 text-base";

/** A row's label inside a sheet, truncating. */
export const mobileSheetLabel = "min-w-0 flex-1 truncate";

/** The toasts: on top, clear of the notch, the keyboard and the floating buttons. */
export const mobileToaster = "top-[env(safe-area-inset-top)] bottom-auto max-w-none";

/* ============================== The plane screen ========================== */

/**
 * The plane's scroller: the whole screen under the banner, native scroll.
 * Its bottom pads clear of the floating buttons, so the last cell can be
 * scrolled above them.
 */
export const mobilePlaneScroll = cn(
	"min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain",
	"pb-[calc(env(safe-area-inset-bottom)+88px)]",
);

/** The plane: no gutters, its cells one under another at the full width. */
export const mobilePlaneBody = "flex min-w-0 flex-col gap-doc-cell-gap px-2 pt-4";

/** The title band: the plane above (when there is one), then the icon and the title. */
export const mobilePlaneHead = "flex min-w-0 flex-col gap-0.5 px-doc-cell pb-3";

/** The plane above the title, small and muted. */
export const mobilePlaneTrail = "truncate text-sm text-text-muted";

/** The icon and the title side by side; a long title wraps under itself. */
export const mobilePlaneTitleLine = "flex min-w-0 items-start gap-2";

/** The title, read-only: rename lives on the sidebar's long-press. */
export const mobilePlaneTitle = `${cn("min-w-0 flex-1 break-words font-bold text-text-primary")} text-2xl`;

/** The plane's icon, on the title's first line. */
export const mobilePlaneIcon = "mt-1.5 shrink-0 text-text-muted";

/** A plane with no cells yet: a muted note pointing at the +. */
export const mobilePlaneEmpty = "px-doc-cell py-6 text-sm text-text-muted";

/**
 * One cell, the full width, its desktop pad. A long-press opens its sheet, so
 * no callout and no selection on its output; what you type in (an input, a
 * text area, a document) still selects. The one pressed carries the same
 * wash as a selected cell on desktop while its sheet is open.
 */
export function mobileCell(pressed: boolean): string {
	return cn(
		"relative min-w-0 rounded-md p-doc-cell",
		"select-none [-webkit-touch-callout:none]",
		"[&_:is(input,textarea,[contenteditable=true])]:select-text",
		"transition-colors duration-fast ease-out",
		pressed && "bg-doc-hover",
	);
}

/** The source screen's code: the rest of the screen under its title, scrolled inside. */
export const mobileSourceBody = "min-h-0 flex-1 overflow-y-auto overscroll-contain";

/** The source screen's title: the cell's id, set in mono. */
export const mobileSourceTitle = "truncate pr-10 font-mono text-base font-medium";

/* ============================== The desk screen =========================== */

/** The desk screen: its bar, its dots, then the pages. */
export const mobileDesk = "relative flex min-h-0 min-w-0 flex-1 flex-col";

/** The desk's top bar: the desk's name, the pane's title, and n/m at its end. */
export const mobileDeskBar = "flex h-12 shrink-0 items-center gap-1.5 px-3 select-none";

/** The desk's name in the bar. */
export const mobileDeskName =
	"shrink-0 max-w-[45%] truncate text-base font-semibold text-text-primary";

/** The pane's title after the desk's name, muted. */
export const mobileDeskPane = "min-w-0 flex-1 truncate text-sm text-text-muted";

/** Where the pager stands: n/m. */
export const mobileDeskCount = "shrink-0 text-sm text-text-muted tabular-nums";

/** The dots under the bar, one per pane: where you are, not a control. */
export const mobileDeskDots = "flex shrink-0 items-center justify-center gap-1.5 pb-1.5";

/** One dot; the one on screen is a short bar. */
export function mobileDeskDot(on: boolean): string {
	return cn(
		"h-1.5 rounded-full transition-[width,background-color] duration-fast ease-out",
		on ? "w-4 bg-text-primary" : "w-1.5 bg-border-strong",
	);
}

/**
 * The pager: the browser's own sideways scroll, one page a snap. Each page
 * scrolls up and down inside itself, so the two axes never fight: the
 * browser locks a drag to the axis it starts on.
 */
export const mobileDeskPager = cn(
	"flex min-h-0 min-w-0 flex-1 snap-x snap-mandatory overflow-x-auto overflow-y-hidden",
	"overscroll-x-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
);

/** One page: the full width, held at its snap. */
export const mobileDeskPage = "flex h-full w-full min-w-0 shrink-0 snap-start snap-always";
