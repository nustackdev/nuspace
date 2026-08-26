import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@nustackdev/ui-kit/styles";
import "./index.css";
import { App } from "./App";
import { AppsRef } from "./refs/apps/apps";
import { HeaderRef } from "./refs/header/header";
import { LensRef } from "./refs/lens/lens";
import { registerRefEntry } from "./refs/register";
import { SidebarRef } from "./refs/sidebar/sidebar";
import { ensureLanding } from "./router";

// Register nuspace-shipped refs before the store dispatches any mount.
registerRefEntry("HeaderRef", HeaderRef);
registerRefEntry("SidebarRef", SidebarRef);
registerRefEntry("LensRef", LensRef);
registerRefEntry("AppsRef", AppsRef);

// Default landing = /lens for the v1 demo. Bare / (or any unknown path)
// gets replaced with /lens so the URL reflects the visible page.
ensureLanding();

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
	<StrictMode>
		<App />
	</StrictMode>,
);
