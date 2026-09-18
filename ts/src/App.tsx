import {
	IconButton,
	NodeView,
	Spinner,
	StatusPill,
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Moon, Sun } from "lucide-react";
import { useNuspaceConnection } from "./app/connect";
import { useBooted, useTypePath } from "./app/surfaces";
import { toggleTheme, useTheme } from "./app/theme";
import { shellBooting, shellMain, shellMissing, shellRoot, shellStatus } from "./design";

// The shell: a sidebar and a Viewer, side by side, and nothing else.
//
// There is no top strip and no surface switcher, because there is no third
// region to switch to. The sidebar lists every Plane that draws and the Viewer
// draws whichever one the URL names, so navigation is entirely the sidebar's
// and the shell only places the two.
//
// Both are found BY TYPE (see app/surfaces.ts), not by a slot name. Where
// python hangs them is python's call, and the wire type is the one thing about
// a region both sides already agree on.
//
// The connection pill and the theme flip are the only chrome left. They belong
// to the window rather than to either region, so they sit in a corner of it and
// take no layout room from what they are reporting on.

/** Wire status -> the kit's five status tones. */
const CONNECTION_TONE: Record<string, "ok" | "info" | "warn" | "danger"> = {
	connected: "ok",
	connecting: "info",
	reconnecting: "warn",
	disconnected: "danger",
};

function ThemeToggle() {
	const theme = useTheme();
	const next = theme === "dark" ? "light" : "dark";
	const Icon = theme === "dark" ? Sun : Moon;
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label={`Switch to ${next} theme`}
					onClick={toggleTheme}
				>
					<Icon />
				</IconButton>
			</TooltipTrigger>
			<TooltipContent side="top">{next} theme</TooltipContent>
		</Tooltip>
	);
}

export function App() {
	const status = useNuspaceConnection();
	const booted = useBooted();
	const sidebar = useTypePath("SidebarRef");
	const viewer = useTypePath("ViewerRef");

	if (!booted) {
		return (
			<div className={shellBooting}>
				<Spinner size="sm" tone="neutral" label="Connecting" />
				waiting for the tree...
			</div>
		);
	}

	return (
		<TooltipProvider>
			<div className={shellRoot}>
				{sidebar ? <NodeView path={sidebar} /> : null}
				<main className={shellMain}>
					{viewer ? (
						<NodeView path={viewer} />
					) : (
						<section className={shellMissing}>no Viewer on the tree</section>
					)}
				</main>
				<div className={shellStatus}>
					<StatusPill tone={CONNECTION_TONE[status] ?? "danger"} size="sm">
						{status}
					</StatusPill>
					<ThemeToggle />
				</div>
			</div>
		</TooltipProvider>
	);
}
