// RouteRef -- the browser answering "which Plane am I on?".
//
// Mirrors `nuspace/web/route.py`. The route is per view, so the browser owns it
// outright and the server keeps no copy: an arm that needs to know which Plane
// this connection is looking at sends a `read` frame, and this answers it off
// the live URL.
//
// Pulled, never pushed. There is no `write` handler, so a server that tried to
// move somebody's tab gets the store's "op not supported" rather than a silent
// navigation; and there is no notify on navigation either, because every arm
// that cares reads the route when it runs. `pages.open` is what tells the
// server a tab moved, and it is a ViewerRef op, not a route one.
//
// The shape is `{page_ids, page_id}`: every Plane the URL names, left to
// right, and the leftmost as `page_id` for a reader that wants just one, empty
// when it names none. An empty kv key segment is not a key, so the server
// treats "" as "no Plane" rather than as something to look up.
//
// Not `NavRef`: the kit registers one of those, the last registration for a
// name wins, and a bare `NavRef` here would replace it without saying so.
//
// `read` is the one handler, and it earns its place: the default answers with
// `props.value`, and this ref has no stored value to answer with. A mirrored
// route is a stale route the moment somebody uses the back button.

import { OPS } from "@nustackdev/ui-core";
import type { NodeEntry } from "@nustackdev/ui-kit";
import { currentRoutes } from "../app/router";

export type Route = { page_ids: string[]; page_id: string };

/** Structural: bound to the URL, renders nothing into the visible tree. */
function RouteView() {
	return null;
}

export const RouteRef: NodeEntry = {
	component: RouteView,
	handlers: {
		read: (ctx) => {
			// Read directly off the URL: the read path is not in a render.
			const page_ids = currentRoutes();
			ctx.send(OPS.read, { page_ids, page_id: page_ids[0] ?? "" } satisfies Route, ctx.frame.id);
		},
	},
};
