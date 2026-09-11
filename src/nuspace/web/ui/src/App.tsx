import {
	FieldView,
	IconButton,
	NavLink,
	Separator,
	Spinner,
	StatusPill,
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
	useStore,
} from "@nustackdev/ui-kit";
import type { LucideIcon } from "lucide-react";
import { Boxes, FileText, Moon, Sun, Telescope } from "lucide-react";
import { useNuspaceConnection } from "./app/connect";
import { hrefFor, onNavClick, rememberedPath, TOPS, type Top, useRoute } from "./app/router";
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

// The shell: a thin top strip and one full-bleed surface.
//
// Every page's fields are mounted at once (the server ships them all in one
// mount envelope) and the router only decides which one renders. Switching
// surfaces must never remount -- a remount disposes every slice, including the
// ones a running section is writing into.
//
// The strip is chrome, so it is kit chrome: `NavLink` for the surfaces (real
// anchors, active-aware, `aria-current="page"` for free), `StatusPill` for the
// connection, `IconButton` + `Tooltip` for the theme flip. Nothing here paints
// its own hover or active state.

const SURFACE: Record<Top, { icon: LucideIcon; label: string }> = {
	pages: { icon: FileText, label: "pages" },
	apps: { icon: Boxes, label: "apps" },
	lens: { icon: Telescope, label: "lens" },
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
	useNuspaceConnection();
	const page = useStore((s) => s.page);
	const status = useStore((s) => s.status);
	const route = useRoute();

	if (!page) {
		return (
			<div className={shellBooting}>
				<Spinner size="sm" tone="neutral" label="Connecting" />
				waiting for mount...
			</div>
		);
	}

	const activePage = page.pages?.find((p) => p.route === `/${route.top}`) ?? null;

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
					{activePage ? (
						<section className={shellSurface}>
							{activePage.fields.map((f) => (
								<FieldView key={f.path} field={f} />
							))}
						</section>
					) : (
						<section className={shellMissing}>no surface for /{route.top}</section>
					)}
				</main>
			</div>
		</TooltipProvider>
	);
}
