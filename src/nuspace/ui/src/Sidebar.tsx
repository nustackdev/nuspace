// Left rail for nuspace. Lists pages from the mount payload; clicking a
// page posts to /control/primitive with switch_page. Server rebuilds
// MOUNT for all connected sessions.

import type { ReactNode } from "react";
import type { NuspacePage } from "./types";

type Props = {
	pages: NuspacePage[];
	activeSlug: string;
	footer?: ReactNode;
};

async function switchPage(slug: string): Promise<void> {
	try {
		await fetch("/control/primitive", {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ op: "switch_page", args: { slug } }),
		});
	} catch (e) {
		// server may be down; ignore
		console.warn("switch_page failed", e);
	}
}

export function Sidebar({ pages, activeSlug, footer }: Props) {
	return (
		<aside className="w-52 shrink-0 border-r border-border-default bg-bg-sunken flex flex-col">
			<div className="px-4 py-4 border-b border-border-default">
				<span className="text-xs text-text-muted font-mono uppercase tracking-wider">
					nuspace
				</span>
			</div>
			<nav className="flex-1 overflow-y-auto p-2 flex flex-col gap-0.5">
				{pages.map((p) => {
					const active = p.slug === activeSlug;
					return (
						<button
							type="button"
							key={p.slug}
							onClick={() => {
								if (!active) void switchPage(p.slug);
							}}
							className={[
								"text-left text-sm px-3 py-1.5 rounded-md w-full",
								active
									? "bg-accent text-text-primary"
									: "text-text-secondary hover:bg-bg-canvas",
							].join(" ")}
						>
							{p.title}
						</button>
					);
				})}
			</nav>
			{footer ? (
				<div className="px-4 py-3 border-t border-border-default">{footer}</div>
			) : null}
		</aside>
	);
}
