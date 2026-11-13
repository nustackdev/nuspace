// NotFound: the canvas's one "not found", drawn as a pane, so a missing
// plane, desk, desk item or a url that is none of them all read the same: a
// pane's frame, no header, and a short line in the body with a way on.
//
// `NotFoundBody` is the body alone: the pane of a plane the server reports
// absent draws it in its own frame (./Pane.tsx), with its Close.

import { Button, EmptyState, ScrollArea } from "@nustackdev/ui-kit";
import type * as React from "react";
import { homeHref, type Missing } from "../core/router";
import {
	docContentTrack,
	docPlaneAbsent,
	paneBody,
	paneBodyScroll,
	paneBodyViewport,
	shellPane,
} from "../design";

/** What each kind of not found says. */
export const NOT_FOUND_TEXT: Record<Missing, string> = {
	plane: "This plane doesn't exist",
	desk: "This desk doesn't exist",
	item: "This desk has no such item",
	page: "This page doesn't exist",
};

/** A not found line in a pane's body, with an action under it. */
export function NotFoundBody({ text, action }: { text: string; action?: React.ReactNode }) {
	return (
		<div className={docPlaneAbsent}>
			<EmptyState className={docContentTrack} action={action}>
				{text}
			</EmptyState>
		</div>
	);
}

/** The way out of a not found that is not on a desk: home. */
export function GoHome() {
	return (
		<Button asChild variant="ghost" size="sm">
			<a href={homeHref()}>Go home</a>
		</Button>
	);
}

/** A whole pane saying `what` was not found, with a way home. */
export function NotFound({ what }: { what: Missing }) {
	return (
		<section className={shellPane} aria-label={NOT_FOUND_TEXT[what]} data-not-found={what}>
			<ScrollArea className={paneBodyScroll} viewportClassName={paneBodyViewport}>
				<div className={paneBody}>
					<NotFoundBody text={NOT_FOUND_TEXT[what]} action={<GoHome />} />
				</div>
			</ScrollArea>
		</section>
	);
}
