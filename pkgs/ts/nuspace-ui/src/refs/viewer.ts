// ViewerRef: the node type the desk area is mounted as. Mirrors
// `nuspace/web/viewer`. The component is ../main/Desk.tsx and the write body is
// ../main/state.ts; the only thing said here is that a write is judged against
// the Planes the router has open right now.

import type { NodeEntry } from "@nustackdev/ui-kit";
import { currentRoutes } from "../core/router";
import { Desk } from "../main/Desk";
import { applyViewerWrite } from "../main/state";

export const ViewerRef: NodeEntry = {
	component: Desk,
	handlers: {
		write: (ctx, payload) =>
			ctx.update((props) => applyViewerWrite(props, payload, currentRoutes())),
	},
};
