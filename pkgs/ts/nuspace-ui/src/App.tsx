// The root: open the socket and draw the shell, and beside it the one confirm
// dialog and the keyboard shortcuts sheet.
//
// The shell draws at once, before the tree lands: its sidebar and viewer stand
// in as skeletons until their nodes arrive (see ./shell/Shell.tsx), so the
// window has its layout from the first frame.
//
// The socket is opened here and nowhere else. What it is doing is read through
// `useConnectionStatus` by whoever draws it, so a reconnect never re-renders
// the shell.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./core/connection";
import { ConfirmDialog } from "./shell/ConfirmDialog";
import { KeysDialog } from "./shell/KeysDialog";
import { Shell } from "./shell/Shell";

export function App() {
	useNuspaceConnection();

	return (
		<TooltipProvider delayDuration={800} skipDelayDuration={300}>
			<Shell />
			<ConfirmDialog />
			<KeysDialog />
		</TooltipProvider>
	);
}
