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
import { FileText, Moon, Sun, Telescope } from "lucide-react";
import { useNuspaceConnection } from "./connect";
import { hrefFor, onNavClick, rememberedPath, TOPS, type Top, useRoute } from "./router";
import { toggleTheme, useTheme } from "./theme";

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
			<div className="flex min-h-screen items-center justify-center gap-2 bg-bg-canvas text-base text-text-muted">
				<Spinner size="sm" tone="neutral" label="Connecting" />
				waiting for mount...
			</div>
		);
	}

	const activePage = page.pages?.find((p) => p.route === `/${route.top}`) ?? null;

	return (
		<TooltipProvider>
			<div className="flex h-screen flex-col bg-bg-canvas text-text-primary">
				<header className="flex h-9 shrink-0 items-center gap-1 border-b border-border-subtle bg-bg-surface px-2">
					<nav aria-label="Surfaces" className="flex items-center gap-1">
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
				<main className="flex min-h-0 flex-1">
					{activePage ? (
						<section className="flex min-h-0 min-w-0 flex-1">
							{activePage.fields.map((f) => (
								<FieldView key={f.path} field={f} />
							))}
						</section>
					) : (
						<section className="min-h-0 flex-1 p-6 text-base text-text-muted">
							no surface for /{route.top}
						</section>
					)}
				</main>
			</div>
		</TooltipProvider>
	);
}
