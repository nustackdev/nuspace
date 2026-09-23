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
// ## Every block is the same
//
// There is no block kind to branch on. Each block renders the subtree at its
// own address -- the ui refs its program mounted, which arrive as ordinary
// nodes -- through `NodeView`, inside the same `docBlock`, with the same
// gutter: add and drag, copy the section id, open the source. Every block
// compiles, runs, is supervised and reports status identically. See
// ./blocks.ts for where that address is.
//
// ## The one thing on the canvas that is not a block: the ghost input
//
// A ghost is a line you can put a caret in that has not decided what it is
// yet. It holds no value, owns no id, and nothing exists in the store because
// of it. Press `/` (or just start typing) and it offers the registered
// snippets; pick one and it becomes a block made from that snippet. Enter on
// an empty ghost makes a blank program.
//
// There is always one at the end of the page, which is what makes an empty
// page writeable without hunting for a control, and the gutter `+` summons a
// second one after any row. The summoned one is transient: it resolves into a
// block or it is gone the moment it loses focus with nothing in it.
//
// ## The two selection regimes
//
// Inside a block's open source editor you get a caret. Across a block
// boundary you get *block* selection:
//
//   - arrowing out of an editor's first or last line moves to the next block
//   - if that block is open in code mode, the caret enters it, carrying its
//     column
//   - otherwise the block gets *selected* and the canvas takes keyboard focus
//
// ## Focus after a structural op
//
// A create round-trips through the server. The id does not: the browser mints
// it and sends it, so focus is aimed at a known id rather than guessed at from
// a position once `set_page` comes back.

import type { Path } from "@nustackdev/ui-core";
import {
	IconButton,
	pathKey,
	Toggle,
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Check, Code, GripVertical, Hash, Plus } from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { mintId } from "../../app/ids";
import {
	docBlock,
	docColumn,
	docDragHandle,
	docDropIndicator,
	docGhost,
	docGutter,
	docGutterAffordances,
	docGutterRow,
	docGutterToggle,
	docStatusRail,
	docTail,
} from "../../design";
import { blockUiPath } from "./blocks";
import type { Notify } from "./ops";
import { ProgramBlock } from "./Program";
import { filterSlash, SlashMenu } from "./Slash";
import type { SlashSnippet } from "./state";
import { type EditorState, type FocusReq, patchEditor, useEditorState } from "./state";
import type { ActivePage, Block, ExitDir, SectionState } from "./types";

const NO_SNIPPETS: SlashSnippet[] = [];

export function Canvas({
	refPath,
	page,
	snippets = NO_SNIPPETS,
	editable,
	notify,
}: {
	refPath: Path;
	page: ActivePage;
	/** The registered snippets, in order: the `/` menu's rows. */
	snippets?: SlashSnippet[];
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
	/** A block that has been asked for but not shipped back yet. `set_page`
	 *  prunes focus pointing at a block it does not carry, so the intent is
	 *  parked here until the block actually arrives. */
	const pendingFocus = useRef<string | null>(null);
	/** The two ghost inputs, for vertical travel to aim at. `plus` is the one
	 *  a gutter `+` summoned, and is null far more often than not. */
	const endGhost = useRef<HTMLInputElement | null>(null);
	const plusGhost = useRef<HTMLInputElement | null>(null);

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
			if (editing.includes(block.id)) {
				patch({
					focus: { blockId: block.id, ...req },
					selected: [],
					anchor: null,
					column: null,
				});
				return;
			}
			// A block with its source closed has no text for a caret to sit in.
			// Select it, and park the column so the next hop still lands under
			// the caret.
			patch({
				focus: null,
				selected: [block.id],
				anchor: block.id,
				column: req.column ?? null,
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
		(fromId: string, dir: ExitDir, column: number | undefined) => {
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
			focusBlock(blocks[j], { place: dir === "up" ? "end" : "start", column }, editor.editing);
		},
		[blocks, editor.editing, editor.ghost, focusBlock, index],
	);

	const enterBlock = useCallback(
		(block: Block, place: "start" | "end" = "end") => {
			patch((e) => ({
				editing: e.editing.includes(block.id) ? e.editing : [...e.editing, block.id],
				focus: { blockId: block.id, place },
				selected: [],
				anchor: null,
			}));
		},
		[patch],
	);

	/** Open or close a block's source editor. The caret follows it open. */
	const setEditing = useCallback(
		(id: string, on: boolean) => {
			patch((e) => ({
				editing: on
					? e.editing.includes(id)
						? e.editing
						: [...e.editing, id]
					: e.editing.filter((x) => x !== id),
				focus: on ? { blockId: id, place: "end" } : e.focus,
			}));
		},
		[patch],
	);

	// Land the caret in a newly created block, once the server confirms it.
	useEffect(() => {
		const want = pendingFocus.current;
		if (!want) return;
		if (!blocks.some((b) => b.id === want)) return;
		pendingFocus.current = null;
		patch((e) => ({
			editing: e.editing.includes(want) ? e.editing : [...e.editing, want],
			focus: { blockId: want, place: "start" },
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
	 * Add a block made from the snippet `name` after `afterId` (or last), and
	 * aim the caret at it. The server stores the snippet's program; a name no
	 * snippet has makes a blank one.
	 */
	const createAfter = useCallback(
		(afterId: string | null, name: string) => {
			const id = mintId("s");
			const at = afterId ? index(afterId) : -1;
			notify("section.create", {
				page_id: pageId,
				section_id: id,
				name,
				index: at < 0 ? blocks.length : at + 1,
			});
			pendingFocus.current = id;
		},
		[blocks.length, index, notify, pageId],
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
				// Land the caret when the neighbour can hold one; otherwise the
				// selection just walks on, carrying the parked column with it.
				focusBlock(
					blocks[j],
					{ place: dir < 0 ? "end" : "start", column: editor.column ?? undefined },
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
	const slashItems = useMemo(
		() => (slash ? filterSlash(slash.query, snippets) : []),
		[slash, snippets],
	);

	const pickSlash = useCallback(
		(item: SlashSnippet) => {
			const s = editor.slash;
			if (!s) return;
			patch({ slash: null, ghost: null });
			createAfter(s.blockId, item.name);
		},
		[createAfter, editor.slash, patch],
	);

	const slashKey = useCallback(
		(key: string): boolean => {
			const s = editor.slash;
			if (!s) return false;
			const items = filterSlash(s.query, snippets);
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
		[editor.slash, snippets, patch, pickSlash],
	);

	// -- the ghost inputs ------------------------------------------------------
	//
	// Both ghosts run the same handlers. What differs is where they sit and
	// whether they are allowed to go away: the end-of-page one is furniture,
	// the summoned one is a passing offer. `after` is the block a ghost would
	// create past -- null only on a page with no blocks -- and it doubles as
	// the ghost's identity, which is how the slash state can name one when
	// neither of them has an id of its own.

	/** Nothing was picked. Close the menu, and take the offer back. */
	const dismissGhost = useCallback(
		(transient: boolean) => patch(transient ? { ghost: null, slash: null } : { slash: null }),
		[patch],
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

	/** Escape with no menu open selects the block the ghost hangs off, since
	 *  the ghost itself cannot be one. */
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
			query={slash && slash.blockId === after ? slash.query : null}
			onWake={() => {
				// Clicking a ghost leaves block-selection mode, exactly as
				// clicking into a block does.
				patch((e) => (e.selected.length ? { selected: [], anchor: null } : {}));
			}}
			onBlank={() => {
				patch({ slash: null, ghost: null });
				createAfter(after, "");
			}}
			onOpenSlash={(anchor, query) =>
				patch({
					slash: { blockId: after, query, anchor, index: 0 },
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
	// editor inside it, including ones we do not own (Monaco, a block's refs).

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
				const editing = editor.editing.includes(block.id);
				const state = block.status.state;
				const selectSelf = () => {
					patch({ selected: [block.id], anchor: block.id, focus: null });
					rootRef.current?.focus({ preventScroll: true });
				};
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
							{editable ? (
								<Gutter
									blockId={block.id}
									state={state}
									pinned={editing || selected}
									editing={editing}
									onSetEditing={(on) => setEditing(block.id, on)}
									onDrag={(e) => startDrag(e, block.id)}
									onPlus={() => {
										// Make room, do not make a block. What goes here is
										// whatever gets picked next.
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
									onSelect={selectSelf}
								/>
							) : null}
							<ProgramBlock
								source={block.source}
								uiPath={blockUiPath(refPath, block.id)}
								status={block.status}
								editing={editing}
								focusReq={focusReq}
								onFocusConsumed={() => patch({ focus: null })}
								onCommit={(src) => commitSource(block.id, src)}
								onExit={(dir, column) => step(block.id, dir, column)}
								onSelectSelf={selectSelf}
								onSetEditing={(on) => setEditing(block.id, on)}
							/>
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
const GHOST_HINT = "/ for blocks";
/** ...and once the menu is open, which is the whole of what changed. */
const GHOST_SEARCH = "type to search";

/**
 * The ghost input.
 *
 * A one-line text input that never holds anything but the slash query. `/`
 * opens the menu with an empty query; any other character opens it with that
 * character as the query. Enter with the menu closed makes a blank program.
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
	onBlank,
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
	/** The caret arrived. */
	onWake: () => void;
	/** Enter on an empty ghost: a blank program. */
	onBlank: () => void;
	onOpenSlash: (anchor: { x: number; y: number }, query: string) => void;
	onQuery: (query: string) => void;
	/** Return true if the menu consumed the key. */
	onKey: (key: string) => boolean;
	/** Put the menu away and leave the ghost standing. */
	onCloseSlash: () => void;
	onEscape: () => void;
	onLeave: (dir: ExitDir) => void;
	onDismiss: () => void;
}) {
	const open = query !== null;

	// biome-ignore lint/correctness/useExhaustiveDependencies: hostRef is a ref object and never changes identity
	useEffect(() => {
		if (autoFocus) hostRef.current?.focus();
	}, [autoFocus]);

	const anchorOf = (el: HTMLElement) => {
		const r = el.getBoundingClientRect();
		return { x: r.left, y: r.bottom };
	};

	return (
		<input
			ref={hostRef}
			type="text"
			aria-label="New block"
			className={docGhost}
			placeholder={open ? GHOST_SEARCH : GHOST_HINT}
			value={query ?? ""}
			onFocus={onWake}
			onChange={(e) => {
				const next = e.currentTarget.value;
				if (open) {
					onQuery(next);
					return;
				}
				if (next) onOpenSlash(anchorOf(e.currentTarget), next);
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
					// Backspacing off the end of the query puts the menu away.
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
				if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
					// Consumed: the `/` is the gesture, not the query.
					e.preventDefault();
					onOpenSlash(anchorOf(e.currentTarget), "");
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					onBlank();
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
				// Nothing was picked, or the pick would have unmounted this. A
				// menu pick keeps the caret here (mousedown is prevented), so a
				// blur is always a departure and never a selection.
				onDismiss();
			}}
		/>
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
	blockId,
	editing,
	onSetEditing,
	onDrag,
	onPlus,
	onSelect,
	state,
	pinned,
}: {
	blockId: string;
	/** The block's state, painted as the rail on the lane's edge. */
	state: SectionState;
	/** Keep controls + rail visible off hover: source open, or block-selected. */
	pinned: boolean;
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
		<div className={docGutter}>
			<span className={docStatusRail(state, pinned)} title={state} />
			{/* Slower than the kit's 200ms, and with no instant reopen. The gutter
			    is a stack you walk THROUGH to reach one control, so at the kit's
			    delay a tooltip fires on every glyph you cross and lands portalled
			    over the blocks below. 700ms is long enough that passing through
			    says nothing and resting says "tell me what this is"; the 0 skip
			    window is what stops the second and third from arriving instantly
			    once the first has spoken. Scoped here so the shell strip and the
			    rails keep the kit's snappier feel. */}
			<TooltipProvider delayDuration={700} skipDelayDuration={0}>
				<div className={docGutterAffordances(pinned)}>
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
									{copied ? <Check className="text-status-ok" /> : <Hash />}
								</IconButton>
							</TooltipTrigger>
							<TooltipContent side="top">{copied ? "copied" : "copy section id"}</TooltipContent>
						</Tooltip>
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
