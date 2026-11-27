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

/**
 * The room a scrolled list leaves at its end for the floating buttons: the
 * home indicator, the buttons' 16px offset, their 48px, and 16px more, so
 * the last row scrolls fully clear of them. Padded on the content, not on
 * the scroller: a scroller's own end padding is dropped by some engines
 * (WebKit, a flex scroller), the content's never is.
 */
export const mobileFabClear = "pb-[calc(env(safe-area-inset-bottom)+80px)]";

/* ============================== The header ================================ */

/*
 * One header for every screen (../mobile/Header.tsx), drawn on the sidebar
 * rows' grid, so its icon and its buttons sit in the rows' columns:
 *
 *   | gutter 8 | pad 12 | lead 32 | title ............ | action 44 ... | gutter 8 |
 *
 * 56px tall under the top safe area (the screen's own padding), out of the
 * scroller: what scrolls goes under its bottom edge and the header stays.
 */

/** The header: 56px, the rows' left edge and right gutter. */
export const mobileHeader = "flex h-14 w-full min-w-0 shrink-0 items-center pr-2 pl-5 select-none";

/** Its title: 18px, one line, truncating. */
export const mobileHeaderTitle =
	"min-w-0 flex-1 truncate text-[1.125rem] leading-tight font-semibold text-text-primary";

/** Its actions, at the right edge, each one trail lane wide. */
export const mobileHeaderActions = "flex shrink-0 items-center";

/** An action: a 44px tap target, its glyph 20px, dimmed when it cannot act. */
export const mobileHeaderButton = cn(
	"flex size-11 shrink-0 items-center justify-center rounded-lg",
	"text-text-muted active:bg-bg-press-strong [&_svg]:size-5",
);

/** A figure between actions, eg the pager's n/m. */
export const mobileHeaderCount = "shrink-0 px-0.5 text-sm text-text-muted tabular-nums";

/**
 * The desk's title: its name, dimmed, then the pane's title. The name takes
 * at most 40%, so the pane's title, the one that changes, always has room.
 */
export const mobileDeskTitle = "flex min-w-0 flex-1 items-baseline";
export const mobileDeskTitleDesk = "max-w-[40%] shrink-0 truncate text-text-muted";
export const mobileDeskTitleDot = "shrink-0 px-1.5 text-text-muted";
export const mobileDeskTitlePane = "min-w-0 truncate";

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
 * The rows under the bar, scrolled. `pan-y` again here: a scroller starts
 * its own touch-action, so the panel's does not reach the rows, and the
 * browser would take the sideways drag.
 */
export const mobileSidebarBody =
	"min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-contain px-2";

/** The sections, 16px apart, the last one clear of the floating button. */
export const mobileSidebarList = cn("flex flex-col gap-4", mobileFabClear);

/** A section: its title, then its rows. */
export const mobileSection = "flex flex-col";

/** A section title that folds: the rows' radius and their pressed wash. */
export const mobileSectionFold = "rounded-lg active:bg-bg-press";

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
 * emoji (its box and its type), a strip's composite and a skeleton all come
 * out 20px.
 */
export const mobileRowLead = cn(
	"flex w-8 shrink-0 items-center text-text-muted",
	"[&>svg]:size-5 [&>span]:size-5 [&>span]:text-[1.125rem]",
);

/** The header's lead lane (../mobile/Header.tsx): the rows' own, so the icons line up. */
export const mobileHeaderLead = mobileRowLead;

/**
 * A strip row's lead: its planes' icons in the 20px box every row's icon
 * takes, never bigger. Each cell is placed by ../mobile/sidebar/model.ts
 * `compositeOf` (inline left, top, width, height), on whole pixels so the
 * glyphs stay crisp at 2x and 3x.
 */
export const mobileComposite = "relative block";

/** One cell of a composite, its icon 10px: a lucide glyph or an emoji. */
export const mobileCompositeCell = cn(
	"absolute flex items-center justify-center",
	"[&>svg]:size-2.5 [&>span]:size-2.5 [&>span]:text-[9px]",
);

/** The +N in a composite's last cell: the planes past the first three. */
export const mobileCompositeMore =
	"text-[8px] leading-none font-semibold tracking-tighter text-text-secondary tabular-nums";

/**
 * A strip row's label: its planes' titles on one line, truncating, and the
 * +N of the titles the line cannot show in full after them, never cut.
 */
export const mobileStripLabel = "flex w-full min-w-0 items-baseline";
export const mobileStripTitles = "min-w-0 truncate";
export const mobileStripMore = "shrink-0 pl-1 text-text-muted tabular-nums";

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
 * The body inside it leaves the room for the floating buttons.
 */
export const mobilePlaneScroll =
	"min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain";

/**
 * The plane: no gutters, its cells one under another at the full width, the
 * last one clear of the floating buttons.
 */
export const mobilePlaneBody = cn(
	"flex min-w-0 flex-col gap-doc-cell-gap px-2 pt-4",
	mobileFabClear,
);

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

/** The desk screen: the header, then the pages. */
export const mobileDesk = "relative flex min-h-0 min-w-0 flex-1 flex-col";

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
