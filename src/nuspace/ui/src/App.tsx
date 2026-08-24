import { useState } from "react";
import { Badge, FieldView, useStore } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./connect";
import { Sidebar } from "./Sidebar";
import type { NuspaceBlock, NuspaceMount } from "./types";

const statusConfig = {
	connecting: { label: "connecting", variant: "outline" as const },
	connected: { label: "connected", variant: "default" as const },
	reconnecting: { label: "reconnecting...", variant: "outline" as const },
	disconnected: { label: "disconnected", variant: "danger" as const },
};

type BlockMode = "display" | "code";

async function postPrimitive(op: string, args: Record<string, unknown>): Promise<void> {
	try {
		await fetch("/control/primitive", {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ op, args }),
		});
	} catch (e) {
		console.warn(`${op} failed`, e);
	}
}

function BlockCard({ block }: { block: NuspaceBlock }) {
	const [mode, setMode] = useState<BlockMode>("display");
	return (
		<section className="rounded-md border border-border-default bg-bg-canvas p-4">
			<div className="mb-2 flex items-center justify-between">
				<div className="text-xs text-text-muted font-mono">
					{block.id} / {block.kind}
				</div>
				<div className="flex items-center gap-2 text-xs font-mono">
					<button
						type="button"
						onClick={() => setMode("display")}
						className={
							mode === "display"
								? "text-text-primary font-semibold underline"
								: "text-text-secondary hover:text-text-primary"
						}
					>
						display
					</button>
					<button
						type="button"
						onClick={() => setMode("code")}
						className={
							mode === "code"
								? "text-text-primary font-semibold underline"
								: "text-text-secondary hover:text-text-primary"
						}
					>
						code
					</button>
				</div>
			</div>
			{mode === "code" ? (
				<pre className="text-xs font-mono whitespace-pre-wrap p-2 rounded bg-bg-sunken border border-border-default">
					{block.snippet}
				</pre>
			) : (
				<div className="flex flex-col gap-3">
					{block.fields.map((f) => (
						<FieldView key={f.path} field={f} />
					))}
				</div>
			)}
		</section>
	);
}

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

	const onAddBlock = () => {
		const v = window.prompt("initial text?", "");
		if (v === null) return;
		void postPrimitive("add_block", {
			page_slug: active_page.slug,
			kind: "text",
			initial: v,
		});
	};

	return (
		<div className="h-screen flex overflow-hidden">
			<Sidebar pages={pages} activeSlug={active_page.slug} footer={statusBadge} />
			<main className="flex-1 min-w-0 h-full overflow-y-auto">
				<div className="mx-auto max-w-3xl p-6">
					<h1 className="text-xl font-medium mb-6">{active_page.title}</h1>
					<div className="flex flex-col gap-4">
						{active_page.blocks.map((b) => (
							<BlockCard key={b.id} block={b} />
						))}
						<button
							type="button"
							onClick={onAddBlock}
							className="text-sm text-text-secondary hover:text-text-primary border border-dashed border-border-default rounded-md py-2 hover:bg-bg-sunken"
						>
							+ new block
						</button>
					</div>
				</div>
			</main>
		</div>
	);
}

export default App;
