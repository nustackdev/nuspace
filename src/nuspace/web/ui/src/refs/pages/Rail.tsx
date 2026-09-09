// The page rail: a nested tree of pages.
//
// Pages only. Blocks are parts of a page, not navigable entities, so they
// never appear here.
//
// Selection is router-owned: the URL /pages/<pid>/<pid> is the cursor, the row
// click drives navigate(), and the canvas ships `on_page_select` off the route
// effect. The rail itself holds no selection state.
//
// Every affordance here is a kit primitive. A row is a `NavLink` (a real
// anchor, so cmd-click opens a page in a tab and `aria-current="page"` marks
// the selected one for a screen reader); the twisty and the add button are
// `IconButton`s hit-tested beside it rather than nested inside it, because a
// button inside an anchor is not a thing; per-page actions live in a kit
// `DropdownMenu` instead of a row of naked glyphs.

import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	NavLink,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { ChevronRight, Ellipsis, PenLine, Plus, Trash2 } from "lucide-react";
import { useCallback } from "react";
import { hrefFor, onNavClick } from "../../router";
import type { PageNode } from "./types";

type Notify = (payload: Record<string, unknown>) => void;

/** Indent per depth level, on the 4px grid. Row text starts past the twisty. */
const INDENT = 12;
const TWISTY = 20;

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
			<div className="flex h-9 shrink-0 items-center gap-1 border-b border-border-subtle px-2">
				<span className="flex-1 pl-1 text-xs font-medium uppercase tracking-[0.06em] text-text-muted">
					pages
				</span>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="New top-level page"
							onClick={() => {
								const title = window.prompt("new page", "Untitled");
								if (title) notify({ op: "on_page_create", parent_path: [], title });
							}}
						>
							<Plus />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="bottom">new page</TooltipContent>
				</Tooltip>
			</div>
			<nav aria-label="Pages" className="min-h-0 flex-1 overflow-y-auto p-1">
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
			</nav>
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
	const title = node.title || rootLabel || "untitled";

	const rename = useCallback(() => {
		const next = window.prompt("rename page", node.title);
		if (next) notify({ op: "on_page_rename", path, title: next });
	}, [node.title, notify, path]);

	const addChild = useCallback(() => {
		const title = window.prompt("new page", "Untitled");
		if (!title) return;
		notify({ op: "on_page_create", parent_path: path, title });
		if (!expanded.has(key)) onToggle(key);
	}, [expanded, key, notify, onToggle, path]);

	return (
		<div>
			<div className="group/row relative flex items-center">
				{hasKids ? (
					<IconButton
						variant="ghost"
						size="sm"
						aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
						aria-expanded={open}
						onClick={() => onToggle(key)}
						className="absolute z-10 size-5 text-text-muted"
						style={{ left: `${depth * INDENT + 2}px` }}
					>
						<ChevronRight
							className={`transition-transform duration-fast ease-out ${open ? "rotate-90" : ""}`}
						/>
					</IconButton>
				) : null}
				{/* The indent is data (tree depth) and the trailing pad reserves the
				    lane the hover actions occupy, so a long title truncates before
				    it collides with them instead of sliding underneath. */}
				<NavLink
					size="sm"
					active={selected}
					href={hrefFor("pages", path)}
					onClick={onNavClick({ top: "pages", path })}
					onDoubleClick={rename}
					style={{ paddingLeft: `${depth * INDENT + TWISTY}px` }}
					className="min-w-0 flex-1 pr-14"
				>
					<span className="min-w-0 flex-1 truncate">{title}</span>
				</NavLink>
				<div className="absolute right-0.5 flex items-center gap-0.5 opacity-0 transition-opacity duration-fast ease-out group-hover/row:opacity-100 group-focus-within/row:opacity-100 [&:has([data-state=open])]:opacity-100">
					<IconButton
						variant="ghost"
						size="sm"
						aria-label={`New page inside ${title}`}
						onClick={addChild}
						className="size-5"
					>
						<Plus />
					</IconButton>
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<IconButton
								variant="ghost"
								size="sm"
								aria-label={`Actions for ${title}`}
								className="size-5"
							>
								<Ellipsis />
							</IconButton>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="start" className="min-w-40">
							<DropdownMenuItem onSelect={rename}>
								<PenLine />
								Rename
							</DropdownMenuItem>
							<DropdownMenuItem onSelect={addChild}>
								<Plus />
								New page inside
							</DropdownMenuItem>
							{depth > 0 ? (
								<>
									<DropdownMenuSeparator />
									<DropdownMenuItem
										variant="danger"
										onSelect={() => {
											if (!window.confirm(`delete "${title}" and everything under it?`)) return;
											notify({ op: "on_page_delete", path });
										}}
									>
										<Trash2 />
										Delete
									</DropdownMenuItem>
								</>
							) : null}
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
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
