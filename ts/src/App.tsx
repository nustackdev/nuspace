import {
	IconButton,
	NavLink,
	NodeView,
	Separator,
	Spinner,
	StatusPill,
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import type { LucideIcon } from "lucide-react";
import { Boxes, FileText, Moon, Sun, Telescope } from "lucide-react";
import { useNuspaceConnection } from "./app/connect";
import { hrefFor, onNavClick, rememberedPath, TOPS, type Top, useRoute } from "./app/router";
import { useBooted, useTypePath } from "./app/surfaces";
import { toggleTheme, useTheme } from "./app/theme";
import {
	shellBooting,
	shellMain,
	shellMissing,
	shellNav,
	shellRoot,
	shellStrip,
	shellSurface,
} from "./design";

// The shell: a thin top strip, one full-bleed surface, and the agent pinned
// to its right.
//
// Every surface is a node in the tree and they are all there at once, so the
// router only decides which one renders. Switching surfaces must never
// unmount one -- the store would keep the node either way, but a running
// section writing into a surface you cannot see should find its component
// where it left it.
//
// Surfaces are found BY TYPE (see app/surfaces.ts), not by a slot name. The
// old shell read a mount envelope's page list and matched each page's route
// against the URL; there is no envelope now, and the type is the one thing
// about a surface that both sides already agree on.
//
// The agent is pinned beside whichever surface is showing, because a run
// outlives the page you started it from. It sits outside the router's branch
// so navigation cannot touch it.
//
// The strip is chrome, so it is kit chrome: `NavLink` for the surfaces (real
// anchors, active-aware, `aria-current="page"` for free), `StatusPill` for the
// connection, `IconButton` + `Tooltip` for the theme flip. Nothing here paints
// its own hover or active state.

const SURFACE: Record<Top, { icon: LucideIcon; label: string; type: string }> = {
	pages: { icon: FileText, label: "pages", type: "PagesRef" },
	apps: { icon: Boxes, label: "apps", type: "AppsRef" },
	lens: { icon: Telescope, label: "lens", type: "LensRef" },
};

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
			<TooltipContent side="bottom">{next} theme</TooltipContent>
		</Tooltip>
	);
}

export function App() {
	const status = useNuspaceConnection();
	const booted = useBooted();
	const route = useRoute();
	// Every surface, looked up every render. Hooks cannot be called in a loop
	// over the route, and there are three of them, so they are named out.
	const pages = useTypePath("PagesRef");
	const apps = useTypePath("AppsRef");
	const lens = useTypePath("LensRef");
	const chat = useTypePath("ChatRef");

	if (!booted) {
		return (
			<div className={shellBooting}>
				<Spinner size="sm" tone="neutral" label="Connecting" />
				waiting for the tree...
			</div>
		);
	}

	const active = { pages, apps, lens }[route.top];

	return (
		<TooltipProvider>
			<div className={shellRoot}>
				<header className={shellStrip}>
					<nav aria-label="Surfaces" className={shellNav}>
						{TOPS.map((top) => {
							const { icon: Icon, label } = SURFACE[top];
							const path = rememberedPath(top);
							return (
								<NavLink
									key={top}
									size="sm"
									href={hrefFor(top, path)}
									active={route.top === top}
									onClick={onNavClick({ top, path })}
								>
									<Icon />
									{label}
								</NavLink>
							);
						})}
					</nav>
					<span className="flex-1" />
					<StatusPill tone={CONNECTION_TONE[status] ?? "danger"} size="sm">
						{status}
					</StatusPill>
					<Separator orientation="vertical" className="mx-1 h-4" />
					<ThemeToggle />
				</header>
				<main className={shellMain}>
					{active ? (
						<section className={shellSurface}>
							<NodeView path={active} />
						</section>
					) : (
						<section className={shellMissing}>no surface for /{route.top}</section>
					)}
					{chat ? <NodeView path={chat} /> : null}
				</main>
			</div>
		</TooltipProvider>
	);
}
