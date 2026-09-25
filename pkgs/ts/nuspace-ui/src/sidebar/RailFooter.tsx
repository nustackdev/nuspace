// The rail's bottom bar: where nuspace lives on the web on the left, the
// window's own state on the right.
//
// The connection dot and the theme flip belong to the window rather than to
// the space: the server writes no node for either, and a reconnect is the one
// thing in the shell nobody on the other end knows about. They live down here
// because the rail is the only edge the shell has, and two controls floating
// over a document you are writing in are two controls with nothing holding
// them.
//
// The gear, in the free middle, opens the settings Plane the way a sidebar row opens its Plane: a
// real anchor, a plain click in the focused pane, cmd/ctrl-click as a split.
// It holds the space's settings only; the theme is the window's, so it stays
// down here and in the browser.

import { IconButton, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import type { LucideIcon } from "lucide-react";
import { BookOpen, Github, Moon, Settings, Sun } from "lucide-react";
import { useConnectionStatus } from "../core/connection";
import { hrefFor, onNavClick } from "../core/router";
import { toggleTheme, useTheme } from "../core/theme";
import {
	railChromeButton,
	railFooter,
	railFooterSpace,
	railStatus,
	railStatusDot,
} from "../design";

const GITHUB_URL = "https://github.com/nustackdev/nuspace";
/** The docs are not written yet; the site is the closest thing. */
const DOCS_URL = "https://nustack.dev";
/** The settings Plane's id, fixed by the host. */
const SETTINGS = "settings";

/** Wire status -> the kit's status tones. */
const CONNECTION_TONE: Record<string, "ok" | "info" | "warn" | "danger"> = {
	connected: "ok",
	connecting: "info",
	reconnecting: "warn",
	disconnected: "danger",
};

/** Wire status -> the words the tooltip shows. */
const CONNECTION_LABEL: Record<string, string> = {
	connected: "Connected",
	connecting: "Connecting",
	reconnecting: "Reconnecting",
	disconnected: "Disconnected",
};

/** A link out, as a chrome button. Opens in a new tab. */
function RailLink({
	href,
	label,
	hint,
	icon: Icon,
}: {
	href: string;
	label: string;
	/** The tooltip, when it says more than the label. */
	hint?: string;
	icon: LucideIcon;
}) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label={label}
					className={railChromeButton}
					asChild
				>
					<a href={href} target="_blank" rel="noreferrer">
						<Icon />
					</a>
				</IconButton>
			</TooltipTrigger>
			<TooltipContent side="top">{hint ?? label}</TooltipContent>
		</Tooltip>
	);
}

/** What the socket is doing, as a dot. The words are in the tooltip. */
function ConnectionDot() {
	const status = useConnectionStatus();
	const tone = CONNECTION_TONE[status] ?? "danger";
	const label = CONNECTION_LABEL[status] ?? status;
	const busy = status === "connecting" || status === "reconnecting";
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				{/* biome-ignore lint/a11y/noNoninteractiveTabindex: a keyboard has to reach the tooltip */}
				<span role="status" aria-label={label} tabIndex={0} className={railStatus}>
					<span className={railStatusDot(tone, busy)} />
				</span>
			</TooltipTrigger>
			<TooltipContent side="top">{label}</TooltipContent>
		</Tooltip>
	);
}

function SettingsLink() {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label="Settings"
					className={railChromeButton}
					asChild
				>
					<a href={hrefFor(SETTINGS)} onClick={onNavClick(SETTINGS)}>
						<Settings />
					</a>
				</IconButton>
			</TooltipTrigger>
			<TooltipContent side="top">Settings</TooltipContent>
		</Tooltip>
	);
}

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
					className={railChromeButton}
				>
					<Icon />
				</IconButton>
			</TooltipTrigger>
			<TooltipContent side="top">{next === "dark" ? "Dark" : "Light"} theme</TooltipContent>
		</Tooltip>
	);
}

export function RailFooter() {
	return (
		<div className={railFooter}>
			<RailLink href={GITHUB_URL} label="GitHub" icon={Github} />
			<RailLink href={DOCS_URL} label="Docs" hint="Docs are coming soon" icon={BookOpen} />
			<div className={railFooterSpace} />
			<SettingsLink />
			<div className={railFooterSpace} />
			<ConnectionDot />
			<ThemeToggle />
		</div>
	);
}
