import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@nustackdev/ui-kit/styles";
import "./index.css";
import { App } from "./App";
import { ensureLanding } from "./app/router";
import { AppsRef } from "./refs/apps/apps";
import { LensRef } from "./refs/lens/lens";
import { ProseRef } from "./refs/pages/ProseRef";
import { PagesRef } from "./refs/pages/pages";
import { registerRefEntry } from "./refs/register";

// Register nuspace-shipped refs before the store dispatches any mount.
// Header / Sidebar were archived ahead of the pages rebuild (task-139);
// they re-register here as they land.
registerRefEntry("LensRef", LensRef);
registerRefEntry("PagesRef", PagesRef);
registerRefEntry("AppsRef", AppsRef);

// ProseRef is nu's, not nuspace's, and the kit already has an entry for it.
// This one REPLACES it. The kit editor knows nothing about neighbouring
// blocks, by design; a text block is a block, so nuspace wraps that editor
// and rebuilds split, merge-up, arrow travel and the slash menu on top. A
// ProseRef somewhere that is not a block finds no block context and gets the
// kit's plain behaviour back. See ./refs/pages/ProseRef.tsx.
registerRefEntry("ProseRef", ProseRef);

ensureLanding();

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
	<StrictMode>
		<App />
	</StrictMode>,
);
