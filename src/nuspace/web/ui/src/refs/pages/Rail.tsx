// The page rail: a nested tree of pages.
//
// Pages only. Blocks are parts of a page, not navigable entities, so they
// never appear here.
//
// Selection is router-owned: the URL /pages/<pid>/<pid> is the cursor, the row
// click drives navigate(), and the canvas ships `on_page_select` off the route
// effect. The rail itself holds no selection state.
//
// ## The interaction model
//
// Two affordances, two jobs, no overlap:
//
//   * **the row navigates and reveals.** Opening a page that has children
//     shows them. It never hides them - a click that sometimes opens and
//     sometimes closes, depending on where you happened to be standing, is
//     what made this feel broken. Reveal is idempotent.
//   * **the twisty only folds.** It toggles both ways and never navigates, so
//     you can look inside a branch without leaving the page you are reading.
//
// Expansion is *revealed-then-sticky*: navigating to a page opens its whole
// ancestor chain, so a deep link, a back button, or a rename that reships the
// tree never leaves the open page buried in a folded branch. After that the
// fold state is yours until you navigate again. The reveal runs off the
// selection key rather than out of the click handler on purpose - arriving by
// URL has to behave exactly like arriving by click.
//
// The tree is flattened into the list of currently visible rows before it is
// rendered. Recursion made every cross-row question (what is below me, who is
// my parent, where does the indent guide run) unanswerable, which is why there
// was no keyboard model at all. Off a flat list it is a `role="tree"` with a
// roving tabindex and the usual four arrows.
//
// Every affordance is a kit primitive. A row's label is a `NavLink` (a real
// anchor, so cmd-click opens a page in a tab and `aria-current="page"` marks
// the open one for a screen reader); the twisty and the actions are
// `IconButton`s beside it rather than inside it, because a button inside an
// anchor is not a thing; per-page actions live in a kit `DropdownMenu` off the
// `...` and in a kit `ContextMenu` off a right-click on the row. Rename and
// create are a kit `Input` in the row itself - `window.prompt` blocks the tab,
// cannot be themed, and is not so much a dialog as the absence of one.
//
// Geometry and every class string live in `design/rail.ts`.

import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuSeparator,
	ContextMenuTrigger,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Input,
	NavLink,
	Skeleton,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { ChevronRight, Ellipsis, FileText, PenLine, Plus, Trash2 } from "lucide-react";
import type * as React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
	railAction,
	railActions,
	railAside,
	railEmpty,
	railGuide,
	railGuideStyle,
	railHeader,
	railHeaderLabel,
	railIndent,
	railInput,
	railInputBox,
	railLabel,
	railLane,
	railLaneStyle,
	railLeafIcon,
	railRow,
	railRowWrap,
	railScroll,
	railSkeletonRow,
	railTitle,
	railTwisty,
} from "../../design/rail";
import { hrefFor, navigate, onNavClick } from "../../router";
import type { PageNode } from "./types";

type Notify = (payload: Record<string, unknown>) => void;

/** One visible line of the tree, in render order. */
type VisibleRow = {
	/** Expansion + focus key: the page path, joined. The root page is "". */
	key: string;
	path: string[];
	depth: number;
	title: string;
	hasKids: boolean;
	open: boolean;
	/** Row key of the parent, or null at the root. */
	parent: string | null;
	/** 1-based position among *siblings*, which is what aria-posinset means. */
	pos: number;
	/** Number of siblings, for aria-setsize. */
	size: number;
};

/** An inline edit in flight. `create` renders a phantom row under `key`. */
type Draft = { kind: "rename" | "create"; key: string; path: string[]; initial: string };

const ROOT_KEY = "";
const ROOT_LABEL = "Space";

/** Walk the tree into the flat list of rows the current fold state shows. */
function flatten(
	node: PageNode,
	path: string[],
	depth: number,
	parent: string | null,
	pos: number,
	size: number,
	expanded: Set<string>,
	out: VisibleRow[],
): void {
	const key = path.join("/");
	const open = expanded.has(key);
	out.push({
		key,
		path,
		depth,
		title: node.title || (depth === 0 ? ROOT_LABEL : "Untitled"),
		hasKids: node.pages.length > 0,
		open,
		parent,
		pos,
		size,
	});
	if (!open) return;
	node.pages.forEach((kid, i) => {
		flatten(
			kid,
			[...path, String(kid.id)],
			depth + 1,
			key,
			i + 1,
			node.pages.length,
			expanded,
			out,
		);
	});
}

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
	// The tree lands in one `set_tree`; until it does there is nothing to draw
	// and the honest thing is row-shaped placeholders, not a fake empty tree.
	const loading = tree.id == null && tree.pages.length === 0;

	const rows = useMemo(() => {
		const out: VisibleRow[] = [];
		flatten(tree, [], 0, null, 1, 1, expanded, out);
		return out;
	}, [tree, expanded]);

	// -- expansion ------------------------------------------------------------
	//
	// `onToggle` flips a key, so "reveal" is "flip it if it is not already on".
	//
	// Two refs, both load-bearing.
	//
	// `expandedRef` is why the reveal below can run on a *selection* change
	// rather than on every fold: read the set through a ref and collapsing the
	// branch you are standing in does not instantly re-open it.
	//
	// `pending` is why revealing a whole ancestor chain works at all. The store
	// updates synchronously but the prop only lands on the next render, so a
	// second `reveal` in the same pass still sees the old set and flips the key
	// straight back off. That is the whole reason a deep link used to arrive
	// with the tree folded shut.
	const expandedRef = useRef(expanded);
	const pending = useRef(new Set<string>());
	if (expandedRef.current !== expanded) {
		expandedRef.current = expanded;
		pending.current.clear();
	}

	const reveal = useCallback(
		(key: string) => {
			if (expandedRef.current.has(key) || pending.current.has(key)) return;
			pending.current.add(key);
			onToggle(key);
		},
		[onToggle],
	);

	// Every ancestor of the open page is revealed, whether you got there by
	// clicking, by the back button, or by pasting a URL. The root is one of
	// those ancestors, which is also what opens the tree on arrival: it is a
	// real, foldable page like any other - the old rail forced it open *and*
	// still drew a twisty, so that control did nothing at all.
	// biome-ignore lint/correctness/useExhaustiveDependencies: selKey is the content of selectedPath, which is a fresh array every render
	useEffect(() => {
		reveal(ROOT_KEY);
		for (let i = 1; i < selectedPath.length; i++) {
			reveal(selectedPath.slice(0, i).join("/"));
		}
	}, [selKey, reveal]);

	// -- focus ----------------------------------------------------------------
	//
	// Roving tabindex: the tree is one tab stop and the arrows move inside it.
	// A rail with fifty pages is otherwise two hundred tab stops.
	const [activeKey, setActiveKey] = useState<string>(selKey);
	const treeRef = useRef<HTMLDivElement | null>(null);

	// Keep the tab stop on a row that exists: it follows selection and falls
	// back to the first row when whatever it was on got folded away.
	const tabKey = rows.some((r) => r.key === activeKey)
		? activeKey
		: rows.some((r) => r.key === selKey)
			? selKey
			: (rows[0]?.key ?? ROOT_KEY);

	// Rows are addressed by data attribute rather than a ref map: `NavLink` is
	// a plain function component and does not take one.
	const focusRow = useCallback((key: string) => {
		setActiveKey(key);
		const el = treeRef.current?.querySelector<HTMLElement>(`[data-rail-key="${CSS.escape(key)}"]`);
		el?.focus();
	}, []);

	// -- inline rename + create -----------------------------------------------

	const [draft, setDraft] = useState<Draft | null>(null);

	const startRename = useCallback((row: VisibleRow) => {
		setDraft({ kind: "rename", key: row.key, path: row.path, initial: row.title });
	}, []);

	const startCreate = useCallback(
		(row: VisibleRow) => {
			reveal(row.key);
			setDraft({ kind: "create", key: row.key, path: row.path, initial: "Untitled" });
		},
		[reveal],
	);

	const commitDraft = useCallback(
		(title: string) => {
			const d = draft;
			setDraft(null);
			if (!d) return;
			const next = title.trim();
			if (!next) return;
			if (d.kind === "rename") {
				if (next === d.initial.trim()) return;
				notify({ op: "on_page_rename", path: d.path, title: next });
			} else {
				notify({ op: "on_page_create", parent_path: d.path, title: next });
			}
		},
		[draft, notify],
	);

	const cancelDraft = useCallback(() => {
		const d = draft;
		setDraft(null);
		if (d) focusRow(d.key);
	}, [draft, focusRow]);

	// -- keyboard -------------------------------------------------------------

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent, row: VisibleRow, index: number) => {
			const go = (j: number) => {
				const target = rows[Math.max(0, Math.min(rows.length - 1, j))];
				if (target) focusRow(target.key);
			};
			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					go(index + 1);
					break;
				case "ArrowUp":
					e.preventDefault();
					go(index - 1);
					break;
				case "ArrowRight":
					// Open a folded branch; step into an open one.
					e.preventDefault();
					if (row.hasKids && !row.open) onToggle(row.key);
					else if (row.hasKids) go(index + 1);
					break;
				case "ArrowLeft":
					// Fold an open branch; otherwise climb to the parent.
					e.preventDefault();
					if (row.hasKids && row.open) onToggle(row.key);
					else if (row.parent !== null) focusRow(row.parent);
					break;
				case "Home":
					e.preventDefault();
					go(0);
					break;
				case "End":
					e.preventDefault();
					go(rows.length - 1);
					break;
				case "Enter":
				case " ":
					// Same contract as the click: open it, and reveal what is
					// inside it.
					e.preventDefault();
					if (row.hasKids) reveal(row.key);
					navigate({ top: "pages", path: row.path });
					break;
				case "F2":
					e.preventDefault();
					startRename(row);
					break;
				default:
					break;
			}
		},
		[rows, focusRow, onToggle, reveal, startRename],
	);

	return (
		<aside className={railAside}>
			<div className={railHeader}>
				<span className={railHeaderLabel}>pages</span>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="New top-level page"
							disabled={loading}
							onClick={() => {
								const root = rows[0];
								if (root) startCreate(root);
							}}
						>
							<Plus />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="bottom">new page</TooltipContent>
				</Tooltip>
			</div>
			<nav aria-label="Pages" className={railScroll}>
				{loading ? (
					<div aria-busy="true">
						{[0, 1, 1].map((depth, i) => (
							<div
								// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
								key={i}
								className={railSkeletonRow}
								style={railIndent(depth)}
							>
								<Skeleton className="h-3 w-full rounded-sm" />
							</div>
						))}
					</div>
				) : (
					<div role="tree" aria-label="Pages" ref={treeRef}>
						{rows.map((row, index) => (
							<div key={row.key} role="none">
								<div className={railRowWrap}>
									<Guides depth={row.depth} />
									<Row
										row={row}
										index={index}
										selected={row.key === selKey}
										tabbable={row.key === tabKey}
										renaming={draft?.kind === "rename" && draft.key === row.key}
										onToggle={onToggle}
										reveal={reveal}
										onFocus={setActiveKey}
										onKeyDown={onKeyDown}
										onRename={startRename}
										onCreate={startCreate}
										onCommit={commitDraft}
										onCancel={cancelDraft}
										notify={notify}
									/>
								</div>
								{draft?.kind === "create" && draft.key === row.key ? (
									<div className={railRowWrap}>
										<Guides depth={row.depth + 1} />
										<div className={railRow(false)} style={railIndent(row.depth + 1)}>
											<span className={railLane} style={railLaneStyle}>
												<FileText className={railLeafIcon} aria-hidden="true" />
											</span>
											<RowInput
												initial={draft.initial}
												label="Title for the new page"
												onCommit={commitDraft}
												onCancel={cancelDraft}
											/>
										</div>
									</div>
								) : null}
							</div>
						))}
						{/* Only when the root is open and genuinely childless. A
						    collapsed root also renders one row, and "no pages yet"
						    under a tree you just folded shut is a lie. */}
						{rows.length === 1 && rows[0]?.open && !rows[0]?.hasKids && draft == null ? (
							<p className={railEmpty}>no pages yet</p>
						) : null}
					</div>
				)}
			</nav>
		</aside>
	);
}

/**
 * One hairline per crossed level, running down the ancestors' twisty lanes.
 *
 * Levels start at 1, not 0: everything is under the root, so a guide marking
 * the root's lane carries no information and only reads as a second rail
 * border. A depth-1 row therefore gets no guide at all.
 */
function Guides({ depth }: { depth: number }) {
	if (depth < 2) return null;
	return (
		<>
			{Array.from({ length: depth - 1 }, (_, i) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: the index IS the level
				<span key={i} className={railGuide} style={railGuideStyle(i + 1)} aria-hidden="true" />
			))}
		</>
	);
}

function Row({
	row,
	index,
	selected,
	tabbable,
	renaming,
	onToggle,
	reveal,
	onFocus,
	onKeyDown,
	onRename,
	onCreate,
	onCommit,
	onCancel,
	notify,
}: {
	row: VisibleRow;
	index: number;
	selected: boolean;
	tabbable: boolean;
	renaming: boolean;
	onToggle: (key: string) => void;
	reveal: (key: string) => void;
	onFocus: (key: string) => void;
	onKeyDown: (e: React.KeyboardEvent, row: VisibleRow, index: number) => void;
	onRename: (row: VisibleRow) => void;
	onCreate: (row: VisibleRow) => void;
	onCommit: (title: string) => void;
	onCancel: () => void;
	notify: Notify;
}) {
	const { key, path, depth, title, hasKids, open, pos, size } = row;
	const navClick = onNavClick({ top: "pages", path });

	const remove = useCallback(() => {
		if (!window.confirm(`delete "${title}" and everything under it?`)) return;
		notify({ op: "on_page_delete", path });
	}, [notify, path, title]);

	const body = (
		// The row, not the anchor, is the tree item: an ARIA tree wants focus on
		// the item and the roving tabindex has to land somewhere that owns
		// aria-level / aria-expanded. The anchor stays a real anchor (cmd-click,
		// middle-click, aria-current) but drops out of the tab order.
		<div
			className={railRow(selected)}
			style={railIndent(depth)}
			role="treeitem"
			tabIndex={tabbable ? 0 : -1}
			data-rail-key={key}
			aria-selected={selected}
			aria-expanded={hasKids ? open : undefined}
			aria-level={depth + 1}
			aria-posinset={pos}
			aria-setsize={size}
			onFocus={() => onFocus(key)}
			onKeyDown={(e) => onKeyDown(e, row, index)}
		>
			<span className={railLane} style={railLaneStyle}>
				{hasKids ? (
					<IconButton
						variant="ghost"
						size="sm"
						tabIndex={-1}
						aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
						aria-expanded={open}
						onClick={() => onToggle(key)}
						className={railTwisty}
					>
						<ChevronRight
							className={`transition-transform duration-fast ease-out ${open ? "rotate-90" : ""}`}
						/>
					</IconButton>
				) : (
					<FileText className={railLeafIcon} aria-hidden="true" />
				)}
			</span>
			{renaming ? (
				<RowInput
					initial={title}
					label={`Rename ${title}`}
					onCommit={onCommit}
					onCancel={onCancel}
				/>
			) : (
				<NavLink
					size="sm"
					active={selected}
					href={hrefFor("pages", path)}
					title={title}
					tabIndex={-1}
					onClick={(e) => {
						// Opening a page reveals what is inside it. It never folds
						// it: a click that toggles is a click you cannot predict.
						if (hasKids) reveal(key);
						navClick(e);
					}}
					onDoubleClick={() => onRename(row)}
					className={railLabel}
				>
					<span className={railTitle}>{title}</span>
				</NavLink>
			)}
			<div className={railActions}>
				<IconButton
					variant="ghost"
					size="sm"
					tabIndex={tabbable ? 0 : -1}
					aria-label={`New page inside ${title}`}
					onClick={() => onCreate(row)}
					className={railAction}
				>
					<Plus />
				</IconButton>
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							tabIndex={tabbable ? 0 : -1}
							aria-label={`Actions for ${title}`}
							className={railAction}
						>
							<Ellipsis />
						</IconButton>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="start" className="min-w-40">
						<DropdownMenuItem onSelect={() => onRename(row)}>
							<PenLine />
							Rename
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={() => onCreate(row)}>
							<Plus />
							New page inside
						</DropdownMenuItem>
						{depth > 0 ? (
							<>
								<DropdownMenuSeparator />
								<DropdownMenuItem variant="danger" onSelect={remove}>
									<Trash2 />
									Delete
								</DropdownMenuItem>
							</>
						) : null}
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		</div>
	);

	return (
		<ContextMenu>
			<ContextMenuTrigger asChild>{body}</ContextMenuTrigger>
			<ContextMenuContent className="min-w-40">
				<ContextMenuItem onSelect={() => navigate({ top: "pages", path })}>
					<FileText />
					Open
				</ContextMenuItem>
				<ContextMenuSeparator />
				<ContextMenuItem onSelect={() => onRename(row)}>
					<PenLine />
					Rename
				</ContextMenuItem>
				<ContextMenuItem onSelect={() => onCreate(row)}>
					<Plus />
					New page inside
				</ContextMenuItem>
				{depth > 0 ? (
					<>
						<ContextMenuSeparator />
						<ContextMenuItem variant="danger" onSelect={remove}>
							<Trash2 />
							Delete
						</ContextMenuItem>
					</>
				) : null}
			</ContextMenuContent>
		</ContextMenu>
	);
}

/**
 * The in-row editor for rename and create. Commits on Enter and on blur (you
 * clicked away, you meant it), cancels on Escape, and selects the initial text
 * so the first keystroke replaces it.
 */
function RowInput({
	initial,
	label,
	onCommit,
	onCancel,
}: {
	initial: string;
	label: string;
	onCommit: (title: string) => void;
	onCancel: () => void;
}) {
	const done = useRef(false);
	// `Input` is a plain function component and takes no ref, so the caret is
	// placed through the wrapper.
	const box = useRef<HTMLSpanElement | null>(null);
	useEffect(() => {
		const el = box.current?.querySelector("input");
		el?.focus();
		el?.select();
	}, []);
	return (
		<span ref={box} className={railInputBox}>
			<Input
				size="sm"
				aria-label={label}
				defaultValue={initial}
				className={railInput}
				onBlur={(e) => {
					if (done.current) return;
					done.current = true;
					onCommit(e.currentTarget.value);
				}}
				onKeyDown={(e) => {
					// The tree's arrow handling must not see these.
					e.stopPropagation();
					if (e.key === "Enter") {
						e.preventDefault();
						done.current = true;
						onCommit(e.currentTarget.value);
					} else if (e.key === "Escape") {
						e.preventDefault();
						done.current = true;
						onCancel();
					}
				}}
			/>
		</span>
	);
}
