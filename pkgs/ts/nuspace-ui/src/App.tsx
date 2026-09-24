// The app: open the socket, wait for the tree, then draw the shell.
//
// The socket is opened here and nowhere else. What it is doing is read through
// `useConnectionStatus` by whoever draws it, so a reconnect never re-renders
// the shell.

import { Spinner, TooltipProvider } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./app/connection";
import { useBooted } from "./app/surfaces";
import { shellBooting } from "./design";
import { Shell } from "./shell/Shell";

export function App() {
	useNuspaceConnection();
	const booted = useBooted();

	if (!booted) {
		return (
			<div className={shellBooting}>
				<Spinner size="sm" tone="neutral" label="Connecting" />
				waiting for the tree...
			</div>
		);
	}

	return (
		<TooltipProvider>
			<Shell />
		</TooltipProvider>
	);
}
