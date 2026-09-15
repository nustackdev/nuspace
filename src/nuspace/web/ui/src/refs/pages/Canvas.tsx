// The block canvas. This is the editor.
//
// Everything structural lives here and nowhere else: ordering, keyboard,
// selection, focus routing, the slash menu, drag reorder, block lifecycle. No
// library supplies any of it, because no library knows what a running Nu
// section is.
//
// ## Every block is a program, and this file is where that shows
//
// There is no block type to branch on. Each block below renders the subtree
// at its own address -- the ui refs its program mounted, which arrive as
// ordinary nodes -- through `NodeView`, text blocks included: a text block's
// program holds a `ProseRef`, so its paragraph arrives by exactly the same
// route as a program block's slider. See ./blocks.ts for where that address
// is and what is still open about it.
//
// `tpl` is read in one place, `bare` below, and only to choose which interior
// renders the block's output: a prose surface with block-boundary keyboard, or
// a program's alert-and-fields stack. It decides nothing else. Every block,
// whatever made it, is wrapped by the same `docBlock` and gets the same gutter
// with the same three rows -- add and drag, copy the section id, open the
// source -- because every block compiles, runs, is supervised and reports
// status identically, and chrome that pretended otherwise was lying.
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
// A create round-trips through the server. The id does not: the browser mints
// it and sends it, so focus is aimed at a known id rather than guessed at from
// a position once `set_page` comes back.
//
// ## Split and merge are compositions, not verbs
//
// The server has one op per thing that happens to a section: create, update,
// delete, move, reorder. A split is an update plus a create at the next
// index; a merge-up is an update plus a delete. Both halves are independent
// writes to different sections, so which arm runs first does not matter, and
// the server never grows a verb per editor gesture.
//
// What neither carries is *prose*. A text block's content is not its source
// -- the source is the template, and the content lives in the space's kv
// under the block's own namespace, written by the block's own running
// program through its `ProseRef`. So a split moves structure here and the
// text follows through the refs, which means it does not follow at all until
// something is running the sections. See the report for task-145.

import type { Path } from "@nustackdev/ui-core";
import {
	Alert,
	AlertDescription,
	AlertIcon,
	AlertTitle,
	IconButton,
	NodeView,
	pathKey,
	Toggle,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Check, Code, Copy, GripVertical, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SectionStatusDot } from "../../components";
import {
	docAppendBlock,
	docBlock,
	docColumn,
	docDragHandle,
	docDropIndicator,
	docFocusRail,
	docGutter,
	docGutterAffordances,
	docGutterRow,
	docGutterToggle,
	docStatusRail,
	docStatusTrace,
	docTextBlock,
	hasGutterRail,
	SECTION_STATUS,
} from "../../design";
import { blockText, blockUiPath } from "./blocks";
import { SourceEditor } from "./Code";
import type { Notify } from "./ops";
import { ProgramBlock } from "./Program";
import {
	type BlockProse,
	BlockProseContext,
	type ExitDir,
	type InsertTpl,
	type ProseHandle,
} from "./ProseRef";
import { filterSlash, type SlashItem, SlashMenu } from "./Slash";
import { type EditorState, type FocusReq, patchEditor, useEditorState } from "./state";
import { type ActivePage, type Block, type BlockTpl, mintId, type SectionState } from "./types";

/**
 * What the gutter's status dot reports, for now.
 *
 * Hardcoded while the supervisor's per-block state is still settling: an
 * always-green dot is a placeholder nobody will read as truth, whereas a dot
 * that wobbles between real and invented states would be worse than none. To
 * go live, delete this and hand `Gutter` the block's own `status.state` at
 * the call site below -- the dot already renders all six.
 */
const GUTTER_STATUS: SectionState = "running";

export function Canvas({
	refPath,
	page,
	starters,
	notify,
}: {
	refPath: Path;
	page: ActivePage;
	/** What a block of each tpl starts life as, off the ref's props.
	 *  `nuspace/core/tpl.py` is the one spelling of these. */
	starters: Record<string, string>;
	notify: Notify;
}) {
	const editor = useEditorState(refPath);
	const blocks = page.blocks;
	const pageId = page.page_id;
	const refKey = pathKey(refPath);

	const rootRef = useRef<HTMLDivElement | null>(null);
	const elRefs = useRef(new Map<string, HTMLElement>());
	const proseHandles = useRef(new Map<string, ProseHandle | null>());
	/** Focus intent for a block that has been asked for but not shipped back
	 *  yet. `set_page` prunes focus pointing at a block it does not carry, so
	 *  the intent is parked here until the block actually arrives. */
	const pendingFocus = useRef<{ id: string; edit: boolean } | null>(null);

	const index = useCallback((id: string) => blocks.findIndex((b) => b.id === id), [blocks]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const patch = useCallback(
		(p: Partial<EditorState> | ((e: EditorState) => Partial<EditorState>)) =>
			patchEditor(refPath, p),
		[refKey],
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

	/**
	 * Open or close a block's source editor.
	 *
	 * The caret follows the editor open only for a program block. A text block
	 * has prose to hold it, and it keeps holding it while the source sits
	 * alongside -- opening the template to read it is not a request to leave
	 * the paragraph you were writing.
	 */
	const setEditing = useCallback(
		(id: string, on: boolean) => {
			const bare = blocks[index(id)]?.tpl === "text";
			patch((e) => ({
				editing: on
					? e.editing.includes(id)
						? e.editing
						: [...e.editing, id]
					: e.editing.filter((x) => x !== id),
				focus: on && !bare ? { blockId: id, place: "end" } : e.focus,
			}));
		},
		[blocks, index, patch],
	);

	// Land the caret in a newly created block, once the server confirms it.
	useEffect(() => {
		const want = pendingFocus.current;
		if (!want) return;
		if (!blocks.some((b) => b.id === want.id)) return;
		pendingFocus.current = null;
		patch((e) => ({
			editing: want.edit && !e.editing.includes(want.id) ? [...e.editing, want.id] : e.editing,
			focus: { blockId: want.id, place: "start" },
			selected: [],
		}));
	}, [blocks, patch]);

	// -- structural ops -------------------------------------------------------

	const commitSource = useCallback(
		(id: string, source: string) => {
			notify("section.update", { page_id: pageId, section_id: id, source });
		},
		[notify, pageId],
	);

	/**
	 * Add a block after `afterId` (or last), and aim the caret at it.
	 *
	 * `source` empty means "the tpl's starter", which arrived in the mount
	 * rather than being written here: a template that exists in two languages
	 * is a template that drifts.
	 */
	const createAfter = useCallback(
		(afterId: string | null, tpl: BlockTpl, source = "") => {
			const id = mintId("s");
			const at = afterId ? index(afterId) : -1;
			notify("section.create", {
				page_id: pageId,
				section_id: id,
				name: id,
				tpl,
				source: source || starters[tpl] || "",
				index: at < 0 ? blocks.length : at + 1,
			});
			pendingFocus.current = { id, edit: tpl === "program" };
			return id;
		},
		[blocks.length, index, notify, pageId, starters],
	);

	// A split is the two ops it is made of: the head stays where it is, the
	// tail becomes a new block right after it.
	const splitBlock = useCallback(
		(id: string, head: string, tail: string, insert: InsertTpl) => {
			const block = blocks[index(id)];
			// Only a program block's source is editable text. A text block's
			// head is prose, and prose does not travel on this wire.
			if (block && block.tpl !== "text") commitSource(id, head);
			createAfter(id, insert ?? "text", insert === "program" ? "" : tail);
		},
		[blocks, commitSource, createAfter, index],
	);

	const deleteBlocks = useCallback(
		(ids: string[]) => {
			if (ids.length === 0) return;
			const first = index(ids[0]);
			const prev = first > 0 ? blocks[first - 1] : null;
			for (const section_id of ids) {
				notify("section.delete", { page_id: pageId, section_id });
			}
			patch({
				selected: prev ? [prev.id] : [],
				anchor: prev ? prev.id : null,
				focus: null,
				editing: editor.editing.filter((e) => !ids.includes(e)),
			});
		},
		[blocks, editor.editing, index, notify, pageId, patch],
	);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const mergeUp = useCallback(
		(id: string, text: string) => {
			const i = index(id);
			if (i <= 0) return;
			const prev = blocks[i - 1];
			if (prev.tpl === "text") {
				// The join happens in the block above's own prose ref, which is
				// where a text block's content lives; the wire only hears that
				// this block is gone.
				const above = blockText(refPath, prev.id);
				const seam = above.length + (above && text ? 1 : 0);
				notify("section.delete", { page_id: pageId, section_id: id });
				patch({
					focus: { blockId: prev.id, place: "end", offset: seam },
					selected: [],
					anchor: null,
					editing: editor.editing.filter((e) => e !== id),
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
		[blocks, deleteBlocks, editor.editing, index, notify, pageId, patch, refKey],
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
			notify("section.reorder", { page_id: pageId, section_ids: rest });
		},
		[blocks, editor.selected, notify, pageId],
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
				notify("section.reorder", { page_id: pageId, section_ids: rest });
			};
			window.addEventListener("pointermove", move);
			window.addEventListener("pointerup", up);
		},
		[blocks, dropIndexFor, index, notify, pageId, patch],
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
				// The ONE read of `tpl`, and it picks an interior, nothing else.
				const bare = block.tpl === "text";
				const editing = editor.editing.includes(block.id);
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
						{hasGutterRail(state) ? (
							<span className={docStatusRail(state)} />
						) : focused ? (
							<span className={docFocusRail} />
						) : null}
						<Gutter
							program={!bare}
							blockId={block.id}
							editing={editing}
							onSetEditing={(on) => setEditing(block.id, on)}
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
								uiPath={blockUiPath(refPath, block.id)}
								editing={editing}
								onCommit={(src) => commitSource(block.id, src)}
								onExit={(dir, column) => step(block.id, dir, column)}
								onCloseEditor={() => setEditing(block.id, false)}
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
								source={block.source}
								uiPath={blockUiPath(refPath, block.id)}
								status={block.status}
								editing={editing}
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
								onSetEditing={(on) => setEditing(block.id, on)}
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
 * A text block's interior: its diagnostic, its source if you asked for it, and
 * its program's ui refs.
 *
 * The same three parts a program block has, in the same order, because a text
 * block is a section like any other -- it came from a template nobody typed,
 * which changes what the source says but not that it has one. The gutter
 * offers it on the same row either way.
 *
 * The refs come through `NodeView` exactly as a program block's do. The one
 * the template mounts is a `ProseRef`, and nuspace's entry for it (see
 * ./ProseRef.tsx) reads the bus off the context provided here to rebuild the
 * block-boundary behaviour the kit's editor deliberately leaves out.
 *
 * The prose keeps the caret while the source sits open above it, so the
 * editor gets no focus request: two editors in one block cannot both honour
 * one, and the paragraph is the one you were writing in.
 */
function TextBlock({
	block,
	uiPath,
	editing,
	bus,
	onCommit,
	onExit,
	onCloseEditor,
}: {
	block: Block;
	uiPath: Path;
	editing: boolean;
	bus: BlockProse;
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
	onCloseEditor: () => void;
}) {
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
				{editing ? (
					<SourceEditor
						source={block.source}
						focusReq={null}
						onFocusConsumed={() => {}}
						onCommit={onCommit}
						onExit={onExit}
						onEscape={onCloseEditor}
					/>
				) : null}
				<NodeView path={uiPath} />
			</div>
		</BlockProseContext.Provider>
	);
}

/**
 * Every affordance a block has, hung in the gutter outside the reading column.
 *
 * Three stacked rows of kit primitives, so they share a box, a hover tier, a
 * focus ring and one reveal. Top to bottom they read as what you do to the
 * block, what you do with it, and what it is: add and drag, copy its id, open
 * its source next to the dot that says whether it is alive.
 *
 * Every glyph carries a tooltip and a label. A bare glyph in a margin is not
 * self-explanatory, and `title` is not an affordance, it is a delay.
 */
function Gutter({
	program,
	blockId,
	editing,
	onSetEditing,
	onDrag,
	onPlus,
	onSelect,
}: {
	program: boolean;
	blockId: string;
	editing: boolean;
	onSetEditing: (on: boolean) => void;
	onDrag: (e: React.PointerEvent) => void;
	onPlus: (rect: DOMRect) => void;
	onSelect: () => void;
}) {
	const [copied, setCopied] = useState(false);

	// The bare section id, not the `sections.<id>` mount prefix: the id is what
	// every op on the wire is keyed by, so it is the string worth having on the
	// clipboard. See ./blocks.ts for the prefix and where it comes from.
	const copyId = useCallback(() => {
		navigator.clipboard
			?.writeText(blockId)
			.then(() => {
				setCopied(true);
				window.setTimeout(() => setCopied(false), 1200);
			})
			.catch(() => {});
	}, [blockId]);

	return (
		<div className={docGutter(program)}>
			<div className={docGutterAffordances}>
				<div className={docGutterRow}>
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
				<div className={docGutterRow}>
					<Tooltip>
						<TooltipTrigger asChild>
							<IconButton
								variant="ghost"
								size="sm"
								aria-label="Copy this block's section id"
								onClick={copyId}
							>
								{copied ? <Check className="text-status-ok" /> : <Copy />}
							</IconButton>
						</TooltipTrigger>
						<TooltipContent side="top">{copied ? "copied" : "copy section id"}</TooltipContent>
					</Tooltip>
				</div>
				<div className={docGutterRow}>
					<SectionStatusDot status={GUTTER_STATUS} />
					<Tooltip>
						<TooltipTrigger asChild>
							<Toggle
								size="sm"
								pressed={editing}
								onPressedChange={onSetEditing}
								aria-label="Show this block's source"
								className={docGutterToggle}
							>
								<Code />
							</Toggle>
						</TooltipTrigger>
						<TooltipContent side="top">{editing ? "hide source" : "show source"}</TooltipContent>
					</Tooltip>
				</div>
			</div>
		</div>
	);
}
