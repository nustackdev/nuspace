// The page rail: a nested tree of pages.
//
// Pages only. Blocks are parts of a page, not navigable entities, so they
// never appear here.
//
// Selection is router-owned: the URL /pages/<page_id> is the cursor, the row
// click drives navigate(), and `pages.tsx` ships `page.select` off the route
// effect. The rail itself holds no selection state.
//
// Pages are flat on the wire -- one row per page, hierarchy in `parent` and
// `children` -- so a row is keyed by its page id and nothing here carries a
// path. The nesting below is a rendering of the relation, not a shape the
// server ships.
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
// The furniture - the header strip, the row shell, the in-row editor, the
// roving tabindex - is `components/rail`, shared with the apps rail; every
// class string and the geometry are in `design/rail.ts`. What stays here is
// the tree: flatten, the guides, the twisty, and the two arrows that fold.

import {
	ContextMenuItem,
	ContextMenuSeparator,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Skeleton,
} from "@nustackdev/ui-kit";
import { ChevronRight, Ellipsis, FileText, PenLine, Plus, Trash2 } from "lucide-react";
import type * as React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { hrefFor, navigate, onNavClick } from "../../app/router";
import { RailHeader, RailRow, RailRowInput, RailRowLink, useRailFocus } from "../../components";
import {
	railAction,
	railAside,
	railEmpty,
	railGuide,
	railGuideStyle,
	railIndent,
	railLane,
	railLaneStyle,
	railLeafIcon,
	railRow,
	railRowWrap,
	railScroll,
	railSkeletonBar,
	railSkeletonRow,
	railTwisty,
} from "../../design";
import type { Notify } from "./ops";
import { ancestorsOf, childrenOf, mintId, type PageTree, rootId } from "./types";

/** One visible line of the tree, in render order. */
type VisibleRow = {
	/** Expansion + focus key. A page id, which is unique space-wide. */
	key: string;
	id: string;
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
type Draft = { kind: "rename" | "create"; key: string; id: string; initial: string };

const ROOT_LABEL = "Space";

/** The URL for a page. The root page is the bare /pages, not /pages/<root>. */
function pathFor(id: string, root: string): string[] {
	return id === root ? [] : [id];
}

/** Walk the tree into the flat list of rows the current fold state shows. */
function flatten(
	tree: PageTree,
	id: string,
	depth: number,
	parent: string | null,
	pos: number,
	size: number,
	expanded: Set<string>,
	out: VisibleRow[],
): void {
	const row = tree[id];
	if (!row) return;
	const kids = childrenOf(tree, id);
	const open = expanded.has(id);
	out.push({
		key: id,
		id,
		depth,
		title: row.title || (depth === 0 ? ROOT_LABEL : "Untitled"),
		hasKids: kids.length > 0,
		open,
		parent,
		pos,
		size,
	});
	if (!open) return;
	kids.forEach((kid, i) => {
		flatten(tree, kid.id, depth + 1, id, i + 1, kids.length, expanded, out);
	});
}

export function Rail({
	tree,
	loaded,
	expanded,
	onToggle,
	selectedId,
	notify,
}: {
	tree: PageTree;
	loaded: boolean;
	expanded: Set<string>;
	onToggle: (key: string) => void;
	selectedId: string;
	notify: Notify;
}) {
	const selKey = selectedId;
	const root = rootId(tree);
	// The tree lands in one `set_tree`; until it does there is nothing to draw
	// and the honest thing is row-shaped placeholders, not a fake empty tree.
	const loading = !loaded || !root;

	const rows = useMemo(() => {
		const out: VisibleRow[] = [];
		const top = rootId(tree);
		if (top) flatten(tree, top, 0, null, 1, 1, expanded, out);
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
	// biome-ignore lint/correctness/useExhaustiveDependencies: the walk reads the tree, but rerunning on every reship would fight the fold state; `root` flipping from "" is what carries the first tree in
	useEffect(() => {
		if (!root) return;
		// The root is always revealed, which is what opens the tree on arrival
		// even when the root itself is the page being looked at.
		reveal(root);
		for (const row of ancestorsOf(tree, selKey)) reveal(row.id);
	}, [selKey, root, reveal]);

	// -- focus ----------------------------------------------------------------
	//
	// The tree is one tab stop; `useRailFocus` owns the tab stop, the by-key
	// focus and the four moves both rails share.
	const keys = useMemo(() => rows.map((r) => r.key), [rows]);
	const { containerRef, tabKey, setActiveKey, focusKey, focusIndex, handleArrows } = useRailFocus(
		keys,
		selKey,
	);

	// -- inline rename + create -----------------------------------------------

	const [draft, setDraft] = useState<Draft | null>(null);

	const startRename = useCallback((row: VisibleRow) => {
		setDraft({ kind: "rename", key: row.key, id: row.id, initial: row.title });
	}, []);

	const startCreate = useCallback(
		(row: VisibleRow) => {
			reveal(row.key);
			setDraft({ kind: "create", key: row.key, id: row.id, initial: "Untitled" });
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
				notify("page.rename", { page_id: d.id, title: next });
			} else {
				// The id is minted here, so the new page can be routed to the
				// moment the server confirms it rather than guessed at.
				notify("page.create", { page_id: mintId("p"), parent_id: d.id, title: next });
			}
		},
		[draft, notify],
	);

	const cancelDraft = useCallback(() => {
		const d = draft;
		setDraft(null);
		if (d) focusKey(d.key);
	}, [draft, focusKey]);

	// -- keyboard -------------------------------------------------------------
	//
	// On top of the shared four: the two arrows that fold, and open-and-reveal.

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent, row: VisibleRow, index: number) => {
			if (handleArrows(e, index)) return;
			switch (e.key) {
				case "ArrowRight":
					// Open a folded branch; step into an open one.
					e.preventDefault();
					if (row.hasKids && !row.open) onToggle(row.key);
					else if (row.hasKids) focusIndex(index + 1);
					break;
				case "ArrowLeft":
					// Fold an open branch; otherwise climb to the parent.
					e.preventDefault();
					if (row.hasKids && row.open) onToggle(row.key);
					else if (row.parent !== null) focusKey(row.parent);
					break;
				case "Enter":
				case " ":
					// Same contract as the click: open it, and reveal what is
					// inside it.
					e.preventDefault();
					if (row.hasKids) reveal(row.key);
					navigate({ top: "pages", path: pathFor(row.id, root) });
					break;
				case "F2":
					e.preventDefault();
					startRename(row);
					break;
				default:
					break;
			}
		},
		[handleArrows, focusIndex, focusKey, onToggle, reveal, root, startRename],
	);

	return (
		<aside className={railAside}>
			<RailHeader
				label="pages"
				addLabel="New top-level page"
				addTooltip="new page"
				addDisabled={loading}
				onAdd={() => {
					const root = rows[0];
					if (root) startCreate(root);
				}}
			/>
			<nav aria-label="Pages" className={railScroll}>
				{loading ? (
					<div aria-busy="true">
						{[0, 1, 1].map((depth, i) => (
							<div
								// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
								key={i}
								className={railSkeletonRow()}
								style={railIndent(depth)}
							>
								<Skeleton className={railSkeletonBar} />
							</div>
						))}
					</div>
				) : (
					<div role="tree" aria-label="Pages" ref={containerRef}>
						{rows.map((row, index) => (
							<div key={row.key} role="none">
								<div className={railRowWrap}>
									<Guides depth={row.depth} />
									<Row
										row={row}
										root={root}
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
											<RailRowInput
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
	root,
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
	root: string;
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
	const { key, id, depth, title, hasKids, open, pos, size } = row;
	const path = pathFor(id, root);
	const navClick = onNavClick({ top: "pages", path });

	const remove = useCallback(() => {
		if (!window.confirm(`delete "${title}" and everything under it?`)) return;
		notify("page.delete", { page_id: id });
	}, [id, notify, title]);

	return (
		<RailRow
			rowKey={key}
			selected={selected}
			tabbable={tabbable}
			indent={depth}
			level={depth + 1}
			posinset={pos}
			setsize={size}
			expanded={hasKids ? open : undefined}
			onFocus={() => onFocus(key)}
			onKeyDown={(e) => onKeyDown(e, row, index)}
			lane={
				hasKids ? (
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
				)
			}
			label={
				renaming ? (
					<RailRowInput
						initial={title}
						label={`Rename ${title}`}
						onCommit={onCommit}
						onCancel={onCancel}
					/>
				) : (
					<RailRowLink
						href={hrefFor("pages", path)}
						label={title}
						selected={selected}
						onClick={(e) => {
							// Opening a page reveals what is inside it. It never folds
							// it: a click that toggles is a click you cannot predict.
							if (hasKids) reveal(key);
							navClick(e);
						}}
						onDoubleClick={() => onRename(row)}
					/>
				)
			}
			actions={
				<>
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
				</>
			}
			menu={
				<>
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
				</>
			}
		/>
	);
}
