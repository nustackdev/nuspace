// PaneRef: one open plane, at `<viewer>/panes/<plane>`. Mirrors
// `nuspace/web/viewer/ref.py` `PaneRef`. The write body is ../pane/state.ts.
//
// Draws nothing through the tree: the desk (../main/Desk.tsx) puts each pane
// where its layout says, and the pane (../pane/Pane.tsx) reads this node by
// its path. A node of this type only holds what the pane shows.

import type { NodeEntry } from "@nustackdev/ui-kit";
import { applyPaneWrite } from "../pane/state";

export const PaneRef: NodeEntry = {
	component: () => null,
	handlers: { write: (ctx, payload) => ctx.update((props) => applyPaneWrite(props, payload)) },
};
