// The root: open the socket, wait for the tree, then draw the shell, and the
// one confirm dialog beside it.
//
// The socket is opened here and nowhere else. What it is doing is read through
// `useConnectionStatus` by whoever draws it, so a reconnect never re-renders
// the shell.

import { EmptyState, Spinner, TooltipProvider } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./core/connection";
import { useBooted } from "./core/surfaces";
import { shellBooting } from "./design";
import { ConfirmDialog } from "./shell/ConfirmDialog";
import { Shell } from "./shell/Shell";

export function App() {
	useNuspaceConnection();
	const booted = useBooted();

	if (!booted) {
		return (
			<EmptyState
				className={shellBooting}
				icon={<Spinner size="sm" tone="neutral" label="Connecting" />}
			>
				Waiting for the tree...
			</EmptyState>
		);
	}

	return (
		<TooltipProvider delayDuration={800} skipDelayDuration={300}>
			<Shell />
			<ConfirmDialog />
		</TooltipProvider>
	);
}
