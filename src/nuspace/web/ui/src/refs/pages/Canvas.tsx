// The block canvas. This is the editor.
//
// Everything structural lives here and nowhere else: ordering, keyboard,
// selection, focus routing, the slash menu, drag reorder, block lifecycle. No
// library supplies any of it, because no library knows what a running Nu
// section is.
//
// ## Every block is a program, and this file is where that shows
//
// There is no block type to branch on. Each block below renders its `fields`
// -- the ui refs its program mounted -- through the kit's `FieldView`, text
// blocks included: a text block's program holds a `ProseRef`, so its
// paragraph arrives by exactly the same route as a program block's slider.
//
// `tpl` is read in one place, `bare` below, and only to choose how much
// chrome to wrap around that. A text block came from the wysiwyg template, so
// it gets a document surface and nothing else. Anything else is arbitrary
// code, so it gets the status pill, the mount prefix and the code toggle.
// That is an affordance, not a dispatch: both sides compile, run, are
// supervised and report status identically.
//
// ## The two selection regimes
//
// Inside a text block you get a caret and everything a text editor gives
// you. Across a block boundary you get *block* selection, because selecting
// through a running program and retyping it is not an operation with a
// definition. The canvas owns the transition between the two:
//
//   - arrowing out of a text block's last line moves to the next block
//   - if that block is text, or a program already open in code mode, the
//     caret enters it, carrying its column
//   - otherwise the block gets *selected* and the canvas takes keyboard focus
//
// So vertical travel through a document reads as: caret, caret, [block
// selected], caret. One extra keypress per live program block, which is
// honest -- there is nowhere in a running program for a caret to be.
//
// ## Focus after a structural op
//
// Creating, splitting and merging all round-trip through the server, and the
// new block's id is only known once `set_page` comes back. Rather than have
// the server echo browser intent, the canvas records a *positional* intent
// ("the block after X") and resolves it against the next block list.

import {
	Alert,
	AlertDescription,
	AlertIcon,
	AlertTitle,
	FieldView,
	IconButton,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { GripVertical, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import {
	docAppendBlock,
	docBlock,
	docColumn,
	docDragHandle,
	docDropIndicator,
	docFocusRail,
	docGutter,
	docGutterAffordances,
	docStatusRail,
	docStatusTrace,
	docTextBlock,
	hasGutterRail,
	SECTION_STATUS,
} from "../../design";
import type { Notify } from "./ops";
import { ProgramBlock } from "./Program";
import {
	type BlockProse,
	BlockProseContext,
	type ExitDir,
	type InsertTpl,
	type ProseHandle,
	proseValue,
} from "./ProseRef";
import { filterSlash, type SlashItem, SlashMenu } from "./Slash";
import { type EditorState, type FocusReq, patchEditor, useEditorState } from "./slice";
import type { ActivePage, Block } from "./types";

/**
 * The markdown a text block currently holds, read off its own ref.
 *
 * The page payload does not carry it: a text block's content lives on its
 * `ProseRef`, which is where the browser already has it and where a
 * keystroke lands without reshipping the page. A neighbour that needs it --
 * merge-up joining two blocks -- reads it from there. The path is whatever
 * the block's program mounted, so nothing here hardcodes a naming scheme.
 */
function blockText(block: Block): string {
	const field = block.fields.find((f) => f.type === "ProseRef");
	return field ? proseValue(field.path) : "";
}

export function Canvas({
	refPath,
	page,
	notify,
}: {
	refPath: string;
	page: ActivePage;
	notify: Notify;
}) {
	const editor = useEditorState(refPath);
	const blocks = page.blocks;
	const pagePath = page.path;

	const rootRef = useRef<HTMLDivElement | null>(null);
	const elRefs = useRef(new Map<string, HTMLElement>());
	const proseHandles = useRef(new Map<string, ProseHandle | null>());
	/** Positional focus intent, resolved on the next block list. */
	const pendingAfter = useRef<{ afterId: string; edit: boolean } | null>(null);

	const index = useCallback((id: string) => blocks.findIndex((b) => b.id === id), [blocks]);

	const patch = useCallback(
		(p: Partial<EditorState> | ((e: EditorState) => Partial<EditorState>)) =>
			patchEditor(refPath, p),
		[refPath],
	);

	// -- focus routing --------------------------------------------------------

	const focusBlock = useCallback(
		(block: Block, req: Omit<FocusReq, "blockId">, editing: string[]) => {
			const enterable = block.tpl === "text" || editing.includes(block.id);
			if (enterable) {
				patch({
					focus: { blockId: block.id, ...req },
					selected: [],
					anchor: null,
					column: null,
				});
				return;
			}
			// A live program block has no text for a caret to sit in. Select it,
			// and park the column so the next hop still lands under the caret.
			patch({
				focus: null,
				selected: [block.id],
				anchor: block.id,
				column: req.column ?? null,
				x: req.x ?? null,
			});
			rootRef.current?.focus({ preventScroll: true });
			elRefs.current.get(block.id)?.scrollIntoView({ block: "nearest" });
		},
		[patch],
	);

	const step = useCallback(
		(fromId: string, dir: ExitDir, column: number | undefined, x?: number) => {
			const i = index(fromId);
			const j = dir === "up" ? i - 1 : i + 1;
			if (i < 0 || j < 0 || j >= blocks.length) return;
			focusBlock(blocks[j], { place: dir === "up" ? "end" : "start", column, x }, editor.editing);
		},
		[blocks, editor.editing, focusBlock, index],
	);

	const enterBlock = useCallback(
		(block: Block, place: "start" | "end" = "end") => {
			if (block.tpl === "text") {
				patch({
					focus: { blockId: block.id, place },
					selected: [],
					anchor: null,
				});
				return;
			}
			patch((e) => ({
				editing: e.editing.includes(block.id) ? e.editing : [...e.editing, block.id],
				focus: { blockId: block.id, place },
				selected: [],
				anchor: null,
			}));
		},
		[patch],
	);

	// Resolve a positional focus intent once the new block list arrives.
	useEffect(() => {
		const p = pendingAfter.current;
		if (!p) return;
		const i = blocks.findIndex((b) => b.id === p.afterId);
		if (i < 0 || i + 1 >= blocks.length) return;
		pendingAfter.current = null;
		const target = blocks[i + 1];
		if (target.tpl === "text") {
			patch({ focus: { blockId: target.id, place: "start" }, selected: [] });
		} else {
			patch((e) => ({
				editing: e.editing.includes(target.id) ? e.editing : [...e.editing, target.id],
				focus: { blockId: target.id, place: "start" },
				selected: [],
			}));
		}
	}, [blocks, patch]);

	// -- structural ops -------------------------------------------------------

	const commitSource = useCallback(
		(id: string, content: string) => {
			notify("block.update", { page_path: pagePath, block_id: id, content });
		},
		[notify, pagePath],
	);

	// Empty content for a program means "use the tpl's starter". The skeleton
	// lives once, in `nuspace/core/tpl.py`, not in two places that can drift.
	const createAfter = useCallback(
		(afterId: string | null, tpl: "text" | "program", content = "") => {
			if (afterId) pendingAfter.current = { afterId, edit: tpl === "program" };
			notify("block.create", { page_path: pagePath, tpl, content, after: afterId });
		},
		[notify, pagePath],
	);

	const splitBlock = useCallback(
		(id: string, head: string, tail: string, insert: InsertTpl) => {
			pendingAfter.current = { afterId: id, edit: insert === "program" };
			notify("block.split", {
				page_path: pagePath,
				block_id: id,
				head,
				tail,
				insert: insert === null ? null : { tpl: insert, content: "" },
			});
		},
		[notify, pagePath],
	);

	const deleteBlocks = useCallback(
		(ids: string[]) => {
			if (ids.length === 0) return;
			const first = index(ids[0]);
			const prev = first > 0 ? blocks[first - 1] : null;
			notify("block.delete", { page_path: pagePath, block_ids: ids });
			patch({
				selected: prev ? [prev.id] : [],
				anchor: prev ? prev.id : null,
				focus: null,
				editing: editor.editing.filter((e) => !ids.includes(e)),
			});
		},
		[blocks, editor.editing, index, notify, pagePath, patch],
	);

	const mergeUp = useCallback(
		(id: string, text: string) => {
			const i = index(id);
			if (i <= 0) return;
			const prev = blocks[i - 1];
			if (prev.tpl === "text") {
				const above = blockText(prev);
				const seam = above.length + (above && text ? 1 : 0);
				const joined = above && text ? `${above}\n${text}` : above + text;
				notify("block.merge", {
					page_path: pagePath,
					block_id: id,
					into_id: prev.id,
					content: joined,
				});
				patch({
					focus: { blockId: prev.id, place: "end", offset: seam },
					selected: [],
					anchor: null,
				});
				return;
			}
			// A program block sits above. Deleting an empty text block is what
			// you meant; swallowing a program block is not.
			if (text.trim() === "") {
				deleteBlocks([id]);
				return;
			}
			patch({ focus: null, selected: [prev.id], anchor: prev.id });
			rootRef.current?.focus({ preventScroll: true });
		},
		[blocks, deleteBlocks, index, notify, pagePath, patch],
	);

	const moveSelected = useCallback(
		(dir: -1 | 1) => {
			const sel = new Set(editor.selected);
			if (sel.size === 0) return;
			const ids = blocks.map((b) => b.id);
			const picked = ids.filter((i) => sel.has(i));
			const first = ids.indexOf(picked[0]);
			const last = ids.indexOf(picked[picked.length - 1]);
			if (dir < 0 && first === 0) return;
			if (dir > 0 && last === ids.length - 1) return;
			const rest = ids.filter((i) => !sel.has(i));
			const anchorIdx = dir < 0 ? first - 1 : last + 1;
			const anchorId = ids[anchorIdx];
			const at = rest.indexOf(anchorId) + (dir < 0 ? 0 : 1);
			rest.splice(at, 0, ...picked);
			notify("block.reorder", { page_path: pagePath, order: rest });
		},
		[blocks, editor.selected, notify, pagePath],
	);

	// -- canvas-level keyboard (block selection regime) ------------------------

	const onCanvasKey = useCallback(
		(e: React.KeyboardEvent) => {
			const sel = editor.selected;
			if (sel.length === 0) return;
			const ids = blocks.map((b) => b.id);
			const first = ids.indexOf(sel[0]);
			const last = ids.indexOf(sel[sel.length - 1]);

			if (e.key === "Escape") {
				e.preventDefault();
				patch({ selected: [], anchor: null });
				return;
			}
			if (e.key === "Enter") {
				e.preventDefault();
				const b = blocks[last];
				if (b) enterBlock(b);
				return;
			}
			if (e.key === "Backspace" || e.key === "Delete") {
				e.preventDefault();
				deleteBlocks(sel);
				return;
			}
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") {
				e.preventDefault();
				patch({ selected: ids, anchor: ids[0] ?? null });
				return;
			}
			if (e.key === "ArrowUp" || e.key === "ArrowDown") {
				e.preventDefault();
				const dir = e.key === "ArrowUp" ? -1 : 1;
				if (e.metaKey || e.ctrlKey) {
					moveSelected(dir);
					return;
				}
				if (e.shiftKey) {
					const anchor = editor.anchor ?? sel[0];
					const a = ids.indexOf(anchor);
					const head = dir < 0 ? first - 1 : last + 1;
					if (head < 0 || head >= ids.length) return;
					const lo = Math.min(a, head);
					const hi = Math.max(a, head);
					patch({ selected: ids.slice(lo, hi + 1), anchor });
					return;
				}
				const j = dir < 0 ? first - 1 : last + 1;
				if (j < 0 || j >= ids.length) return;
				const target = blocks[j];
				// Land the caret when the neighbour can hold one; otherwise the
				// selection just walks on, carrying the parked column with it.
				focusBlock(
					target,
					{
						place: dir < 0 ? "end" : "start",
						column: editor.column ?? undefined,
						x: editor.x ?? undefined,
					},
					editor.editing,
				);
				return;
			}
		},
		[
			blocks,
			deleteBlocks,
			editor.anchor,
			editor.column,
			editor.x,
			editor.editing,
			editor.selected,
			enterBlock,
			focusBlock,
			moveSelected,
			patch,
		],
	);

	// -- drag reorder ---------------------------------------------------------

	const dragRef = useRef<{ id: string; at: number } | null>(null);

	const dropIndexFor = useCallback(
		(clientY: number) => {
			let at = blocks.length;
			for (let i = 0; i < blocks.length; i++) {
				const el = elRefs.current.get(blocks[i].id);
				if (!el) continue;
				const r = el.getBoundingClientRect();
				if (clientY < r.top + r.height / 2) {
					at = i;
					break;
				}
			}
			return at;
		},
		[blocks],
	);

	const startDrag = useCallback(
		(e: React.PointerEvent, id: string) => {
			e.preventDefault();
			(e.target as HTMLElement).setPointerCapture?.(e.pointerId);
			dragRef.current = { id, at: index(id) };
			patch({
				drag: { id, at: index(id), y: e.clientY },
				selected: [id],
				anchor: id,
			});

			const move = (ev: PointerEvent) => {
				const at = dropIndexFor(ev.clientY);
				const cur = dragRef.current;
				if (!cur) return;
				dragRef.current = { ...cur, at };
				patch({ drag: { id: cur.id, at, y: ev.clientY } });
			};
			const up = () => {
				window.removeEventListener("pointermove", move);
				window.removeEventListener("pointerup", up);
				const cur = dragRef.current;
				dragRef.current = null;
				patch({ drag: null });
				if (!cur) return;
				const from = index(cur.id);
				if (from < 0 || cur.at === from || cur.at === from + 1) return;
				const ids = blocks.map((b) => b.id);
				const rest = ids.filter((i) => i !== cur.id);
				const at = cur.at > from ? cur.at - 1 : cur.at;
				rest.splice(at, 0, cur.id);
				notify("block.reorder", { page_path: pagePath, order: rest });
			};
			window.addEventListener("pointermove", move);
			window.addEventListener("pointerup", up);
		},
		[blocks, dropIndexFor, index, notify, pagePath, patch],
	);

	// -- slash menu -----------------------------------------------------------

	const slash = editor.slash;
	const slashItems = useMemo(() => (slash ? filterSlash(slash.query) : []), [slash]);

	const pickSlash = useCallback(
		(item: SlashItem) => {
			const s = editor.slash;
			if (!s) return;
			if (s.mode === "insert") {
				patch({ slash: null });
				if (item.action.act === "split") {
					createAfter(s.blockId, item.action.insert === "program" ? "program" : "text");
					return;
				}
				const seed = item.action.act === "prefix" ? item.action.prefix : item.action.text;
				createAfter(s.blockId, "text", seed);
				return;
			}
			proseHandles.current.get(s.blockId)?.applySlash(item.action);
		},
		[createAfter, editor.slash, patch],
	);

	const slashKey = useCallback(
		(key: string): boolean => {
			const s = editor.slash;
			if (!s) return false;
			const items = filterSlash(s.query);
			if (key === "ArrowDown" || key === "ArrowUp") {
				const d = key === "ArrowDown" ? 1 : -1;
				const n = Math.max(1, items.length);
				patch({ slash: { ...s, index: (s.index + d + n) % n } });
				return true;
			}
			if (key === "Enter") {
				const item = items[Math.min(s.index, items.length - 1)];
				if (item) pickSlash(item);
				return true;
			}
			if (key === "Escape") {
				patch({ slash: null });
				return true;
			}
			return false;
		},
		[editor.slash, patch, pickSlash],
	);

	// -- render ---------------------------------------------------------------

	const setEl = useCallback((id: string, el: HTMLElement | null) => {
		if (el) elRefs.current.set(id, el);
		else elRefs.current.delete(id);
	}, []);

	// Stable by construction. The bus below is rebuilt every render, so the
	// one thing a block's editor keeps across renders must not be.
	const registerHandle = useCallback((id: string, handle: ProseHandle | null) => {
		if (handle) proseHandles.current.set(id, handle);
		else proseHandles.current.delete(id);
	}, []);

	const drag = editor.drag;

	// -- where the caret actually is -------------------------------------------
	//
	// `editor.focus` is an intent and is consumed the instant a block honours
	// it, so it cannot answer "which block is the caret in" -- which is what
	// the gutter's focus rail needs. Focus events bubble (focusin/focusout), so
	// one listener on the canvas root reports the standing fact for every
	// editor inside it, including ones we do not own (ProseMirror, Monaco).

	const onCanvasFocus = useCallback(
		(e: React.FocusEvent) => {
			const host = (e.target as HTMLElement).closest?.("[data-block]");
			const id = host?.getAttribute("data-block") ?? null;
			patch((ed) => (ed.focused === id ? {} : { focused: id }));
		},
		[patch],
	);

	const onCanvasBlur = useCallback(
		(e: React.FocusEvent) => {
			// Focus moving between two editors inside the canvas fires blur
			// before focus; only a departure that leaves the canvas clears it.
			const next = e.relatedTarget as Node | null;
			if (next && rootRef.current?.contains(next)) return;
			patch((ed) => (ed.focused === null ? {} : { focused: null }));
		},
		[patch],
	);

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the canvas is the keyboard owner in block-selection mode
		<div
			ref={rootRef}
			tabIndex={-1}
			onKeyDown={onCanvasKey}
			onFocus={onCanvasFocus}
			onBlur={onCanvasBlur}
			className={`${docColumn} outline-none`}
		>
			{blocks.map((block, i) => {
				const selected = editor.selected.includes(block.id);
				const focusReq = editor.focus?.blockId === block.id ? editor.focus : null;
				const focused = editor.focused === block.id;
				// The ONE read of `tpl`, and it decides chrome, nothing else.
				const bare = block.tpl === "text";
				const state = block.status.state;
				return (
					// biome-ignore lint/a11y/noStaticElementInteractions: a mousedown anywhere in a block hands control to that block's own editor
					<div
						key={block.id}
						ref={(el) => setEl(block.id, el)}
						data-block={block.id}
						className={docBlock({
							selected,
							selectedStrong: selected && editor.selected.length > 1,
							focused,
							dragging: drag?.id === block.id,
							program: !bare,
						})}
						onMouseDown={(e) => {
							// A plain click inside a block leaves block-selection mode;
							// the block's own editor takes over from here.
							if (e.button === 0 && editor.selected.length > 0) {
								patch({ selected: [], anchor: null });
							}
						}}
					>
						{drag && drag.at === i ? <span className={`${docDropIndicator} top-0`} /> : null}
						{/* One rail slot. A status the author must act on wins over
						    "you are here", because a failing block is more urgent. */}
						{!bare && hasGutterRail(state) ? (
							<span className={docStatusRail(state)} />
						) : focused ? (
							<span className={docFocusRail} />
						) : null}
						<Gutter
							program={!bare}
							onDrag={(e) => startDrag(e, block.id)}
							onPlus={(rect) =>
								patch({
									slash: {
										blockId: block.id,
										mode: "insert",
										query: "",
										from: 0,
										to: 0,
										anchor: { x: rect.left + 24, y: rect.bottom },
										index: 0,
									},
								})
							}
							onSelect={() => {
								patch({
									selected: [block.id],
									anchor: block.id,
									focus: null,
								});
								rootRef.current?.focus({ preventScroll: true });
							}}
						/>
						{bare ? (
							<TextBlock
								block={block}
								bus={{
									blockId: block.id,
									focusReq,
									slashFrom:
										slash && slash.mode === "inline" && slash.blockId === block.id
											? slash.from
											: null,
									onFocusConsumed: () => patch({ focus: null }),
									onExit: (dir, column, x) => step(block.id, dir, column, x),
									onMergeUp: (text) => mergeUp(block.id, text),
									onSplit: (head, tail, insert) => splitBlock(block.id, head, tail, insert),
									onSlashOpen: (offset, anchor) =>
										patch({
											slash: {
												blockId: block.id,
												mode: "inline",
												query: "",
												from: offset,
												to: offset + 1,
												anchor,
												index: 0,
											},
										}),
									onSlashQuery: (query) =>
										patch((e) => (e.slash ? { slash: { ...e.slash, query, index: 0 } } : {})),
									onSlashClose: () => patch({ slash: null }),
									onSlashKey: slashKey,
									onSelectSelf: () => {
										patch({ selected: [block.id], anchor: block.id, focus: null });
										rootRef.current?.focus({ preventScroll: true });
									},
									registerHandle,
								}}
							/>
						) : (
							<ProgramBlock
								blockId={block.id}
								source={block.source}
								fields={block.fields}
								status={block.status}
								editing={editor.editing.includes(block.id)}
								focusReq={focusReq}
								onFocusConsumed={() => patch({ focus: null })}
								onCommit={(src) => commitSource(block.id, src)}
								onExit={(dir, column) => step(block.id, dir, column)}
								onSelectSelf={() => {
									patch({
										selected: [block.id],
										anchor: block.id,
										focus: null,
									});
									rootRef.current?.focus({ preventScroll: true });
								}}
								onSetEditing={(on) =>
									patch((e) => ({
										editing: on
											? [...e.editing, block.id]
											: e.editing.filter((x) => x !== block.id),
										focus: on ? { blockId: block.id, place: "end" } : e.focus,
									}))
								}
								onRestart={() => notify("block.restart", { block_id: block.id })}
							/>
						)}
					</div>
				);
			})}
			{drag && drag.at >= blocks.length ? (
				<div className="relative h-0">
					<span className={docDropIndicator} />
				</div>
			) : null}

			<button
				type="button"
				onClick={() => createAfter(blocks.length ? blocks[blocks.length - 1].id : null, "text")}
				className={docAppendBlock}
			>
				Click to write, or press / for blocks
			</button>

			{slash ? (
				<SlashMenu
					items={slashItems}
					index={slash.index}
					anchor={slash.anchor}
					takeFocus={slash.mode === "insert"}
					onPick={pickSlash}
					onMove={(d) =>
						patch((e) =>
							e.slash
								? {
										slash: {
											...e.slash,
											index:
												(e.slash.index + d + Math.max(1, slashItems.length)) %
												Math.max(1, slashItems.length),
										},
									}
								: {},
						)
					}
					onClose={() => patch({ slash: null })}
				/>
			) : null}
		</div>
	);
}

/**
 * A text block: its program's ui refs, and nothing else.
 *
 * No status pill, no mount prefix, no code toggle. Not because a text block
 * is a different substance -- it compiles, runs and is supervised like every
 * other block -- but because it came from a template nobody typed, so there
 * is nothing about the program for a reader to act on. What is left is the
 * document, which is the whole point.
 *
 * The fields come through `FieldView` exactly as a program block's do. The
 * one the template mounts is a `ProseRef`, and nuspace's entry for it (see
 * ./ProseRef.tsx) reads the bus off the context provided here to rebuild the
 * block-boundary behaviour the kit's editor deliberately leaves out.
 *
 * A status that says the program is broken is still shown: the template
 * failing means nuspace is broken, and a silent blank block would hide it.
 */
function TextBlock({ block, bus }: { block: Block; bus: BlockProse }) {
	const token = SECTION_STATUS[block.status.state];
	return (
		<BlockProseContext.Provider value={bus}>
			<div className={docTextBlock}>
				{block.status.error ? (
					<Alert tone={token.tone}>
						<AlertIcon />
						<div className="min-w-0 flex-1">
							<AlertTitle>
								{block.status.state === "invalid" ? "does not compile" : "ran and died"}
							</AlertTitle>
							<AlertDescription className={docStatusTrace}>{block.status.error}</AlertDescription>
						</div>
					</Alert>
				) : null}
				{block.fields.map((f) => (
					<FieldView key={f.path} field={f} />
				))}
			</div>
		</BlockProseContext.Provider>
	);
}

/**
 * A block's affordances, hung in the gutter outside the reading column.
 *
 * Two kit `IconButton`s on one row, so they share a box, a hover tier, a focus
 * ring and a reveal. The only thing the document layer adds is the grab cursor
 * on the handle. Both carry a tooltip: a bare glyph in a margin is not
 * self-explanatory, and `title` is not an affordance, it is a delay.
 */
function Gutter({
	program,
	onDrag,
	onPlus,
	onSelect,
}: {
	program: boolean;
	onDrag: (e: React.PointerEvent) => void;
	onPlus: (rect: DOMRect) => void;
	onSelect: () => void;
}) {
	return (
		<div className={docGutter(program)}>
			<div className={docGutterAffordances}>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="Insert block below"
							onClick={(e) => onPlus(e.currentTarget.getBoundingClientRect())}
						>
							<Plus />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="top">insert block below</TooltipContent>
				</Tooltip>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="Drag to reorder, click to select"
							onPointerDown={onDrag}
							onClick={onSelect}
							data-block-grip=""
							className={docDragHandle}
						>
							<GripVertical />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="top">drag to reorder, click to select</TooltipContent>
				</Tooltip>
			</div>
		</div>
	);
}
