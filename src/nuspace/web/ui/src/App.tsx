import type { MountField, MountPage } from "@nustackdev/ui-core";
import { FieldView, useStore } from "@nustackdev/ui-kit";
import { useNuspaceConnection } from "./connect";
import { useRoute } from "./router";

// Split a page's fields into (sidebar, content). Pages that carry a
// SidebarRef slot get a two-column layout; the rest take the full width.
// Kept flat -- v1 pages have at most one sidebar and no other structural
// wrappers, so a first-match split is enough.
function splitFields(fields: MountField[]): {
	sidebar: MountField | null;
	content: MountField[];
} {
	const sidebar = fields.find((f) => f.type === "SidebarRef") ?? null;
	const content = sidebar ? fields.filter((f) => f !== sidebar) : fields;
	return { sidebar, content };
}

function findPage(
	pages: MountPage[] | undefined,
	route: string,
): MountPage | null {
	if (!pages) return null;
	return pages.find((p) => p.route === route) ?? null;
}

export function App() {
	useNuspaceConnection();
	const page = useStore((s) => s.page);
	const route = useRoute();

	const structural = page?.fields ?? [];
	const header = structural.find((f) => f.type === "HeaderRef") ?? null;
	const otherStructural = header
		? structural.filter((f) => f !== header)
		: structural;

	const activePage = findPage(page?.pages, route);
	const split = activePage ? splitFields(activePage.fields) : null;

	if (!page) {
		return (
			<div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground font-mono text-sm">
				waiting for mount...
			</div>
		);
	}

	return (
		<div className="min-h-screen flex flex-col bg-background text-text-primary">
			{header ? <FieldView field={header} /> : null}
			{/* Other structural refs (future title, nav, ...) render inline
			    under the header. Kept as a passthrough so nothing gets lost. */}
			{otherStructural.length > 0 ? (
				<div className="hidden">
					{otherStructural.map((f) => (
						<FieldView key={f.path} field={f} />
					))}
				</div>
			) : null}
			<main className="flex-1 min-h-0 flex">
				{split?.sidebar ? <FieldView field={split.sidebar} /> : null}
				<section className="flex-1 min-h-0 overflow-auto p-6">
					{split ? (
						split.content.length > 0 ? (
							<div className="mx-auto max-w-7xl flex flex-col gap-6">
								{split.content.map((f) => (
									<FieldView key={f.path} field={f} />
								))}
							</div>
						) : (
							<div className="mx-auto max-w-7xl text-sm text-muted-foreground font-mono">
								{activePage?.name ?? "empty page"}
							</div>
						)
					) : (
						<div className="mx-auto max-w-7xl text-sm text-muted-foreground font-mono">
							no page for {route}
						</div>
					)}
				</section>
			</main>
		</div>
	);
}
