// The sidebar: every Plane that draws, as one list. One per tab.
//
// The only thing in nuspace that navigates. A row click replaces the focused
// pane or, with cmd/ctrl, opens a split; the URL is the cursor, and the Viewer
// is what tells the server which Planes are open.
//
// Planes are flat on the wire -- one row per Plane, hierarchy in `parent` and
// `children` -- so the row the sidebar draws is keyed by a Plane id and nothing
// here carries a path.

import type { NodeProps } from "@nustackdev/ui-kit";
import { pathKey } from "@nustackdev/ui-kit";
import { useCallback, useMemo } from "react";
import { notifyOp } from "../app/wire";
import type { Ops } from "./ops";
import { Rail } from "./Rail";
import { patchSidebar, useExpanded, useSidebarValue } from "./state";

export function Sidebar({ path }: NodeProps) {
	const { tree, loaded } = useSidebarValue(path);
	const expandedList = useExpanded(path);
	const key = pathKey(path);

	const expanded = useMemo(() => new Set(expandedList), [expandedList]);

	// One ref per op: the op name is the tail of the wire path, not a key in the
	// payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const toggleExpanded = useCallback(
		(id: string) => {
			patchSidebar(path, (s) => {
				const next = new Set(s.expanded);
				if (next.has(id)) next.delete(id);
				else next.add(id);
				return { expanded: Array.from(next) };
			});
		},
		[key],
	);

	return (
		<Rail
			tree={tree}
			loaded={loaded}
			expanded={expanded}
			onToggle={toggleExpanded}
			notify={notify}
		/>
	);
}
