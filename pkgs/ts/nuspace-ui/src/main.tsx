import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@nustackdev/ui-kit/styles";
import "./index.css";
import { touchDevice } from "@nustackdev/ui-kit";
import { ensureLanding } from "./core/router";
// Registers the node types both shells share; each shell registers the ones it
// draws when it loads. Both before the socket opens: the store autovivifies a
// node the moment a write names it, and it resolves the type through the
// registry the same instant.
import "./refs/register";
import { loadShell, shellFor } from "./shells";

ensureLanding();

// Tell the server a page loaded, once: it queues the anonymous `space_loaded`
// event behind the user's opt out. The browser never talks to PostHog. Not in
// vite dev, where no server answers.
if (!import.meta.env.DEV) {
	void fetch("/api/telemetry/space-loaded", { method: "POST", keepalive: true }).catch(() => {});
}

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

// The shell for this device, picked once (./shells.ts). Its root opens the
// socket, so nothing lands before its node types are registered.
void loadShell(shellFor(touchDevice)).then((Shell) => {
	createRoot(root).render(
		<StrictMode>
			<Shell />
		</StrictMode>,
	);
});
