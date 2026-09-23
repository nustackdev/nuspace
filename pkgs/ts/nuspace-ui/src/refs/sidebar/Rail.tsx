// The sidebar rail: a fixed header, a section per group, a fixed footer.
//
// Planes only. Cells are parts of a Plane, not navigable entities, so they
// never appear here.
//
// Selection is router-owned: the URL /<plane id> is the cursor, the row click
// drives navigate(), and the Viewer ships `page.select` off the route. The rail
// itself holds no selection state.
//
// Rows are flat on the wire -- one row each, hierarchy in `parent` and
// `children` -- so a row is keyed by its id and nothing here carries a path.
// The nesting below is a rendering of the relation, not a shape the server
// ships.
//
// ## Sections
//
// Two of the three kinds of row are shims the server invents: one for the
// Space, which is the tree's root and is never drawn because the header strip
// is what a person sees in its place, and one per group, which is a section.
// What a section is called and which Planes are in it are both the server's
// answer, so adding a group adds a section and nothing here changes.
//
// A section is an ordinary row with an ordinary twisty, which is what keeps the
// flatten, the fold state and the roving focus below working one level deeper
// without knowing a section exists. What it is not is a place: it has no Plane
// behind it, so it never navigates, and opening it is the only thing it does.
//
// ## The interaction model
//
// Two affordances, two jobs, no overlap:
//
//   * **the row navigates and reveals.** Opening a Plane that has children
//     shows them. It never hides them - a click that sometimes opens and
//     sometimes closes, depending on where you happened to be standing, is
//     what made this feel broken. Reveal is idempotent.
//   * **the twisty only folds.** It toggles both ways and never navigates, so
//     you can look inside a branch without leaving the Plane you are reading.
//
// Expansion is *revealed-then-sticky*: every section opens on arrival, and
// navigating to a Plane opens its whole ancestor chain, so a deep link, a back
// button, or a rename that reships the tree never leaves the open Plane buried
// in a folded branch. After that the fold state is yours until you navigate
// again. The reveal runs off the selection key rather than out of the click
// handler on purpose - arriving by URL has to behave exactly like arriving by
// click.
//
// The tree is flattened into the list of currently visible rows before it is
// rendered. Recursion made every cross-row question (what is below me, who is
// my parent, where does the indent guide run) unanswerable, which is why there
// was no keyboard model at all. Off a flat list it is a `role="tree"` with a
// roving tabindex and the usual four arrows.
//
// Every affordance is a kit primitive. A Plane row's label is a `NavLink` (a
// real anchor, so cmd-click opens a Plane in a tab and `aria-current="page"`
// marks the open one for a screen reader); the twisty and the actions are
// `IconButton`s beside it rather than inside it, because a button inside an
// anchor is not a thing; per-Plane actions live in a kit `DropdownMenu` off the
// `...` and in a kit `ContextMenu` off a right-click on the row. Rename and
// create are a kit `Input` in the row itself - `window.prompt` blocks the tab,
// cannot be themed, and is not so much a dialog as the absence of one.
//
// The furniture sits beside this file - `header.tsx` the strip, `footer.tsx`
// the connection pill and the theme flip, `row.tsx` the row shell,
// `row-input.tsx` the in-row editor, `roving-focus.ts` the one tab stop - and
// every class string and the geometry are in `design/rail.ts`. What stays here
// is the tree: flatten, the guides, the twisty, and the two arrows that fold.

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
import { mintId } from "../../app/ids";
import { hrefFor, navigate, onNavClick, useRoute } from "../../app/router";
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
	railResizeHandle,
	railRow,
	railRowWrap,
	railScroll,
	railSkeletonBar,
	railSkeletonRow,
	railTwisty,
} from "../../design";
import { RailFooter } from "./footer";
import { RailHeader } from "./header";
import type { Notify } from "./ops";
import { useRailWidth } from "./resize";
import { useRailFocus } from "./roving-focus";
import { RailRow, RailRowLink, RailSectionLabel } from "./row";
import { RailRowInput } from "./row-input";
import { ancestorsOf, childrenOf, KIND_GROUP, type PageTree, type RowKind, rootId } from "./types";

/** One visible line of the tree, in render order. */
type VisibleRow = {
	/** Expansion + focus key. A row id, which is unique space-wide. */
	key: string;
	id: string;
	kind: RowKind;
	/** The section this row is in. A section's own group is itself. */
	group: string;
	depth: number;
	title: string;
	hasKids: boolean;
	open: boolean;
	/** Row key of the parent, or null at the top. */
	parent: string | null;
	/** 1-based position among *siblings*, which is what aria-posinset means. */
	pos: number;
	/** Number of siblings, for aria-setsize. */
	size: number;
};

/** An inline edit in flight. `create` renders a phantom row under `key`. */
type Draft = { kind: "rename" | "create"; key: string; id: string; group: string; initial: string };

const RAIL_LABEL = "nuspace";

/** Whether a row folds. A section always does, even while it holds nothing. */
function folds(row: VisibleRow): boolean {
	return row.kind === KIND_GROUP || row.hasKids;
}

/** Walk the tree into the flat list of rows the current fold state shows. */
function flatten(
	tree: PageTree,
	id: string,
	group: string,
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
		kind: row.kind,
		group,
		depth,
		title: row.title || "Untitled",
		hasKids: kids.length > 0,
		open,
		parent,
		pos,
		size,
	});
	if (!open) return;
	kids.forEach((kid, i) => {
		flatten(tree, kid.id, group, depth + 1, id, i + 1, kids.length, expanded, out);
	});
}

export function Rail({
	tree,
	loaded,
	expanded,
	onToggle,
	notify,
}: {
	tree: PageTree;
	loaded: boolean;
	expanded: Set<string>;
	onToggle: (key: string) => void;
	notify: Notify;
}) {
	const route = useRoute();
	const { width: railWidth, onResizeStart, onResizeReset } = useRailWidth();
	const root = rootId(tree);
	// A bare "/" has nothing open, and no row stands in for that: the row that
	// stands for the Space is the tree's root and is not drawn.
	const selKey = route;
	// The tree lands in one `set_tree`; until it does there is nothing to draw
	// and the honest thing is row-shaped placeholders, not a fake empty tree.
	const loading = !loaded || !root;

	// The root is walked through rather than drawn, so the sections are the top
	// level and each one names the group everything under it belongs to.
	const sections = useMemo(() => childrenOf(tree, rootId(tree)), [tree]);

	const rows = useMemo(() => {
		const out: VisibleRow[] = [];
		sections.forEach((section, i) => {
			flatten(tree, section.id, section.id, 0, null, i + 1, sections.length, expanded, out);
		});
		return out;
	}, [tree, sections, expanded]);

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

	// Every section opens on arrival, and so does every ancestor of the open
	// Plane, whether you got there by clicking, by the back button, or by
	// pasting a URL. A rail whose sections all start folded is a rail that
	// looks empty.
	// biome-ignore lint/correctness/useExhaustiveDependencies: the walk reads the tree, but rerunning on every reship would fight the fold state; `root` flipping from "" is what carries the first tree in
	useEffect(() => {
		if (!root) return;
		for (const section of childrenOf(tree, root)) reveal(section.id);
		for (const row of ancestorsOf(tree, selKey)) if (row.id !== root) reveal(row.id);
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
		setDraft({
			kind: "rename",
			key: row.key,
			id: row.id,
			group: row.group,
			initial: row.title,
		});
	}, []);

	const startCreate = useCallback(
		(row: VisibleRow) => {
			reveal(row.key);
			setDraft({
				kind: "create",
				key: row.key,
				id: row.id,
				group: row.group,
				initial: "Untitled",
			});
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
				// The id is minted here, so the new Plane can be routed to the
				// moment the server confirms it rather than guessed at. `group`
				// is what decides what gets built; `parent_id` is where the row
				// would sit, and nothing nests yet.
				notify("page.create", {
					page_id: mintId("p"),
					parent_id: "",
					group: d.group,
					title: next,
				});
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
			const foldable = folds(row);
			switch (e.key) {
				case "ArrowRight":
					// Open a folded branch; step into an open one.
					e.preventDefault();
					if (foldable && !row.open) onToggle(row.key);
					else if (row.hasKids) focusIndex(index + 1);
					break;
				case "ArrowLeft":
					// Fold an open branch; otherwise climb to the parent.
					e.preventDefault();
					if (foldable && row.open) onToggle(row.key);
					else if (row.parent !== null) focusKey(row.parent);
					break;
				case "Enter":
				case " ":
					// Same contract as the click: a section only folds, a Plane
					// opens and reveals what is inside it.
					e.preventDefault();
					if (row.kind === KIND_GROUP) onToggle(row.key);
					else {
						if (row.hasKids) reveal(row.key);
						navigate(row.id);
					}
					break;
				case "F2":
					e.preventDefault();
					if (row.kind !== KIND_GROUP) startRename(row);
					break;
				default:
					break;
			}
		},
		[handleArrows, focusIndex, focusKey, onToggle, reveal, startRename],
	);

	return (
		<aside className={railAside} style={{ width: railWidth }}>
			<RailHeader label={RAIL_LABEL} />
			<nav aria-label="Planes" className={railScroll}>
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
					<div role="tree" aria-label="Planes" ref={containerRef}>
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
											<RailRowInput
												initial={draft.initial}
												label="Title for the new Plane"
												onCommit={commitDraft}
												onCancel={cancelDraft}
											/>
										</div>
									</div>
								) : null}
								{/* Only under a section that is open and genuinely
								    empty. A folded one draws a row too, and
								    "nothing here yet" under a branch you just
								    folded shut is a lie. */}
								{row.kind === KIND_GROUP && row.open && !row.hasKids && draft?.key !== row.key ? (
									<p className={railEmpty}>nothing here yet</p>
								) : null}
							</div>
						))}
					</div>
				)}
			</nav>
			<RailFooter />
			{/* biome-ignore lint/a11y/noStaticElementInteractions: pointer-only resize strip */}
			<div
				aria-hidden="true"
				className={railResizeHandle}
				onPointerDown={onResizeStart}
				onDoubleClick={onResizeReset}
			/>
		</aside>
	);
}

/**
 * One hairline per crossed level, running down the ancestors' twisty lanes.
 *
 * Levels start at 1, not 0: a guide marking the top level's lane carries no
 * information and only reads as a second rail border. A depth-1 row therefore
 * gets no guide at all.
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
	const { key, id, kind, depth, title, hasKids, open, pos, size } = row;
	const section = kind === KIND_GROUP;
	const foldable = folds(row);
	const navClick = onNavClick(id);

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
			expanded={foldable ? open : undefined}
			onFocus={() => onFocus(key)}
			onKeyDown={(e) => onKeyDown(e, row, index)}
			lane={
				foldable ? (
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
				) : section ? (
					<RailSectionLabel label={title} />
				) : (
					<RailRowLink
						href={hrefFor(id)}
						label={title}
						selected={selected}
						onClick={(e) => {
							// Opening a Plane reveals what is inside it. It never folds
							// it: a click that toggles is a click you cannot predict.
							if (hasKids) reveal(key);
							navClick(e);
						}}
						onDoubleClick={() => onRename(row)}
					/>
				)
			}
			actions={
				section ? (
					<IconButton
						variant="ghost"
						size="sm"
						tabIndex={tabbable ? 0 : -1}
						aria-label={`New in ${title}`}
						onClick={() => onCreate(row)}
						className={railAction}
					>
						<Plus />
					</IconButton>
				) : (
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
							<DropdownMenuSeparator />
							<DropdownMenuItem variant="danger" onSelect={remove}>
								<Trash2 />
								Delete
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				)
			}
			menu={
				section ? (
					<ContextMenuItem onSelect={() => onCreate(row)}>
						<Plus />
						New in {title}
					</ContextMenuItem>
				) : (
					<>
						<ContextMenuItem onSelect={() => navigate(id)}>
							<FileText />
							Open
						</ContextMenuItem>
						<ContextMenuSeparator />
						<ContextMenuItem onSelect={() => onRename(row)}>
							<PenLine />
							Rename
						</ContextMenuItem>
						<ContextMenuSeparator />
						<ContextMenuItem variant="danger" onSelect={remove}>
							<Trash2 />
							Delete
						</ContextMenuItem>
					</>
				)
			}
		/>
	);
}
