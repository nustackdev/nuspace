// The block canvas. This is what the Viewer draws.
//
// `editable` is the Plane's own bit and the only thing here that branches on
// it: with it you get the gutter, the insert affordances, the drag handle and
// the code toggle, and without it the same blocks render with none of them.
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
// ## The one thing on the canvas that is not a block: the ghost input
//
// A ghost is a line you can put a caret in that has not decided what it is
// yet. It holds no value, owns no id, and nothing exists in the store because
// of it -- it is a promise that the next thing you do will make a block, and
// a place to stand while you do it. Type a character and it becomes a text
// block carrying that character; press `/` and it offers the whole menu,
// which is the one place the whole menu makes sense.
//
// There is always one at the end of the page, which is what makes an empty
// page writeable without hunting for a control, and the gutter `+` summons a
// second one after any row. The summoned one is transient: it resolves into a
// block or it is gone the moment it loses focus with nothing in it. That is
// the difference between "insert a block below" -- which used to create one
// before you had said what it should be -- and "make room below".
//
// Seeding the block it becomes goes the long way round, and has to. A create
// carries structure, not prose (see "Split and merge" below), so the typed
// character is parked and handed to the new block's own prose ref the moment
// that ref registers. See `pendingSeed`.
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
// something is running the sections.

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
	TooltipProvider,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Check, Code, Copy, GripVertical, Plus } from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { mintId } from "../../app/ids";
import { SectionStatusDot } from "../../components";
import {
	docBlock,
	docColumn,
	docDragHandle,
	docDropIndicator,
	docFocusRail,
	docGhost,
	docGutter,
	docGutterAffordances,
	docGutterRow,
	docGutterStatus,
	docGutterToggle,
	docStatusRail,
	docStatusTrace,
	docTail,
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
	type BlockSeed,
	type ExitDir,
	type InsertTpl,
	type ProseHandle,
} from "./ProseRef";
import { filterSlash, type SlashItem, SlashMenu } from "./Slash";
import { type EditorState, type FocusReq, patchEditor, useEditorState } from "./state";
import type { ActivePage, Block, BlockTpl, SectionState } from "./types";

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
	editable,
	notify,
}: {
	refPath: Path;
	page: ActivePage;
	/** What a block of each tpl starts life as, off the ref's props.
	 *  `nuspace/ops/templates.py` is the one spelling of these. */
	starters: Record<string, string>;
	/** The Plane's own bit. False draws the same Cells with none of the
	 *  controls a document has: no gutter, no insert, no drag, no code
	 *  toggle. */
	editable: boolean;
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
	const pendingFocus = useRef<{ id: string; edit: boolean; place: "start" | "end" } | null>(null);
	/** What a block that does not exist yet is to start life holding.
	 *  Parked here rather than sent, because prose does not travel on the
	 *  create wire; `registerHandle` below hands it over the instant the new
	 *  block's own prose ref turns up. */
	const pendingSeed = useRef<{ id: string; seed: BlockSeed } | null>(null);
	/** The two ghost inputs, for vertical travel to aim at. `plus` is the one
	 *  a gutter `+` summoned, and is null far more often than not. */
	const endGhost = useRef<HTMLInputElement | null>(null);
	const plusGhost = useRef<HTMLInputElement | null>(null);
	/** The block the focused ghost has already turned into, if any. Cleared
	 *  every time a ghost takes the caret, so a ghost is spent exactly once
	 *  and a seed that never got delivered cannot wedge the next one. */
	const becoming = useRef<string | null>(null);

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

	/**
	 * Leave a block vertically and land wherever is next.
	 *
	 * A ghost is not in `blocks` -- it is not a block -- but it IS in the
	 * document, between two rows or at the foot of the page, so travel has to
	 * know about it or the last line on every page would be unreachable from
	 * the keyboard. It carries no column: there is no text in it to land under.
	 */
	const step = useCallback(
		(fromId: string, dir: ExitDir, column: number | undefined, x?: number) => {
			const i = index(fromId);
			if (i < 0) return;
			if (dir === "down") {
				if (editor.ghost === fromId) {
					plusGhost.current?.focus();
					return;
				}
				if (i === blocks.length - 1) {
					endGhost.current?.focus();
					return;
				}
			} else if (i > 0 && editor.ghost === blocks[i - 1].id) {
				plusGhost.current?.focus();
				return;
			}
			const j = dir === "up" ? i - 1 : i + 1;
			if (j < 0 || j >= blocks.length) return;
			focusBlock(blocks[j], { place: dir === "up" ? "end" : "start", column, x }, editor.editing);
		},
		[blocks, editor.editing, editor.ghost, focusBlock, index],
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
			focus: { blockId: want.id, place: want.place },
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
	 *
	 * `seed` is the other thing a new block can start life holding, and it is
	 * a separate argument because it is a separate substance: `source` is the
	 * program and rides the create, `seed` is prose and cannot -- it waits for
	 * the block's prose ref to exist and is handed over there.
	 */
	const createAfter = useCallback(
		(afterId: string | null, tpl: BlockTpl, source = "", seed?: BlockSeed) => {
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
			// A seeded block is one somebody has already started writing, so the
			// caret belongs after what they wrote. Everything else opens empty
			// (or at the top of a starter program) and "start" is the same place
			// or the right one. Load bearing only if the focus intent happens to
			// land after the prose ref has already taken the seed.
			pendingFocus.current = { id, edit: tpl === "program", place: seed ? "end" : "start" };
			pendingSeed.current = seed ? { id, seed } : null;
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
	const slashItems = useMemo(() => (slash ? filterSlash(slash.query, slash.mode) : []), [slash]);

	const pickSlash = useCallback(
		(item: SlashItem) => {
			const s = editor.slash;
			if (!s) return;
			if (s.mode === "ghost") {
				patch({ slash: null, ghost: null });
				// A ghost has no line to shape and nothing to split, so the two
				// actions read differently here: a "split" item names the tpl to
				// make, and a prose item makes a text block already wearing the
				// shape it would otherwise have imposed. The prefix never lands as
				// characters -- the seed applies the same command the inline path
				// does, so the caret ends up after it either way.
				if (item.action.act === "split") {
					createAfter(s.blockId, item.action.insert === "program" ? "program" : "text");
					return;
				}
				createAfter(s.blockId, "text", "", { action: item.action });
				return;
			}
			if (s.blockId) proseHandles.current.get(s.blockId)?.applySlash(item.action);
		},
		[createAfter, editor.slash, patch],
	);

	const slashKey = useCallback(
		(key: string): boolean => {
			const s = editor.slash;
			if (!s) return false;
			const items = filterSlash(s.query, s.mode);
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

	// -- the ghost inputs ------------------------------------------------------
	//
	// Both ghosts run the same handlers. What differs is where they sit and
	// whether they are allowed to go away: the end-of-page one is furniture,
	// the summoned one is a passing offer. `after` is the block a ghost would
	// create past -- null only on a page with no blocks -- and it doubles as
	// the ghost's identity, which is how the slash state can name one when
	// neither of them has an id of its own.

	/** Nothing was entered. Close the menu, and take the offer back. */
	const dismissGhost = useCallback(
		(transient: boolean) => patch(transient ? { ghost: null, slash: null } : { slash: null }),
		[patch],
	);

	/**
	 * Something was entered. This is the moment a ghost becomes a block.
	 *
	 * And it happens at most once per ghost, which is the whole reason this
	 * bothers to remember anything. A create round-trips, and somebody typing
	 * at speed gets several keystrokes in before it lands; one block per
	 * keystroke is what "create on first character" means if you do not say
	 * otherwise. So the first character makes the block and every character
	 * after it rewrites the seed that block has not received yet. Nothing is
	 * dropped and nothing is made twice.
	 */
	const seedGhost = useCallback(
		(after: string | null, text: string) => {
			const id = becoming.current;
			if (id) {
				if (pendingSeed.current?.id === id) pendingSeed.current = { id, seed: { text } };
				return;
			}
			patch({ slash: null, ghost: null });
			becoming.current = createAfter(after, "text", "", { text });
		},
		[createAfter, patch],
	);

	/** Arrow out of a ghost into whichever block is that way, if any. */
	const leaveGhost = useCallback(
		(after: string | null, dir: ExitDir, transient: boolean) => {
			if (transient) patch({ ghost: null });
			const i = after ? index(after) : -1;
			const target = dir === "up" ? blocks[i] : blocks[i + 1];
			if (!target) return;
			focusBlock(target, { place: dir === "up" ? "end" : "start" }, editor.editing);
		},
		[blocks, editor.editing, focusBlock, index, patch],
	);

	/** Escape with no menu open, which in prose selects the block. Same here:
	 *  the block the ghost hangs off, since the ghost itself cannot be one. */
	const escapeGhost = useCallback(
		(after: string | null, transient: boolean) => {
			const block = after ? blocks[index(after)] : null;
			patch((e) => ({
				slash: null,
				ghost: transient ? null : e.ghost,
				selected: block ? [block.id] : [],
				anchor: block ? block.id : null,
				focus: null,
			}));
			rootRef.current?.focus({ preventScroll: true });
		},
		[blocks, index, patch],
	);

	// -- render ---------------------------------------------------------------

	const setEl = useCallback((id: string, el: HTMLElement | null) => {
		if (el) elRefs.current.set(id, el);
		else elRefs.current.delete(id);
	}, []);

	/**
	 * A block's prose ref arriving or leaving.
	 *
	 * Stable by construction. The bus below is rebuilt every render, so the
	 * one thing a block's editor keeps across renders must not be.
	 *
	 * This is also where a parked seed is delivered, and it has to be: a
	 * create round-trips through the server, the page comes back, the section
	 * is compiled and run, and only then does its `ProseRef` exist. There is
	 * no earlier moment at which "put this text in that block" is a thing the
	 * browser can do, and registration is exactly that moment.
	 */
	const registerHandle = useCallback((id: string, handle: ProseHandle | null) => {
		if (!handle) {
			proseHandles.current.delete(id);
			return;
		}
		proseHandles.current.set(id, handle);
		const want = pendingSeed.current;
		if (want?.id !== id) return;
		pendingSeed.current = null;
		handle.seed(want.seed);
	}, []);

	const drag = editor.drag;
	const lastId = blocks.length ? blocks[blocks.length - 1].id : null;

	/**
	 * One ghost, wired up. `after` is both where it sits and who it is.
	 *
	 * A closure rather than a memo: it takes arguments that only the render
	 * knows, and what it returns is an element, not a value anybody caches.
	 */
	const ghost = (after: string | null, transient: boolean) => (
		<Ghost
			hostRef={transient ? plusGhost : endGhost}
			autoFocus={transient}
			query={slash && slash.mode === "ghost" && slash.blockId === after ? slash.query : null}
			onWake={() => {
				becoming.current = null;
				// Clicking a ghost leaves block-selection mode, exactly as
				// clicking into a block does.
				patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
			}}
			onSeed={(text) => seedGhost(after, text)}
			onOpenSlash={(anchor) =>
				patch({
					slash: { blockId: after, mode: "ghost", query: "", from: 0, to: 0, anchor, index: 0 },
					selected: [],
					anchor: null,
				})
			}
			onQuery={(query) => patch((e) => (e.slash ? { slash: { ...e.slash, query, index: 0 } } : {}))}
			onKey={slashKey}
			onCloseSlash={() => patch({ slash: null })}
			onEscape={() => escapeGhost(after, transient)}
			onLeave={(dir) => leaveGhost(after, dir, transient)}
			onDismiss={() => dismissGhost(transient)}
		/>
	);

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
					<Fragment key={block.id}>
						{/* biome-ignore lint/a11y/noStaticElementInteractions: a mousedown anywhere in a block hands control to that block's own editor */}
						<div
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
							{editable ? (
								<Gutter
									program={!bare}
									blockId={block.id}
									editing={editing}
									onSetEditing={(on) => setEditing(block.id, on)}
									onDrag={(e) => startDrag(e, block.id)}
									onPlus={() => {
										// Make room, do not make a block. What goes here is
										// whatever gets typed next, and until something is
										// typed there is nothing to have an opinion about.
										//
										// On the last block there is already a ghost directly
										// below -- the permanent one -- so summoning a second
										// would put two identical empty lines next to each
										// other and make vertical travel pick between them.
										if (block.id === lastId) {
											patch({ ghost: null, slash: null });
											endGhost.current?.focus();
											return;
										}
										patch({
											ghost: block.id,
											slash: null,
											selected: [],
											anchor: null,
											focus: null,
										});
									}}
									onSelect={() => {
										patch({
											selected: [block.id],
											anchor: block.id,
											focus: null,
										});
										rootRef.current?.focus({ preventScroll: true });
									}}
								/>
							) : null}
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
						{editable && editor.ghost === block.id ? ghost(block.id, true) : null}
					</Fragment>
				);
			})}
			{drag && drag.at >= blocks.length ? (
				<div className="relative h-0">
					<span className={docDropIndicator} />
				</div>
			) : null}

			{/* The permanent ghost is how an empty Plane is written on without
			    hunting for a control, so it goes with the rest of the authoring
			    affordances. The run-off under it is only there to aim at it. */}
			{editable ? (
				<>
					{ghost(lastId, false)}
					{/* biome-ignore lint/a11y/noStaticElementInteractions: the run-off under a document is a click target, not a control -- the keyboard reaches the same ghost by arrowing down */}
					<div
						className={docTail}
						onMouseDown={(e) => {
							// mousedown and not click, and preventDefault: the caret has to
							// land in the ghost, not in the empty div that was clicked.
							if (e.button !== 0) return;
							e.preventDefault();
							endGhost.current?.focus();
						}}
					/>
				</>
			) : null}

			{slash ? (
				<SlashMenu
					items={slashItems}
					index={slash.index}
					anchor={slash.anchor}
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
				/>
			) : null}
		</div>
	);
}

/** What a ghost offers before anything has happened in it. */
const GHOST_HINT = "write, or / for blocks";
/** ...and once `/` has been pressed, which is the whole of what changed. */
const GHOST_SEARCH = "type to search";

/**
 * The ghost input.
 *
 * A one-line text input that is never allowed to hold anything. Everything
 * typed into it leaves immediately -- into a new block, or into the slash
 * query -- so its value is either the query or the empty string, and it is
 * controlled to make sure of it. That is what "creates nothing until you
 * commit" is, mechanically: there is no draft anywhere, because the input is
 * not where the text was going to live.
 *
 * Typed characters are the interesting case. They land in the DOM input, are
 * read back and wiped from it in the same handler, and are reported onward as
 * the text the new block should start life with. The input is left holding
 * nothing, every time, so each `onChange` carries exactly the characters that
 * were not reported before: written once, never twice, and never left behind
 * in a field that is about to stop existing. `typed` keeps the running total,
 * because the block they are going to does not arrive for a round trip and
 * somebody quick gets three more keystrokes in before it does.
 *
 * Wiping the DOM value by hand rather than letting the controlled value do it
 * is not a shortcut around React: the rendered value IS "", so the two never
 * disagree. It is there because a keystroke that changes no React state
 * re-renders nothing, and an input nobody re-rendered keeps what it was given.
 *
 * An `<input>` and not a contenteditable on purpose: it is one line, it holds
 * no marks, it is in the tab order for free, and screen readers already know
 * what it is.
 */
function Ghost({
	hostRef,
	autoFocus,
	query,
	onWake,
	onSeed,
	onOpenSlash,
	onQuery,
	onKey,
	onCloseSlash,
	onEscape,
	onLeave,
	onDismiss,
}: {
	hostRef: React.RefObject<HTMLInputElement | null>;
	/** A summoned ghost takes the caret; the end-of-page one waits for it. */
	autoFocus: boolean;
	/** The slash query while the menu is open on THIS ghost. Null when not. */
	query: string | null;
	/** The caret arrived. Whatever this ghost was last time does not count. */
	onWake: () => void;
	/** Everything typed so far, which is what the new block is to hold. */
	onSeed: (text: string) => void;
	onOpenSlash: (anchor: { x: number; y: number }) => void;
	onQuery: (query: string) => void;
	/** Return true if the menu consumed the key. Same contract as prose. */
	onKey: (key: string) => boolean;
	/** Put the menu away and leave the ghost standing. */
	onCloseSlash: () => void;
	onEscape: () => void;
	onLeave: (dir: ExitDir) => void;
	onDismiss: () => void;
}) {
	const open = query !== null;
	/** Everything typed since the caret arrived. Spent when it is non-empty. */
	const typed = useRef("");

	// biome-ignore lint/correctness/useExhaustiveDependencies: hostRef is a ref object and never changes identity
	useEffect(() => {
		if (autoFocus) hostRef.current?.focus();
	}, [autoFocus]);

	return (
		<input
			ref={hostRef}
			type="text"
			aria-label="New block"
			className={docGhost}
			placeholder={open ? GHOST_SEARCH : GHOST_HINT}
			value={query ?? ""}
			onFocus={() => {
				typed.current = "";
				onWake();
			}}
			onChange={(e) => {
				const el = e.currentTarget;
				const next = el.value;
				if (open) {
					onQuery(next);
					return;
				}
				if (!next) return;
				el.value = "";
				typed.current += next;
				onSeed(typed.current);
			}}
			onKeyDown={(e) => {
				// The ghost owns its keyboard outright, for the reason a focused
				// block does: the canvas must not also act on a key answered here.
				e.stopPropagation();
				if (open && onKey(e.key)) {
					e.preventDefault();
					return;
				}
				if (open) {
					// Backspacing off the end of the query is how the menu goes
					// away in prose -- the `/` gets deleted. There is no `/` here
					// to delete, so the empty query stands in for it.
					if (e.key === "Backspace" && query === "") {
						e.preventDefault();
						onCloseSlash();
					}
					return;
				}
				if (e.key === "Escape") {
					e.preventDefault();
					onEscape();
					return;
				}
				// Spent. A block is on its way to take the caret, and until it
				// does this line is a waiting room, not somewhere to navigate
				// from -- arrowing out of it now would race the arriving caret.
				if (typed.current) return;
				if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
					// Consumed: the `/` is the gesture, not content. Nothing is in
					// the input, so there is nothing for the query to be measured
					// from and nothing to take back out when an item is picked.
					e.preventDefault();
					const r = e.currentTarget.getBoundingClientRect();
					onOpenSlash({ x: r.left, y: r.bottom });
					return;
				}
				if (e.key === "Enter") {
					// An empty line is a legitimate thing to want.
					e.preventDefault();
					onSeed("");
					return;
				}
				if (e.key === "ArrowUp" || e.key === "ArrowLeft" || e.key === "Backspace") {
					e.preventDefault();
					onLeave("up");
					return;
				}
				if (e.key === "ArrowDown" || e.key === "ArrowRight") {
					e.preventDefault();
					onLeave("down");
				}
			}}
			onBlur={() => {
				// Nothing was entered, or the pick would have unmounted this. A
				// menu pick keeps the caret here (mousedown is prevented), so a
				// blur is always a departure and never a selection.
				onDismiss();
			}}
		/>
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
	/** Open a line below this block. Not a block: see the canvas header. */
	onPlus: () => void;
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
			{/* Slower than the kit's 200ms, and with no instant reopen. The gutter
			    is a stack you walk THROUGH to reach one control, so at the kit's
			    delay a tooltip fires on every glyph you cross and lands portalled
			    over the blocks below. 700ms is long enough that passing through
			    says nothing and resting says "tell me what this is"; the 0 skip
			    window is what stops the second and third from arriving instantly
			    once the first has spoken. Scoped here so the shell strip and the
			    rails keep the kit's snappier feel. */}
			<TooltipProvider delayDuration={700} skipDelayDuration={0}>
				<div className={docGutterAffordances}>
					<div className={docGutterRow}>
						<Tooltip>
							<TooltipTrigger asChild>
								<IconButton
									variant="ghost"
									size="sm"
									aria-label="Add a line below"
									onClick={onPlus}
								>
									<Plus />
								</IconButton>
							</TooltipTrigger>
							<TooltipContent side="top">add a line below</TooltipContent>
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
						<span className={docGutterStatus}>
							<SectionStatusDot status={GUTTER_STATUS} />
						</span>
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
			</TooltipProvider>
		</div>
	);
}
