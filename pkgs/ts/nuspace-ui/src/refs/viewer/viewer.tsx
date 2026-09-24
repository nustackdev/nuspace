// ViewerRef -- whichever Planes the URL names, drawn side by side.
//
// One Viewer, and it never asks what kind of thing it is drawing. Each pane
// renders one Plane's Cells and roots their refs, every Cell the same way.
//
// The one bit it reads off a Plane is `editable`: with it you get the
// controls a document has -- insert, drag, the code toggle, the gutter -- and
// without it the same Cells draw with none of them.
//
// Selection is router-owned: the URL /<id1>+<id2>+... is the cursor, left to
// right, the sidebar drives it, and the route effect here ships `pages.open`
// with the full list whenever it changes. The bare "/" names no Plane, which
// is a real route and not a loading state.
//
// Each pane is its own scroll host with its own title, close button and
// Canvas, and the pane last clicked is the focused one: that is the pane a
// plain sidebar click replaces. We never remount a pane that stays open.

import type { Path } from "@nustackdev/ui-core";
import { IconButton, type NodeEntry, type NodeProps, pathKey, Spinner } from "@nustackdev/ui-kit";
import { X } from "lucide-react";
import { useCallback, useEffect } from "react";
import { closePane, currentRoutes, focusPane, useFocusedRoute, useRoutes } from "../../app/router";
import { notifyOp } from "../../app/wire";
import {
	docPageLoading,
	docPageSurface,
	docTitle,
	docTitleHead,
	shellPane,
	shellPaneClose,
	shellPaneFocusLine,
	shellPanes,
	shellSurface,
} from "../../design";
import { Canvas } from "./Canvas";
import type { Notify, Ops } from "./ops";
import {
	applyViewerWrite,
	pruneViewer,
	type SlashSnippet,
	useSnippets,
	useViewerValue,
} from "./state";
import type { ActivePage } from "./types";

// The Plane the server inits with no name shows this instead. A placeholder,
// muted, so it cannot be mistaken for a title that is really there.
const TITLE_FALLBACK = "Untitled";

/** Nothing is open. A fact, not an error, so it says so and stops. */
const NOTHING_OPEN = "pick a Plane";

function ViewerView({ path }: NodeProps) {
	const { pages } = useViewerValue(path);
	const snippets = useSnippets(path);
	const routes = useRoutes();
	const focused = useFocusedRoute();
	const key = pathKey(path);
	const routesKey = routes.join("+");

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// The full list, every time it changes and once on load -- an empty one
	// included, so the server stops shipping a Plane nobody has open. Pages
	// and editor state of panes that closed go at the same moment.
	// biome-ignore lint/correctness/useExhaustiveDependencies: routes is compared by its joined key; path by value.
	useEffect(() => {
		notify("pages.open", { page_ids: routes });
		pruneViewer(path, routes);
	}, [routesKey, notify]);

	if (routes.length === 0) {
		return (
			<div className={shellSurface}>
				<div className={docPageSurface}>
					<div className={docPageLoading}>{NOTHING_OPEN}</div>
				</div>
			</div>
		);
	}

	const split = routes.length > 1;
	return (
		<div className={shellPanes}>
			{routes.map((id, i) => (
				<Pane
					key={id}
					refPath={path}
					pageId={id}
					page={pages[id] ?? null}
					snippets={snippets}
					notify={notify}
					divided={i > 0}
					split={split}
					focused={id === focused}
				/>
			))}
		</div>
	);
}

function Pane({
	refPath,
	pageId,
	page,
	snippets,
	notify,
	divided,
	split,
	focused,
}: {
	refPath: Path;
	pageId: string;
	/** Null until this Plane's `set_page` lands. */
	page: ActivePage | null;
	snippets: SlashSnippet[];
	notify: Notify;
	divided: boolean;
	split: boolean;
	focused: boolean;
}) {
	// Capture, so a click that a block handles and stops still moves focus,
	// and a caret tabbed into the pane counts the same as a click.
	const claim = useCallback(() => focusPane(pageId), [pageId]);

	return (
		<section
			className={shellPane(divided)}
			aria-label={page?.title || TITLE_FALLBACK}
			onPointerDownCapture={claim}
			onFocusCapture={claim}
		>
			{split ? <div className={shellPaneFocusLine(focused)} aria-hidden="true" /> : null}
			<IconButton
				variant="ghost"
				size="sm"
				aria-label={`Close ${page?.title || TITLE_FALLBACK}`}
				className={shellPaneClose(split)}
				onClick={() => closePane(pageId)}
			>
				<X />
			</IconButton>
			<div className={docPageSurface}>
				{page == null ? (
					<div className={docPageLoading}>
						<Spinner size="sm" tone="neutral" label="Loading" />
						loading...
					</div>
				) : (
					<>
						<header className={docTitleHead}>
							<h1 className={docTitle} data-placeholder={TITLE_FALLBACK}>
								{page.title}
							</h1>
						</header>
						<Canvas
							refPath={refPath}
							page={page}
							snippets={snippets}
							editable={page.editable}
							notify={notify}
						/>
					</>
				)}
			</div>
		</section>
	);
}

export const ViewerRef: NodeEntry = {
	component: ViewerView,
	handlers: {
		write: (ctx, payload) =>
			ctx.update((props) => applyViewerWrite(props, payload, currentRoutes())),
	},
};
