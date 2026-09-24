// One pane: a plane's frame. The bar on top, the plane under it in its own
// scroll host. With a split the bar goes: the tab bar over the strip carries
// every pane's title, settings and close instead.
//
// The pane last clicked (or tabbed into) is the focused one: that is the pane
// a plain sidebar click replaces. With more than one pane open the others
// sit on a dimmed surface and the focused one keeps the canvas.

import type { Path } from "@nustackdev/ui-core";
import { Spinner } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useCallback } from "react";
import { closePane, focusPane } from "../core/router";
import { docPlaneLoading, docTitle, docTitleHead, shellPane, shellPanePlane } from "../design";
import type { Notify } from "../plane/ops";
import { Plane } from "../plane/Plane";
import type { ActivePlane, SlashSnippet } from "../plane/types";
import { PaneBar } from "./PaneBar";

// The Plane the server inits with no name shows this instead. A placeholder,
// muted, so it cannot be mistaken for a title that is really there.
export const TITLE_FALLBACK = "Untitled";

export function Pane({
	viewerPath,
	planeId,
	plane,
	snippets,
	notify,
	onMeta,
	split,
	divided,
	focused,
	style,
}: {
	viewerPath: Path;
	planeId: string;
	/** Null until this Plane's `set_plane` lands. */
	plane: ActivePlane | null;
	snippets: SlashSnippet[];
	notify: Notify;
	/** Change this plane's settings. */
	onMeta: (planeId: string, patch: Record<string, unknown>) => void;
	/** More than one pane is open: no bar, the tab bar stands in for it. */
	split: boolean;
	/** Draws the divider on its left edge. */
	divided: boolean;
	focused: boolean;
	/** The pane's share of the strip. See ../main/usePaneWidths.ts. */
	style: React.CSSProperties;
}) {
	// Capture, so a click that a cell handles and stops still moves focus,
	// and a caret tabbed into the pane counts the same as a click.
	const claim = useCallback(() => focusPane(planeId), [planeId]);
	const title = plane?.title || TITLE_FALLBACK;
	const wide = plane?.meta.full_width === true;
	const compact = plane?.meta.compact === true;

	return (
		<section
			data-pane={planeId}
			className={shellPane(divided, split && !focused)}
			style={style}
			aria-label={title}
			onPointerDownCapture={claim}
			onFocusCapture={claim}
		>
			{split ? null : (
				<PaneBar
					planeId={planeId}
					title={title}
					meta={plane?.meta ?? null}
					onMeta={(patch) => onMeta(planeId, patch)}
					onClose={() => closePane(planeId)}
				/>
			)}
			<div className={shellPanePlane}>
				{plane == null ? (
					<div className={docPlaneLoading}>
						<Spinner size="sm" tone="neutral" label="Loading" />
						loading...
					</div>
				) : (
					<>
						<header className={docTitleHead(wide, compact)}>
							<h1 className={docTitle(compact)} data-placeholder={TITLE_FALLBACK}>
								{plane.title}
							</h1>
						</header>
						<Plane
							viewerPath={viewerPath}
							plane={plane}
							snippets={snippets}
							editable={plane.meta.editable}
							wide={wide}
							compact={compact}
							notify={notify}
						/>
					</>
				)}
			</div>
		</section>
	);
}
