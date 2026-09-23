// ViewerRef -- whichever Plane the sidebar picked, drawn.
//
// One Viewer, and it never asks what kind of thing it is drawing. It renders
// the Plane's Cells and roots their refs, every Cell the same way.
//
// The one bit it reads off the Plane is `editable`: with it you get the
// controls a document has -- insert, drag, the code toggle, the gutter -- and
// without it the same Cells draw with none of them.
//
// Selection is router-owned: the URL /<plane id> is the cursor, the sidebar
// drives navigate(), and the route effect here ships `page.select`. The bare
// "/" names no Plane, which is a real route and not a loading state.
//
// We never remount on navigation.

import { type NodeEntry, type NodeProps, pathKey, Spinner } from "@nustackdev/ui-kit";
import { useCallback, useEffect } from "react";
import { useRoute } from "../../app/router";
import { notifyOp } from "../../app/wire";
import { docPageLoading, docPageSurface, docTitle, docTitleHead, shellSurface } from "../../design";
import { Canvas } from "./Canvas";
import type { Ops } from "./ops";
import { applyViewerWrite, useSnippets, useViewerValue } from "./state";

// The Plane the server inits with no name shows this instead. A placeholder,
// muted, so it cannot be mistaken for a title that is really there.
const TITLE_FALLBACK = "Untitled";

/** Nothing is open. A fact, not an error, so it says so and stops. */
const NOTHING_OPEN = "pick a Plane";

function ViewerView({ path }: NodeProps) {
	const { page } = useViewerValue(path);
	const snippets = useSnippets(path);
	const planeId = useRoute();
	const key = pathKey(path);

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	useEffect(() => {
		if (!planeId) return;
		notify("page.select", { page_id: planeId });
	}, [planeId, notify]);

	// The route wins over what has landed. A select for "" is never sent, so
	// the last Plane's blocks are still in props and drawing them would show a
	// document the URL says is not open.
	const showing = planeId ? page : null;

	return (
		<div className={shellSurface}>
			<div className={docPageSurface}>
				{!planeId ? (
					<div className={docPageLoading}>{NOTHING_OPEN}</div>
				) : showing == null ? (
					<div className={docPageLoading}>
						<Spinner size="sm" tone="neutral" label="Loading" />
						loading...
					</div>
				) : (
					<>
						<header className={docTitleHead}>
							<h1 className={docTitle} data-placeholder={TITLE_FALLBACK}>
								{showing.title}
							</h1>
						</header>
						<Canvas
							refPath={path}
							page={showing}
							snippets={snippets}
							editable={showing.editable}
							notify={notify}
						/>
					</>
				)}
			</div>
		</div>
	);
}

export const ViewerRef: NodeEntry = {
	component: ViewerView,
	handlers: { write: (ctx, payload) => ctx.update((props) => applyViewerWrite(props, payload)) },
};
