// The rail's footer strip: what the socket is doing, and the theme flip.
//
// Both belong to the window rather than to the sidebar, and neither belongs to
// the space: the server writes no node for either, and a reconnect is the one
// thing in the shell nobody on the other end knows about. They live down here
// because the rail is the only edge the shell has left, and two controls floating
// over a document you are writing in are two controls with nothing holding
// them.

import {
	IconButton,
	StatusPill,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Moon, Sun } from "lucide-react";
import { useConnectionStatus } from "../core/connection";
import { toggleTheme, useTheme } from "../core/theme";
import { railFooter } from "../design";

/** Wire status -> the kit's five status tones. */
const CONNECTION_TONE: Record<string, "ok" | "info" | "warn" | "danger"> = {
	connected: "ok",
	connecting: "info",
	reconnecting: "warn",
	disconnected: "danger",
};

/** Wire status -> the words the pill shows. */
const CONNECTION_LABEL: Record<string, string> = {
	connected: "Connected",
	connecting: "Connecting",
	reconnecting: "Reconnecting",
	disconnected: "Disconnected",
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
			<TooltipContent side="top">{next === "dark" ? "Dark" : "Light"} theme</TooltipContent>
		</Tooltip>
	);
}

export function RailFooter() {
	const status = useConnectionStatus();
	return (
		<div className={railFooter}>
			<StatusPill tone={CONNECTION_TONE[status] ?? "danger"} size="sm">
				{CONNECTION_LABEL[status] ?? status}
			</StatusPill>
			<ThemeToggle />
		</div>
	);
}
