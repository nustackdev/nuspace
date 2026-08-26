import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@nustackdev/ui-kit/styles";
import "./index.css";
import { App } from "./App";
import { LensRef } from "./refs/lens/lens";
import { registerRefEntry } from "./refs/register";

// Register nuspace-shipped refs before the store dispatches any mount.
registerRefEntry("LensRef", LensRef);

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
	<StrictMode>
		<App />
	</StrictMode>,
);
