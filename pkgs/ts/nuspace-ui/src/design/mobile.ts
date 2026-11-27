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

/** Its top bar: the wordmark, and the + for a new plane. */
export const mobileSidebarHead = "flex h-14 shrink-0 items-center gap-2 pr-2 pl-5";

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

/** A section title: small and muted, an action at its end. */
export const mobileSectionHead =
	"flex h-10 items-center gap-2 pr-0.5 pl-3 text-sm font-medium text-text-muted select-none";

/**
 * One row, 44px: the sidebar is a kit-owned kind of surface, sized for the
 * thumb for real. The same washes as desktop's rows, pressed rather than
 * hovered. No callout or text selection on a long-press.
 */
export function mobileRow(selected: boolean): string {
	return cn(
		"relative flex min-h-11 w-full items-center gap-3 rounded-lg pr-3 text-left text-base select-none",
		"[-webkit-touch-callout:none]",
		selected
			? "bg-bg-press text-text-primary active:bg-bg-press-strong"
			: "text-text-secondary active:bg-bg-press",
	);
}

/** Left pad for a row at `depth`, as an inline style: 12px, then 20px a level. */
export function mobileIndent(depth: number): { paddingLeft: string } {
	return { paddingLeft: `calc(0.75rem + ${depth} * 1.25rem)` };
}

/** A tree row's link: the whole row but its expand button. */
export const mobileRowMain = "flex min-h-11 min-w-0 flex-1 items-center gap-3 outline-hidden";

/** A row's icon. */
export const mobileRowIcon = "size-4.5 shrink-0 text-text-muted";

/** A row's label, truncating. */
export const mobileRowLabel = "min-w-0 flex-1 truncate";

/** A row's trailing note (a strip's pane count). */
export const mobileRowNote = "shrink-0 text-sm text-text-muted tabular-nums";

/** A muted line in place of rows ("No planes inside", an empty desk). */
export const mobileRowEmpty = "flex min-h-11 items-center text-sm text-text-muted select-none";

/** A tree row's expand button: 44px, at the row's end. */
export const mobileTwisty = cn(
	"-mr-3 flex size-11 shrink-0 items-center justify-center rounded-lg",
	"text-text-muted active:bg-bg-press-strong",
);

/** The chevron of an expanding row, at its end, turned down when open. */
export function mobileChevron(open: boolean): string {
	return cn(
		"size-4 shrink-0 text-text-muted transition-transform duration-fast",
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
