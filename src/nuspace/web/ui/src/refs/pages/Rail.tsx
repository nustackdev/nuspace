// The page rail: a nested tree of pages.
//
// Pages only. Blocks are parts of a page, not navigable entities, so they
// never appear here.
//
// Selection is router-owned: the URL /pages/<pid>/<pid> is the cursor, the row
// click drives navigate(), and the canvas ships `on_page_select` off the route
// effect. The rail itself holds no selection state.

import { useCallback } from "react";
import { navigate } from "../../router";
import type { PageNode } from "./types";

type Notify = (payload: Record<string, unknown>) => void;

export function Rail({
	tree,
	expanded,
	onToggle,
	selectedPath,
	notify,
}: {
	tree: PageNode;
	expanded: Set<string>;
	onToggle: (key: string) => void;
	selectedPath: string[];
	notify: Notify;
}) {
	const selKey = selectedPath.join("/");

	return (
		<aside className="flex w-60 shrink-0 flex-col border-r border-border-subtle bg-bg-surface">
			<div className="flex items-center gap-2 px-3 py-2.5">
				<span className="flex-1 font-mono text-xs uppercase tracking-wide text-text-muted">
					pages
				</span>
				<button
					type="button"
					title="New top-level page"
					onClick={() => {
						const title = window.prompt("new page", "Untitled");
						if (title) notify({ op: "on_page_create", parent_path: [], title });
					}}
					className="rounded-sm px-1.5 text-sm text-text-muted hover:bg-bg-sunken hover:text-text-primary"
				>
					+
				</button>
			</div>
			<div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-4">
				<Row
					node={tree}
					path={[]}
					depth={0}
					expanded={expanded}
					onToggle={onToggle}
					selKey={selKey}
					notify={notify}
					rootLabel="Space"
				/>
			</div>
		</aside>
	);
}

function Row({
	node,
	path,
	depth,
	expanded,
	onToggle,
	selKey,
	notify,
	rootLabel,
}: {
	node: PageNode;
	path: string[];
	depth: number;
	expanded: Set<string>;
	onToggle: (key: string) => void;
	selKey: string;
	notify: Notify;
	rootLabel?: string;
}) {
	const key = path.join("/");
	const open = depth === 0 || expanded.has(key);
	const selected = key === selKey;
	const hasKids = node.pages.length > 0;

	const select = useCallback(() => {
		navigate({ top: "pages", path });
	}, [path]);

	return (
		<div>
			<div
				className={`group flex items-center gap-1 rounded-md pr-1 ${
					selected ? "bg-accent-wash text-text-primary" : "text-text-secondary"
				} hover:bg-bg-sunken`}
				style={{ paddingLeft: `${depth * 12 + 2}px` }}
			>
				<button
					type="button"
					onClick={() => onToggle(key)}
					disabled={!hasKids}
					className={`w-4 shrink-0 text-xs ${
						hasKids ? "text-text-muted hover:text-text-primary" : "opacity-0"
					}`}
				>
					{open ? "▾" : "▸"}
				</button>
				<button
					type="button"
					onClick={select}
					onDoubleClick={() => {
						const title = window.prompt("rename page", node.title);
						if (title) notify({ op: "on_page_rename", path, title });
					}}
					className="min-w-0 flex-1 truncate py-1 text-left text-sm"
				>
					{node.title || rootLabel || "untitled"}
				</button>
				<button
					type="button"
					title="New child page"
					onClick={() => {
						const title = window.prompt("new page", "Untitled");
						if (!title) return;
						notify({ op: "on_page_create", parent_path: path, title });
						if (!expanded.has(key)) onToggle(key);
					}}
					className="hidden shrink-0 rounded-sm px-1 text-sm text-text-muted hover:text-text-primary group-hover:block"
				>
					+
				</button>
				{depth > 0 ? (
					<button
						type="button"
						title="Delete page"
						onClick={() => {
							if (
								!window.confirm(
									`delete "${node.title}" and everything under it?`,
								)
							)
								return;
							notify({ op: "on_page_delete", path });
						}}
						className="hidden shrink-0 rounded-sm px-1 text-sm text-text-muted hover:text-status-danger group-hover:block"
					>
						×
					</button>
				) : null}
			</div>
			{open
				? node.pages.map((kid) => (
						<Row
							key={kid.id ?? kid.title}
							node={kid}
							path={[...path, String(kid.id)]}
							depth={depth + 1}
							expanded={expanded}
							onToggle={onToggle}
							selKey={selKey}
							notify={notify}
						/>
					))
				: null}
		</div>
	);
}
