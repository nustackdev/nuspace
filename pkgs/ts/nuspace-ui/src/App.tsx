// The root: open the socket, wait for the tree, then draw the shell.
//
// The socket is opened here and nowhere else. What it is doing is read through
// `useConnectionStatus` by whoever draws it, so a reconnect never re-renders
// the shell.

import { Spinner, TooltipProvider } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./core/connection";
import { useBooted } from "./core/surfaces";
import { shellBooting } from "./design";
import { Shell } from "./shell/Shell";

export function App() {
	useNuspaceConnection();
	const booted = useBooted();

	if (!booted) {
		return (
			<div className={shellBooting}>
				<Spinner size="sm" tone="neutral" label="Connecting" />
				Waiting for the tree...
			</div>
		);
	}

	return (
		<TooltipProvider delayDuration={1000} skipDelayDuration={300}>
			<Shell />
		</TooltipProvider>
	);
}
