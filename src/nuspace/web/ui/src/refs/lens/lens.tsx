// LensRef -- Miller-columns browser for any Nu Shape.
//
// Server-owned. Every `write` frame carries a full replace:
//   {action: "replace", path: string[], columns: Column[]}
// The browser mirrors that into the slice and renders. Notify frames flow
// the other way with {action: "push", segment} on click / ArrowRight,
// {action: "pop"} on ArrowLeft / Escape, or {action: "replace", path} for
// keyboard shortcuts we may add later. Up / Down move focus locally in
// the active column with no wire hit.
//
// Column kind palette leans on the kit chart-N categorical tokens so we
// pick up theme colors for free (no bespoke lens tokens today).

import { OP_NOTIFY } from "@nustackdev/ui-core";
import type { RefEntry, SliceFactory } from "@nustackdev/ui-kit";
import { useStore } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo, useRef } from "react";

type Entry = {
	key: string;
	kind: string;
	preview: string;
	navigable: boolean;
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

const KIND_COLOR: Record<string, string> = {
	shape: "var(--chart-1)",
	mapping: "var(--chart-2)",
	sequence: "var(--chart-3)",
	leaf: "var(--chart-4)",
	unknown: "var(--chart-8)",
};

function _kindColor(kind: string): string {
	return KIND_COLOR[kind] ?? KIND_COLOR.unknown;
}

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
		write: (v) =>
			ctx.set((refs) => {
				const slice = refs[path];
				if (!slice) return;
				const p = (v ?? {}) as { action?: unknown } & Record<string, unknown>;
				const action = p.action;
				if (action === "replace") {
					slice.value = {
						path: Array.isArray(p.path) ? p.path.map((s) => String(s)) : [],
						columns: Array.isArray(p.columns) ? (p.columns as Column[]) : [],
					};
					slice.focusedIndex = {};
				} else if (action === "append") {
					const cur = slice.value as LensValue;
					const seg = p.segment != null ? String(p.segment) : "";
					const col = (p.column as Column | undefined) ?? {
						kind: "unknown",
						entries: [],
						total: 0,
					};
					slice.value = {
						path: [...cur.path, seg],
						columns: [...cur.columns, col],
					};
				} else if (action === "pop") {
					const cur = slice.value as LensValue;
					slice.value = {
						path: cur.path.slice(0, -1),
						columns: cur.columns.slice(0, -1),
					};
				}
			}),
	};
};

function ColumnPanel({
	path,
	colIdx,
	col,
	focused,
	active,
	onFocus,
	onDrill,
	onSetActive,
}: {
	path: string;
	colIdx: number;
	col: Column;
	focused: number;
	active: boolean;
	onFocus: (i: number) => void;
	onDrill: (segment: string) => void;
	onSetActive: () => void;
}) {
	const rowRefs = useRef<Array<HTMLButtonElement | null>>([]);
	useEffect(() => {
		if (active) rowRefs.current[focused]?.focus();
	}, [active, focused]);

	const kindLabel = col.kind;
	const truncated = col.total > col.entries.length;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: hover/focus tracking on a plain container
		<div
			className="flex flex-col gap-1 border-r border-border/60 min-w-[220px] max-w-[340px] w-[260px] shrink-0"
			onFocus={onSetActive}
			onMouseEnter={onSetActive}
		>
			<div className="px-3 py-2 text-xs uppercase tracking-wide text-muted-foreground font-mono border-b border-border/60">
				<span
					className="inline-block size-2 rounded-full mr-2 align-middle"
					style={{ backgroundColor: _kindColor(kindLabel) }}
				/>
				{kindLabel}{" "}
				{truncated ? `(${col.entries.length}/${col.total})` : `(${col.total})`}
			</div>
			<div className="flex-1 min-h-0 overflow-y-auto">
				{col.entries.length === 0 ? (
					<div className="px-3 py-2 text-xs text-muted-foreground font-mono">
						empty
					</div>
				) : (
					col.entries.map((e, i) => {
						const isFocused = active && i === focused;
						const rowKey = `${colIdx}::${i}::${e.key}`;
						return (
							<button
								// biome-ignore lint/suspicious/noArrayIndexKey: server-driven list, index is stable per replace
								key={rowKey}
								type="button"
								ref={(el) => {
									rowRefs.current[i] = el;
								}}
								onFocus={() => onFocus(i)}
								onClick={() => {
									onFocus(i);
									if (e.navigable) onDrill(e.key);
								}}
								className={
									"w-full text-left px-3 py-1.5 text-sm font-mono flex items-center gap-2 " +
									"outline-none transition-colors " +
									(isFocused
										? "bg-primary/10 text-text-primary"
										: "hover:bg-muted/40 text-text-primary")
								}
								data-path={path}
							>
								<span
									className="inline-block size-2 rounded-full shrink-0"
									style={{ backgroundColor: _kindColor(e.kind) }}
								/>
								<span className="truncate flex-1">{e.key}</span>
								{e.preview ? (
									<span className="text-xs text-muted-foreground truncate max-w-[60%]">
										{e.preview}
									</span>
								) : null}
							</button>
						);
					})
				)}
			</div>
		</div>
	);
}

function LensView({ path }: { path: string }) {
	const value = useStore((s) => s.refs[path]?.value as LensValue | undefined);
	const focused = useStore(
		(s) =>
			(s.refs[path]?.focusedIndex as Record<number, number> | undefined) ?? {},
	);
	const setLocal = useStore((s) => s.setLocal);
	const set = useStore.setState;
	const send = useStore((s) => s.send);
	const containerRef = useRef<HTMLDivElement | null>(null);
	const activeColRef = useRef<number>(0);

	const columns = value?.columns ?? [];
	const cursorPath = value?.path ?? [];
	const activeCol = Math.max(0, columns.length - 1);

	const setFocused = useCallback(
		(colIdx: number, i: number) => {
			set((s) => {
				const slice = s.refs[path];
				if (!slice) return s;
				const next = { ...(slice.focusedIndex as Record<number, number>) };
				next[colIdx] = i;
				return {
					...s,
					refs: { ...s.refs, [path]: { ...slice, focusedIndex: next } },
				};
			});
		},
		[path],
	);

	const notify = useCallback(
		(payload: Record<string, unknown>) => {
			send({ op: OP_NOTIFY, ref: path, payload });
		},
		[path, send],
	);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLDivElement>) => {
			const colIdx = activeColRef.current;
			const col = columns[colIdx];
			if (!col) return;
			const cur = focused[colIdx] ?? 0;
			if (e.key === "ArrowDown") {
				e.preventDefault();
				setFocused(colIdx, Math.min(col.entries.length - 1, cur + 1));
			} else if (e.key === "ArrowUp") {
				e.preventDefault();
				setFocused(colIdx, Math.max(0, cur - 1));
			} else if (e.key === "ArrowRight" || e.key === "Enter") {
				e.preventDefault();
				const entry = col.entries[cur];
				if (entry?.navigable) notify({ action: "push", segment: entry.key });
			} else if (e.key === "ArrowLeft" || e.key === "Escape") {
				e.preventDefault();
				notify({ action: "pop" });
			}
		},
		[columns, focused, notify, setFocused],
	);

	const breadcrumb = useMemo(
		() => ["root", ...cursorPath].join(" › "),
		[cursorPath],
	);

	// Ensure the slice's setLocal spot isn't left stale between mounts.
	useEffect(() => {
		if (!value) setLocal(path, { path: [], columns: [] });
	}, [path, value, setLocal]);

	return (
		<div className="flex flex-col h-[70vh] min-h-[400px] border rounded-md overflow-hidden bg-card">
			<div className="px-3 py-2 border-b border-border/60 text-xs text-muted-foreground font-mono flex items-center justify-between">
				<span>{breadcrumb}</span>
				<span className="text-[10px] uppercase tracking-wider">
					arrow keys navigate · enter to drill · esc to pop
				</span>
			</div>
			<div
				ref={containerRef}
				tabIndex={0}
				onKeyDown={onKeyDown}
				role="tree"
				aria-label="Nu Shape lens"
				className="flex-1 min-h-0 flex overflow-x-auto overflow-y-hidden outline-none"
			>
				{columns.map((col, i) => (
					<ColumnPanel
						// biome-ignore lint/suspicious/noArrayIndexKey: columns are position-indexed by design
						key={`${path}-col-${i}`}
						path={path}
						colIdx={i}
						col={col}
						focused={focused[i] ?? 0}
						active={i === activeCol}
						onFocus={(idx) => setFocused(i, idx)}
						onDrill={(segment) => notify({ action: "push", segment })}
						onSetActive={() => {
							activeColRef.current = i;
						}}
					/>
				))}
				{columns.length === 0 ? (
					<div className="p-6 text-sm text-muted-foreground font-mono">
						waiting for lens columns...
					</div>
				) : null}
			</div>
		</div>
	);
}

export const LensRef: RefEntry = { factory, component: LensView };
