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

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
	<StrictMode>
		<App />
	</StrictMode>,
);
