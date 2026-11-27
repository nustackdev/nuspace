// What a pane calls its plane when the plane gives no name, or is not there.
// Shared by desktop's pane (./Pane.tsx) and the phone's plane screen
// (../mobile/plane/MobilePlane.tsx), so neither imports the other.

import type { AbsentReason } from "../plane/types";
import { NOT_FOUND_TEXT } from "./NotFound";

// The Plane the server inits with no name shows this instead. A placeholder,
// muted, so it cannot be mistaken for a title that is really there.
export const TITLE_FALLBACK = "Untitled";

/** What an absent pane says, per reason. */
export const ABSENT_TEXT: Record<AbsentReason, string> = {
	missing: NOT_FOUND_TEXT.plane,
	headless: "This plane runs without a view",
};
