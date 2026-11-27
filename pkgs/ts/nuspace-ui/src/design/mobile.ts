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
