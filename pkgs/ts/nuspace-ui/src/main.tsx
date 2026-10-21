import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@nustackdev/ui-kit/styles";
import "./index.css";
import { App } from "./App";
import { ensureLanding } from "./core/router";
// Registers every nuspace node type. Side-effect import, before the socket
// opens: the store autovivifies a node the moment a write names it, and it
// resolves the type through the registry the same instant.
import "./refs/register";

ensureLanding();

// Tell the server a page loaded, once: it queues the anonymous `space_loaded`
// event behind the user's opt out. The browser never talks to PostHog. Not in
// vite dev, where no server answers.
if (!import.meta.env.DEV) {
	void fetch("/api/telemetry/space-loaded", { method: "POST", keepalive: true }).catch(() => {});
}

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
	<StrictMode>
		<App />
	</StrictMode>,
);
