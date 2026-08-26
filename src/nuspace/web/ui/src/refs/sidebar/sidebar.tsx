// SidebarRef -- v1 skeleton.
//
// Renders a narrow left rail with a title. Content model lands with
// AppsExplorerRef and PagesRendererRef. Kept as a real ref (not a
// layout flag) so the shell can put the sidebar/no-sidebar decision on
// the page's slot list rather than a magic prop.

import type { RefEntry, RefSlice, SliceFactory } from "@nustackdev/ui-kit";
import { useStore } from "@nustackdev/ui-kit";

type SidebarSlice = RefSlice & { title: string };

const factory: SliceFactory = (_path, _ctx, props) => {
	const title = typeof props?.title === "string" ? props.title : "";
	return {
		type: "SidebarRef",
		value: null,
		title,
	} as SidebarSlice;
};

function SidebarView({ path }: { path: string }) {
	const slice = useStore((s) => s.refs[path] as SidebarSlice | undefined);
	const title = slice?.title ?? "";
	return (
		<aside className="w-60 shrink-0 border-r border-border/60 h-full flex flex-col">
			<div className="px-4 py-3 text-xs uppercase tracking-wider text-muted-foreground font-mono border-b border-border/60">
				{title}
			</div>
			<div className="flex-1 min-h-0 overflow-y-auto p-4 text-sm text-muted-foreground font-mono">
				(coming soon)
			</div>
		</aside>
	);
}

export const SidebarRef: RefEntry = { factory, component: SidebarView };
