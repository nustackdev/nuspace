import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
	<StrictMode>
		<div className="p-6 text-sm text-neutral-300">nuspace-ui: shell placeholder</div>
	</StrictMode>,
);
