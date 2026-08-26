// HeaderRef -- nuspace shell header.
//
// Server ships brand + tabs once in mount props. Status comes from the
// shared store (set by the connect hook). Tab click drives the local
// router; the active tab highlight is picked from window.location.

import type { RefEntry, RefSlice, SliceFactory } from "@nustackdev/ui-kit";
import { Badge, useStore } from "@nustackdev/ui-kit";
import { navigate, useRoute } from "../../router";

type Tab = { route: string; label: string };

type HeaderSlice = RefSlice & {
	brand: string;
	tabs: Tab[];
};

function _tabs(raw: unknown): Tab[] {
	if (!Array.isArray(raw)) return [];
	return raw
		.map((t) => {
			if (t && typeof t === "object") {
				const rec = t as Record<string, unknown>;
				const route = typeof rec.route === "string" ? rec.route : "";
				const label = typeof rec.label === "string" ? rec.label : "";
				if (route && label) return { route, label };
			}
			return null;
		})
		.filter((t): t is Tab => t !== null);
}

const factory: SliceFactory = (_path, _ctx, props) => {
	const brand = typeof props?.brand === "string" ? props.brand : "nuspace";
	const tabs = _tabs(props?.tabs);
	return {
		type: "HeaderRef",
		value: null,
		brand,
		tabs,
	} as HeaderSlice;
};

const statusConfig = {
	connecting: { label: "connecting", variant: "outline" as const },
	connected: { label: "connected", variant: "default" as const },
	reconnecting: { label: "reconnecting...", variant: "outline" as const },
	disconnected: { label: "disconnected", variant: "danger" as const },
};

function HeaderView({ path }: { path: string }) {
	const slice = useStore((s) => s.refs[path] as HeaderSlice | undefined);
	const status = useStore((s) => s.status);
	const currentRoute = useRoute();
	const brand = slice?.brand ?? "nuspace";
	const tabs = slice?.tabs ?? [];
	const { label, variant } = statusConfig[status];

	return (
		<header className="sticky top-0 z-20 border-b border-border/60 bg-background/90 backdrop-blur">
			<div className="mx-auto flex h-12 max-w-7xl items-center gap-6 px-4">
				<span className="text-sm font-mono font-semibold tracking-wide">
					{brand}
				</span>
				<nav className="flex flex-1 items-center gap-1">
					{tabs.map((t) => {
						const active = t.route === currentRoute;
						return (
							<button
								key={t.route}
								type="button"
								onClick={() => navigate(t.route as never)}
								className={
									"px-3 py-1.5 text-sm font-mono rounded-md transition-colors " +
									(active
										? "bg-primary/10 text-text-primary"
										: "text-muted-foreground hover:bg-muted/40 hover:text-text-primary")
								}
								aria-current={active ? "page" : undefined}
							>
								{t.label}
							</button>
						);
					})}
				</nav>
				<Badge variant={variant}>{label}</Badge>
			</div>
		</header>
	);
}

export const HeaderRef: RefEntry = { factory, component: HeaderView };
