// ViewerRef: the node type the strip of panes is mounted as. Mirrors
// `nuspace/web/viewer`. The component is ../main/Main.tsx and the write body is
// ../main/state.ts; the only thing said here is that a write is judged against
// the Planes the URL has open right now.

import type { NodeEntry } from "@nustackdev/ui-kit";
import { currentRoutes } from "../core/router";
import { Main } from "../main/Main";
import { applyViewerWrite } from "../main/state";

export const ViewerRef: NodeEntry = {
	component: Main,
	handlers: {
		write: (ctx, payload) =>
			ctx.update((props) => applyViewerWrite(props, payload, currentRoutes())),
	},
};
