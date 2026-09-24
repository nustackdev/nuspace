// One pane: a page's frame. The bar on top, the page under it in its own
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
import { closePane, focusPane } from "../app/router";
import { docPageLoading, docTitle, docTitleHead, shellPane, shellPanePage } from "../design";
import type { Notify } from "../page/ops";
import { Page } from "../page/Page";
import type { ActivePage, SlashSnippet } from "../page/types";
import { PaneBar } from "./PaneBar";

// The Plane the server inits with no name shows this instead. A placeholder,
// muted, so it cannot be mistaken for a title that is really there.
export const TITLE_FALLBACK = "Untitled";

export function Pane({
	viewerPath,
	pageId,
	page,
	snippets,
	notify,
	onMeta,
	split,
	divided,
	focused,
	style,
}: {
	viewerPath: Path;
	pageId: string;
	/** Null until this Plane's `set_page` lands. */
	page: ActivePage | null;
	snippets: SlashSnippet[];
	notify: Notify;
	/** Change this page's settings. */
	onMeta: (pageId: string, patch: Record<string, unknown>) => void;
	/** More than one pane is open: no bar, the tab bar stands in for it. */
	split: boolean;
	/** Draws the divider on its left edge. */
	divided: boolean;
	focused: boolean;
	/** The pane's share of the strip. See ../main/usePaneWidths.ts. */
	style: React.CSSProperties;
}) {
	// Capture, so a click that a block handles and stops still moves focus,
	// and a caret tabbed into the pane counts the same as a click.
	const claim = useCallback(() => focusPane(pageId), [pageId]);
	const title = page?.title || TITLE_FALLBACK;
	const wide = page?.meta.full_width === true;
	const compact = page?.meta.compact === true;

	return (
		<section
			data-pane={pageId}
			className={shellPane(divided, split && !focused)}
			style={style}
			aria-label={title}
			onPointerDownCapture={claim}
			onFocusCapture={claim}
		>
			{split ? null : (
				<PaneBar
					title={title}
					meta={page?.meta ?? null}
					onMeta={(patch) => onMeta(pageId, patch)}
					onClose={() => closePane(pageId)}
				/>
			)}
			<div className={shellPanePage}>
				{page == null ? (
					<div className={docPageLoading}>
						<Spinner size="sm" tone="neutral" label="Loading" />
						loading...
					</div>
				) : (
					<>
						<header className={docTitleHead(wide, compact)}>
							<h1 className={docTitle(compact)} data-placeholder={TITLE_FALLBACK}>
								{page.title}
							</h1>
						</header>
						<Page
							viewerPath={viewerPath}
							page={page}
							snippets={snippets}
							editable={page.meta.editable}
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
