import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@nustackdev/ui-kit/styles";
import "./index.css";
import { App } from "./App";
import { ensureLanding } from "./app/router";
import { AppsRef } from "./refs/apps/apps";
import { LensRef } from "./refs/lens/lens";
import { PagesRef } from "./refs/pages/pages";
import { registerRefEntry } from "./refs/register";

// Register nuspace-shipped refs before the store dispatches any mount.
// Header / Sidebar were archived ahead of the pages rebuild (task-139);
// they re-register here as they land.
registerRefEntry("LensRef", LensRef);
registerRefEntry("PagesRef", PagesRef);
registerRefEntry("AppsRef", AppsRef);

ensureLanding();

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
	<StrictMode>
		<App />
	</StrictMode>,
);
