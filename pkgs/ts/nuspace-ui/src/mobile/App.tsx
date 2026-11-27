// The mobile root (../shells.ts picks it on a touch device): open the socket
// and draw the mobile shell, and beside it the one confirm dialog. Same lower
// layer as desktop's ../App.tsx: the connection, the router, the desk and
// pane state, the refs. No keyboard shortcuts sheet: a phone has no keys.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "../core/connection";
// The stored theme, painted before the first frame. Desktop paints it from
// its sidebar footer; the phone has no footer.
import "../core/theme";
import { admits } from "../main/state";
import { ConfirmDialog } from "../shell/ConfirmDialog";
// The node types this shell draws, before the socket opens (./refs.ts).
import "./refs";
import { MobileShell } from "./Shell";

export function MobileApp() {
	useNuspaceConnection(admits);

	return (
		<TooltipProvider delayDuration={800} skipDelayDuration={300}>
			<MobileShell />
			<ConfirmDialog />
		</TooltipProvider>
	);
}
