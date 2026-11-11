// The sidebar footer, the fixed bottom bar: where nuspace lives on the web and the keyboard
// shortcuts on the left, the window's own state on the right.
//
// The connection dot and the theme flip belong to the window rather than to
// the space: the server writes no node for either, and a reconnect is the one
// thing in the shell nobody on the other end knows about. They live down here
// because the sidebar is the only edge the shell has, and two controls floating
// over a document you are writing in are two controls with nothing holding
// them.
//
// The free middle stays free: settings is a Plane, reached through its row in
// the nav section or cmd/ctrl+comma. That Plane holds the space's settings only;
// the theme is the window's, so it stays down here and in the browser.

import {
	IconButton,
	Shortcut,
	StatusDot,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import type { LucideIcon } from "lucide-react";
import { BookOpen, Github, Keyboard, Moon, Sun } from "lucide-react";
import { useConnectionStatus } from "../core/connection";
import { KEYS_KEYS, setKeysOpen } from "../core/keys";
import { toggleTheme, useTheme } from "../core/theme";
import {
	sidebarChromeButton,
	sidebarFooter,
	sidebarFooterSpace,
	sidebarStatus,
	sidebarTooltipHint,
} from "../design";

const GITHUB_URL = "https://github.com/nustackdev/nuspace";
const DOCS_URL = "https://nustack.dev/docs";

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
function FooterLink({
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
		<IconButton
			variant="ghost"
			size="sm"
			ring="inset"
			aria-label={label}
			tip={hint ?? label}
			tipSide="top"
			className={sidebarChromeButton}
			asChild
		>
			<a href={href} target="_blank" rel="noreferrer">
				<Icon />
			</a>
		</IconButton>
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
				<span role="status" aria-label={label} tabIndex={0} className={sidebarStatus}>
					<StatusDot tone={tone} pulse={busy} />
				</span>
			</TooltipTrigger>
			<TooltipContent side="top">{label}</TooltipContent>
		</Tooltip>
	);
}

/** Opens the keyboard shortcuts sheet (../shell/KeysDialog.tsx). */
function KeysButton() {
	return (
		<IconButton
			variant="ghost"
			size="sm"
			ring="inset"
			aria-label="Keyboard shortcuts"
			aria-keyshortcuts="Meta+/ Control+/"
			tip={
				<>
					Keyboard shortcuts
					<Shortcut keys={KEYS_KEYS} size="sm" className={sidebarTooltipHint} />
				</>
			}
			tipSide="top"
			onClick={() => setKeysOpen(true)}
			className={sidebarChromeButton}
		>
			<Keyboard />
		</IconButton>
	);
}

function ThemeToggle() {
	const theme = useTheme();
	const next = theme === "dark" ? "light" : "dark";
	const Icon = theme === "dark" ? Sun : Moon;
	return (
		<IconButton
			variant="ghost"
			size="sm"
			ring="inset"
			aria-label={`Switch to ${next} theme`}
			tip={`${next === "dark" ? "Dark" : "Light"} theme`}
			tipSide="top"
			onClick={toggleTheme}
			className={sidebarChromeButton}
		>
			<Icon />
		</IconButton>
	);
}

export function SidebarFooter() {
	return (
		<div className={sidebarFooter}>
			<FooterLink href={GITHUB_URL} label="GitHub" icon={Github} />
			<FooterLink href={DOCS_URL} label="Docs" icon={BookOpen} />
			<KeysButton />
			<div className={sidebarFooterSpace} />
			<ConnectionDot />
			<ThemeToggle />
		</div>
	);
}
