import { Badge, FieldView, useStore } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./connect";

const statusConfig = {
	connecting: { label: "connecting", variant: "outline" as const },
	connected: { label: "connected", variant: "default" as const },
	reconnecting: { label: "reconnecting...", variant: "outline" as const },
	disconnected: { label: "disconnected", variant: "danger" as const },
};

// Minimal shell for the v1 lens demo: one page, one lens ref.
// Structural fields render null but must mount so slices exist in the store.
export function App() {
	useNuspaceConnection();
	const status = useStore((s) => s.status);
	const page = useStore((s) => s.page);
	const fields = page?.fields ?? [];
	const { label, variant } = statusConfig[status];

	return (
		<div className="min-h-screen p-6 bg-background text-text-primary">
			<div className="mx-auto max-w-6xl">
				<div className="mb-4 flex items-center justify-between">
					<span className="text-sm text-muted-foreground font-mono">
						nuspace {page?.name ? `· ${page.name}` : ""}
					</span>
					<Badge variant={variant}>{label}</Badge>
				</div>
				{fields.length > 0 ? (
					<div className="flex flex-col gap-6">
						{fields.map((f) => (
							<FieldView key={f.path} field={f} />
						))}
					</div>
				) : (
					<p className="text-sm text-muted-foreground font-mono">
						waiting for mount...
					</p>
				)}
			</div>
		</div>
	);
}
