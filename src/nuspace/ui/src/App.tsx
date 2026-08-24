import { Badge, FieldView, useStore } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./connect";
import { Sidebar } from "./Sidebar";
import type { NuspaceMount } from "./types";

const statusConfig = {
	connecting: { label: "connecting", variant: "outline" as const },
	connected: { label: "connected", variant: "default" as const },
	reconnecting: { label: "reconnecting...", variant: "outline" as const },
	disconnected: { label: "disconnected", variant: "danger" as const },
};

function App() {
	useNuspaceConnection();
	const status = useStore((s) => s.status);
	// kit's store puts our whole adapted payload on `s.page`; nuspace shape is under `nuspace`.
	const stored = useStore((s) => s.page) as { nuspace?: NuspaceMount } | null;
	const page = stored?.nuspace ?? null;

	const { label, variant } = statusConfig[status];
	const statusBadge = <Badge variant={variant}>{label}</Badge>;

	if (!page) {
		return (
			<div className="min-h-screen p-6 text-sm text-text-muted font-mono">
				waiting for mount...
			</div>
		);
	}

	const { pages, active_page } = page;

	if (!active_page) {
		return (
			<div className="h-screen flex overflow-hidden">
				<Sidebar pages={pages} activeSlug="" footer={statusBadge} />
				<main className="flex-1 min-w-0 h-full grid place-items-center text-sm text-text-muted font-mono">
					no page yet
				</main>
			</div>
		);
	}

	return (
		<div className="h-screen flex overflow-hidden">
			<Sidebar pages={pages} activeSlug={active_page.slug} footer={statusBadge} />
			<main className="flex-1 min-w-0 h-full overflow-y-auto">
				<div className="mx-auto max-w-3xl p-6">
					<h1 className="text-xl font-medium mb-6">{active_page.title}</h1>
					<div className="flex flex-col gap-4">
						{active_page.blocks.map((b) => (
							<section
								key={b.id}
								className="rounded-md border border-border-default bg-bg-canvas p-4"
							>
								<div className="mb-2 text-xs text-text-muted font-mono">
									{b.id} / {b.kind}
								</div>
								<div className="flex flex-col gap-3">
									{b.fields.map((f) => (
										<FieldView key={f.path} field={f} />
									))}
								</div>
							</section>
						))}
					</div>
				</div>
			</main>
		</div>
	);
}

export default App;
