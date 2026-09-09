// LensRef -- Miller-columns browser for any Nu Shape.
//
// Browser owns the cursor. Slice starts with `path: []`; the server
// ships the root column on mount (`{path: [], columns: [root]}`) and
// the slice takes it from there. Every `write` frame carries the full
// new state:
//   {path: string[], columns: Column[]}
//
// Notify frames flow the other way with the browser-computed full path:
//   {path: string[]}
// Click / ArrowRight / Enter -> push a segment, ArrowLeft / Escape ->
// pop -- always sent as an already-resolved full path so the server
// stays a pure "recompute columns for whatever path you're given" loop
// with no runtime state of its own. Reload starts back at root.
// Up / Down move focus locally in the active column with no wire hit.
//
// Look and feel live in ../../design/lens.ts (class recipes, the kind and
// value-type vocabularies) and ../../design/lens.css (tokens). Nothing below
// picks a color or a size at the call site.
//
// The one idea the surface is built around: three row tiers that must never
// collapse into each other -- neutral hover, neutral TRAIL (the row that
// opened the column to its right), accent CURSOR (where the keyboard is).
// In miller columns that distinction is the navigation model, not decoration.

import { OP_NOTIFY } from "@nustackdev/ui-core";
import type { RefEntry, SliceFactory } from "@nustackdev/ui-kit";
import {
	Breadcrumb,
	BreadcrumbEllipsis,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
	cn,
	Kbd,
	Skeleton,
	useStore,
} from "@nustackdev/ui-kit";
import { ChevronRight } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef } from "react";

import {
	glyphTone,
	kindIcon,
	kindLabel,
	lensBar,
	lensBarHint,
	lensBarPath,
	lensCapNote,
	lensColumn,
	lensColumnBody,
	lensColumnCount,
	lensColumnHead,
	lensColumnKind,
	lensColumns,
	lensCrumb,
	lensEmpty,
	lensFiller,
	lensFillerHead,
	lensHintPair,
	lensLeafBody,
	lensLeafNote,
	lensRoot,
	lensRow,
	lensRowChevron,
	lensRowGlyph,
	lensRowKey,
	lensRowRail,
	lensRowValue,
	lensSentinelChip,
	lensSkeletonRow,
	rowIcon,
	VTYPE_SENTINEL_LABEL,
	valueTone,
} from "../../design/lens";

type Entry = {
	key: string;
	kind: string;
	preview: string;
	navigable: boolean;
	/** Value type. "" when the row holds no value (a dict key). */
	vtype?: string;
	/** Leaf rows only: the untruncated value for the reader pane. */
	text?: string;
	clipped?: boolean;
};

type Column = {
	kind: string;
	entries: Entry[];
	total: number;
};

type LensValue = {
	path: string[];
	columns: Column[];
};

/** Sentinel-ish types render as a chip, never as text. */
const SENTINEL = new Set(["empty", "none", "invalid", "error"]);

const factory: SliceFactory = (path, ctx, props) => {
	const maxRows =
		typeof props?.max_rows === "number" && Number.isFinite(props.max_rows)
			? Math.max(1, Math.floor(props.max_rows as number))
			: 200;
	return {
		type: "LensRef",
		value: { path: [], columns: [] } as LensValue,
		maxRows,
		focusedIndex: {} as Record<number, number>,
		scroll: {} as Record<number, number>,
		// Depth of the navigation currently in flight, or null. Drives the
		// skeleton column: a drill should show the column arriving, not a
		// frozen surface with nothing to say for a round trip.
		pendingDepth: null as number | null,
		write: (v) =>
			ctx.set((refs) => {
				const slice = refs[path];
				if (!slice) return;
				const p = (v ?? {}) as Record<string, unknown>;
				const columns = Array.isArray(p.columns) ? (p.columns as Column[]) : [];
				slice.value = {
					path: Array.isArray(p.path) ? p.path.map((s) => String(s)) : [],
					columns,
				};
				// Keep the cursor of every column that still exists, drop the
				// rest. Clearing this wholesale is what made popping land back
				// on row 0 instead of on the row you came through: the cursor
				// for column N is exactly where you were standing when you
				// drilled out of it.
				const prev = (slice.focusedIndex ?? {}) as Record<number, number>;
				const kept: Record<number, number> = {};
				for (const key of Object.keys(prev)) {
					const i = Number(key);
					if (i < columns.length) kept[i] = prev[i];
				}
				slice.focusedIndex = kept;
				slice.pendingDepth = null;
			}),
	};
};

/* ============================== pieces =================================== */

/** A value cell, rendered by type. */
function ValueCell({ entry }: { entry: Entry }) {
	const vtype = entry.vtype ?? "";
	if (SENTINEL.has(vtype)) {
		return (
			<span className={cn(lensRowValue, valueTone(vtype), lensSentinelChip)}>
				{VTYPE_SENTINEL_LABEL[vtype] ?? vtype}
			</span>
		);
	}
	if (!entry.preview) return null;
	return (
		<span className={cn(lensRowValue, valueTone(vtype))} title={entry.preview}>
			{entry.preview}
		</span>
	);
}

function Row({
	entry,
	id,
	level,
	cursor,
	trail,
	onOpen,
}: {
	entry: Entry;
	id: string;
	level: number;
	cursor: boolean;
	trail: boolean;
	onOpen: () => void;
}) {
	const el = useRef<HTMLButtonElement | null>(null);
	const Glyph = rowIcon(entry.kind, entry.vtype ?? "");

	// Keep the cursor in view on a keyboard walk. `nearest` so a click never
	// yanks the column, only an off-screen key press does.
	useLayoutEffect(() => {
		if (cursor) el.current?.scrollIntoView({ block: "nearest" });
	}, [cursor]);

	return (
		<button
			id={id}
			ref={el}
			type="button"
			// The container owns the keyboard; rows stay out of the tab order
			// so tabbing past a 200-row column takes one press, not two hundred.
			tabIndex={-1}
			role="treeitem"
			aria-level={level}
			aria-selected={cursor}
			aria-expanded={entry.navigable ? trail : undefined}
			className={lensRow({ cursor, trail })}
			onClick={onOpen}
		>
			<span className={lensRowRail({ cursor, trail })} aria-hidden="true" />
			<Glyph
				className={cn(lensRowGlyph, glyphTone(entry.vtype ?? "", entry.navigable))}
				aria-hidden="true"
			/>
			<span className={lensRowKey} title={entry.key}>
				{entry.key}
			</span>
			<ValueCell entry={entry} />
			<ChevronRight className={lensRowChevron(entry.navigable)} aria-hidden="true" />
		</button>
	);
}

/** The leaf column's reader pane: one value, in full, wrapped. */
function LeafBody({ entry }: { entry: Entry }) {
	const vtype = entry.vtype ?? "";
	if (SENTINEL.has(vtype)) {
		return (
			<div className={lensEmpty}>
				<span className={cn(lensSentinelChip, valueTone(vtype))}>
					{VTYPE_SENTINEL_LABEL[vtype] ?? vtype}
				</span>
				<span>
					{vtype === "empty"
						? "this slot has never been written"
						: vtype === "none"
							? "the slot holds null"
							: "the read did not produce a value"}
				</span>
			</div>
		);
	}
	const body = entry.text ?? entry.preview;
	if (!body) {
		return <div className={lensEmpty}>no value</div>;
	}
	return (
		<>
			<div className={cn(lensLeafBody, valueTone(vtype))}>{body}</div>
			{entry.clipped ? (
				<div className={lensLeafNote}>clipped -- value is longer than shown</div>
			) : null}
		</>
	);
}

function ColumnPanel({
	col,
	colIdx,
	active,
	trailKey,
	cursorIdx,
	rowId,
	onOpen,
}: {
	col: Column;
	colIdx: number;
	active: boolean;
	trailKey: string | null;
	cursorIdx: number;
	rowId: (colIdx: number, i: number) => string;
	onOpen: (colIdx: number, key: string) => void;
}) {
	const leaf = col.kind === "leaf";
	const vtype = leaf ? (col.entries[0]?.vtype ?? "") : "";
	// On a leaf column the header states the value's TYPE, because that is the
	// only thing about it a header can usefully say; everywhere else it states
	// the structural kind, which is what the rows below are.
	const Glyph = leaf ? rowIcon(col.kind, vtype) : kindIcon(col.kind);
	const capped = col.total > col.entries.length;

	return (
		<div className={lensColumn(leaf)}>
			<div className={lensColumnHead(active)}>
				<Glyph
					className={cn(lensRowGlyph, active ? "text-accent" : "text-text-muted")}
					aria-hidden="true"
				/>
				<span className={lensColumnKind}>
					{leaf ? vtype || kindLabel(col.kind) : kindLabel(col.kind)}
				</span>
				{!leaf ? (
					<span className={lensColumnCount}>
						{capped ? `${col.entries.length}/${col.total}` : col.total}
					</span>
				) : null}
			</div>

			{leaf && col.entries[0] ? (
				<LeafBody entry={col.entries[0]} />
			) : col.entries.length === 0 ? (
				<div className={lensEmpty}>
					<span>nothing here</span>
					<span>this {kindLabel(col.kind)} holds no entries</span>
				</div>
			) : (
				<>
					{/* biome-ignore lint/a11y/useSemanticElements: the tree lives on the scroll host; a column is one level of it */}
					<div className={lensColumnBody} role="group">
						{col.entries.map((e, i) => (
							<Row
								key={`${colIdx}::${e.key}`}
								id={rowId(colIdx, i)}
								entry={e}
								level={colIdx + 1}
								cursor={active && i === cursorIdx}
								trail={!active && e.key === trailKey}
								onOpen={() => onOpen(colIdx, e.key)}
							/>
						))}
					</div>
					{capped ? (
						<div className={lensCapNote}>
							first {col.entries.length} of {col.total}
						</div>
					) : null}
				</>
			)}
		</div>
	);
}

/** Placeholder for the column being fetched. Same geometry, so nothing jumps. */
function SkeletonColumn() {
	return (
		<div className={lensColumn(false)} aria-hidden="true">
			<div className={lensColumnHead(true)}>
				<Skeleton shape="text" className="h-3 w-16" />
			</div>
			<div className={lensColumnBody}>
				{[0, 1, 2, 3, 4, 5].map((i) => (
					<div key={i} className={lensSkeletonRow}>
						<Skeleton shape="circle" className="size-3" />
						<Skeleton shape="text" className="h-2.5" style={{ width: `${70 - i * 8}%` }} />
					</div>
				))}
			</div>
		</div>
	);
}

/** The path trail. Collapses the middle so a deep path never eats the bar. */
function PathTrail({ path, onJump }: { path: string[]; onJump: (depth: number) => void }) {
	// root + up to five segments reads fine at 1440; past that the middle
	// folds, because the useful crumbs on a deep path are the root (jump
	// home) and the last few (where you are).
	const KEEP = 3;
	const folded = path.length > 5;
	const shown = folded ? path.slice(path.length - KEEP) : path;
	const offset = folded ? path.length - KEEP : 0;

	return (
		<Breadcrumb className={lensBarPath}>
			<BreadcrumbList className="flex-nowrap gap-1">
				<BreadcrumbItem>
					{path.length === 0 ? (
						<BreadcrumbPage className={lensCrumb}>root</BreadcrumbPage>
					) : (
						<BreadcrumbLink
							className={lensCrumb}
							onClick={(e) => {
								e.preventDefault();
								onJump(0);
							}}
						>
							root
						</BreadcrumbLink>
					)}
				</BreadcrumbItem>
				{folded ? (
					<>
						<BreadcrumbSeparator />
						<BreadcrumbItem>
							<BreadcrumbEllipsis />
						</BreadcrumbItem>
					</>
				) : null}
				{shown.map((seg, i) => {
					const depth = offset + i + 1;
					const last = depth === path.length;
					return (
						<BreadcrumbItem key={`${depth}-${seg}`}>
							<BreadcrumbSeparator />
							{last ? (
								<BreadcrumbPage className={lensCrumb}>{seg}</BreadcrumbPage>
							) : (
								<BreadcrumbLink
									className={lensCrumb}
									onClick={(e) => {
										e.preventDefault();
										onJump(depth);
									}}
								>
									{seg}
								</BreadcrumbLink>
							)}
						</BreadcrumbItem>
					);
				})}
			</BreadcrumbList>
		</Breadcrumb>
	);
}

/* ============================== view ===================================== */

function LensView({ path }: { path: string }) {
	const value = useStore((s) => s.refs[path]?.value as LensValue | undefined);
	const focused = useStore(
		(s) => (s.refs[path]?.focusedIndex as Record<number, number> | undefined) ?? {},
	);
	const pendingDepth = useStore(
		(s) => (s.refs[path]?.pendingDepth as number | null | undefined) ?? null,
	);
	const setLocal = useStore((s) => s.setLocal);
	const set = useStore.setState;
	const send = useStore((s) => s.send);
	const containerRef = useRef<HTMLDivElement | null>(null);

	const columns = useMemo(() => value?.columns ?? [], [value]);
	const cursorPath = useMemo(() => value?.path ?? [], [value]);
	// The live column is always the last one. In miller columns the cursor is
	// singular by construction: clicking an earlier column does not "activate"
	// it, it renavigates, which drops every column to its right.
	const activeCol = Math.max(0, columns.length - 1);
	const cursorIdx = focused[activeCol] ?? 0;

	const patch = useCallback(
		(fn: (slice: Record<string, unknown>) => Record<string, unknown>) => {
			set((s) => {
				const slice = s.refs[path];
				if (!slice) return s;
				return { ...s, refs: { ...s.refs, [path]: { ...slice, ...fn(slice) } } };
			});
		},
		// `set` is `useStore.setState`, a module-level stable identity.
		[path],
	);

	const setCursor = useCallback(
		(i: number) => {
			patch((slice) => ({
				focusedIndex: {
					...(slice.focusedIndex as Record<number, number>),
					[activeCol]: i,
				},
			}));
		},
		[patch, activeCol],
	);

	const sendPath = useCallback(
		(newPath: string[]) => {
			patch(() => ({ pendingDepth: newPath.length }));
			send({ op: OP_NOTIFY, ref: path, payload: { path: newPath } });
		},
		[patch, path, send],
	);

	/** Open `key` from column `colIdx`: everything right of it is replaced. */
	const open = useCallback(
		(colIdx: number, key: string) => {
			containerRef.current?.focus();
			// Park this column's cursor on the row being opened before the
			// response lands, so popping back returns here. Columns to the
			// right are about to be replaced, so their cursors go with them.
			const idx = columns[colIdx]?.entries.findIndex((e) => e.key === key) ?? -1;
			patch((slice) => {
				const prev = (slice.focusedIndex ?? {}) as Record<number, number>;
				const kept: Record<number, number> = {};
				for (const k of Object.keys(prev)) {
					const i = Number(k);
					if (i < colIdx) kept[i] = prev[i];
				}
				if (idx >= 0) kept[colIdx] = idx;
				return { focusedIndex: kept };
			});
			sendPath([...cursorPath.slice(0, colIdx), key]);
		},
		[columns, cursorPath, patch, sendPath],
	);

	const drill = useCallback(() => {
		const entry = columns[activeCol]?.entries[cursorIdx];
		if (entry?.navigable) open(activeCol, entry.key);
	}, [columns, activeCol, cursorIdx, open]);

	const pop = useCallback(() => {
		if (cursorPath.length === 0) return;
		sendPath(cursorPath.slice(0, -1));
	}, [cursorPath, sendPath]);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLDivElement>) => {
			const col = columns[activeCol];
			if (!col) return;
			const last = col.entries.length - 1;
			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					setCursor(Math.min(last, cursorIdx + 1));
					break;
				case "ArrowUp":
					e.preventDefault();
					setCursor(Math.max(0, cursorIdx - 1));
					break;
				case "PageDown":
					e.preventDefault();
					setCursor(Math.min(last, cursorIdx + 10));
					break;
				case "PageUp":
					e.preventDefault();
					setCursor(Math.max(0, cursorIdx - 10));
					break;
				case "Home":
					e.preventDefault();
					setCursor(0);
					break;
				case "End":
					e.preventDefault();
					setCursor(Math.max(0, last));
					break;
				case "ArrowRight":
				case "Enter":
					e.preventDefault();
					drill();
					break;
				case "ArrowLeft":
				case "Escape":
					e.preventDefault();
					pop();
					break;
			}
		},
		[columns, activeCol, cursorIdx, setCursor, drill, pop],
	);

	// Keep the live column in view when the path gets *deeper*. Without this a
	// deep path walks off the right edge and the keyboard cursor ends up
	// somewhere you cannot see.
	//
	// Only on the way in. Pinning to scrollWidth after a pop yanks the view
	// left by a whole column on top of the column already vanishing, which
	// reads as the surface dropping out from under you. On the way back the
	// browser's own clamp is the gentler answer, and it only moves at all when
	// the removed column was the one holding the scroll.
	const prevCount = useRef(columns.length);
	useLayoutEffect(() => {
		const el = containerRef.current;
		const grew = columns.length > prevCount.current;
		prevCount.current = columns.length;
		if (el && (grew || (pendingDepth !== null && pendingDepth >= columns.length))) {
			el.scrollLeft = el.scrollWidth;
		}
	}, [columns.length, pendingDepth]);

	// Ensure the slice's setLocal spot isn't left stale between mounts.
	useEffect(() => {
		if (!value) setLocal(path, { path: [], columns: [] });
	}, [path, value, setLocal]);

	const rowId = useCallback((colIdx: number, i: number) => `${path}-r${colIdx}-${i}`, [path]);

	// A drill is in flight and it goes deeper than what is painted: show the
	// column arriving. A pop needs no placeholder, it only removes.
	const showSkeleton = pendingDepth !== null && pendingDepth >= columns.length;

	return (
		<div className={lensRoot}>
			<div className={lensBar}>
				<PathTrail path={cursorPath} onJump={(d) => sendPath(cursorPath.slice(0, d))} />
				<div className={lensBarHint}>
					<span className={lensHintPair}>
						<Kbd aria-label="Up arrow">&#8593;</Kbd>
						<Kbd aria-label="Down arrow">&#8595;</Kbd>
						move
					</span>
					<span className={lensHintPair}>
						<Kbd aria-label="Right arrow">&#8594;</Kbd>
						open
					</span>
					<span className={lensHintPair}>
						<Kbd aria-label="Left arrow">&#8592;</Kbd>
						back
					</span>
				</div>
			</div>

			<div
				ref={containerRef}
				tabIndex={0}
				onKeyDown={onKeyDown}
				role="tree"
				aria-label="Nu Shape lens"
				aria-activedescendant={columns.length ? rowId(activeCol, cursorIdx) : undefined}
				className={lensColumns}
			>
				{columns.map((col, i) => (
					<ColumnPanel
						// biome-ignore lint/suspicious/noArrayIndexKey: columns are position-indexed by design
						key={`${path}-col-${i}`}
						col={col}
						colIdx={i}
						active={i === activeCol && !showSkeleton}
						trailKey={cursorPath[i] ?? null}
						cursorIdx={cursorIdx}
						rowId={rowId}
						onOpen={open}
					/>
				))}
				{showSkeleton ? <SkeletonColumn /> : null}
				{columns.length === 0 && !showSkeleton ? (
					<>
						<SkeletonColumn />
						<SkeletonColumn />
					</>
				) : null}
				<div className={lensFiller} aria-hidden="true">
					<div className={lensFillerHead} />
				</div>
			</div>
		</div>
	);
}

export const LensRef: RefEntry = { factory, component: LensView };
