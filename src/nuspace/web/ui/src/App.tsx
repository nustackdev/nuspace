import { FieldView, useStore } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./connect";
import { navigate, rememberedPath, TOPS, useRoute } from "./router";

// The shell: a thin top strip and one full-bleed surface.
//
// Every page's fields are mounted at once (the server ships them all in one
// mount envelope) and the router only decides which one renders. Switching
// surfaces must never remount -- a remount disposes every slice, including the
// ones a running section is writing into.

export function App() {
	useNuspaceConnection();
	const page = useStore((s) => s.page);
	const status = useStore((s) => s.status);
	const route = useRoute();

	if (!page) {
		return (
			<div className="flex min-h-screen items-center justify-center bg-bg-canvas font-mono text-sm text-text-muted">
				waiting for mount...
			</div>
		);
	}

	const activePage =
		page.pages?.find((p) => p.route === `/${route.top}`) ?? null;

	return (
		<div className="flex h-screen flex-col bg-bg-canvas text-text-primary">
			<nav className="flex shrink-0 items-center gap-1 border-b border-border-subtle bg-bg-surface px-3 py-1.5">
				{TOPS.map((top) => (
					<button
						key={top}
						type="button"
						onClick={() => navigate({ top, path: rememberedPath(top) })}
						className={`rounded-md px-2.5 py-1 font-mono text-xs ${
							route.top === top
								? "bg-accent-wash text-text-primary"
								: "text-text-muted hover:bg-bg-sunken hover:text-text-secondary"
						}`}
					>
						{top}
					</button>
				))}
				<span className="flex-1" />
				<span
					className={`font-mono text-xs ${
						status === "connected" ? "text-text-muted" : "text-status-warn"
					}`}
				>
					{status}
				</span>
			</nav>
			<main className="flex min-h-0 flex-1">
				{activePage ? (
					<section className="flex min-h-0 min-w-0 flex-1">
						{activePage.fields.map((f) => (
							<FieldView key={f.path} field={f} />
						))}
					</section>
				) : (
					<section className="min-h-0 flex-1 p-6 font-mono text-sm text-text-muted">
						no surface for /{route.top}
					</section>
				)}
			</main>
		</div>
	);
}
