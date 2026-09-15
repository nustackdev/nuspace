// nuspace's own `ProseRef` entry: the kit's editor, plus the block boundary.
//
// A text block is a Nu program holding a `nustd.ui.ProseRef`, so the thing that
// renders a paragraph in this editor is the same machinery that renders a
// slider in a program block: a node in the tree, drawn by `NodeView`. That is
// what makes "every block is a program" true rather than decorative.
//
// ## Why nuspace registers its own entry over the kit's
//
// The kit's `ProseEditor` deliberately knows nothing about neighbours. No
// split, no merge-up, no arrow-exit, no slash menu -- those only mean
// something to a host that owns a *sequence* of blocks, and the kit editor
// owns exactly one value. That line is correct and we are not moving it.
//
// But nuspace IS that host, and those four are most of what makes the
// document feel like a document. So this wraps the kit editor and rebuilds
// them on top, using the three seams it was built to leave open:
//
//   - it binds no bare arrows, no bare Escape, no Mod-Enter
//   - it does not stop keydown propagation
//   - `onView` hands out the live EditorView, so a host can run ProseMirror
//     commands against the real document
//
// ## Where the behaviour comes from
//
// Not from props. A node component is handed one thing, its `path`, so the
// canvas publishes the block's boundary handlers on `BlockProseContext` and
// this reads them. A `ProseRef` a person puts in a program block of
// their own finds no context, gets no boundary behaviour, and behaves like
// the kit's plain editor -- which is the right answer, because that ref is
// not a block.
//
// ## Keyboard ordering, which is the fiddly part
//
// The old island bound its boundary keys as a ProseMirror plugin placed
// *before* baseKeymap, and its slash handling as a direct view prop, which
// runs before every plugin. Both orderings are load bearing: Enter while the
// menu is open must pick an item, not split a paragraph; Backspace at the
// start of a list item must outdent (PM's job) before it merges up (ours).
//
// Neither is expressible from outside the view, so ordering is done with the
// DOM instead. `onKeyDownCapture` on a wrapper runs in the capture phase, on
// an ancestor, which is strictly before the listener ProseMirror registers
// on the editable -- so anything consumed here never reaches PM, exactly as
// if it were the first plugin. Anything NOT consumed falls through to PM
// normally, and the bubble handler then stops it so the canvas (which owns
// block selection) does not act on a key the caret already answered.

import { OPS, type Path } from "@nustackdev/ui-core";
import {
	type NodeEntry,
	type NodeProps,
	nodeAt,
	ProseEditor,
	useBoolProp,
	useSend,
	useSetValue,
	useStringProp,
} from "@nustackdev/ui-kit";
import { setBlockType, wrapIn } from "prosemirror-commands";
import type { Node as PMNode } from "prosemirror-model";
import { liftListItem, wrapInList } from "prosemirror-schema-list";
import { type Command, TextSelection } from "prosemirror-state";
import type { EditorView } from "prosemirror-view";
import { createContext, useCallback, useContext, useEffect, useRef } from "react";
import { docProseEditor } from "../../design";
import {
	nodeType,
	type Parsed,
	parseMarkdown,
	posForOffset,
	proseDialect,
	serializeMarkdown,
	serializeRange,
} from "./prose";
import type { SlashAction } from "./Slash";
import type { FocusReq } from "./state";

export type ExitDir = "up" | "down";
/** What a split inserts between the two halves, if anything. A tpl name. */
export type InsertTpl = "text" | "program" | null;

export type ProseHandle = {
	/** Apply a slash-menu action against the live document and caret. */
	applySlash: (action: SlashAction) => void;
};

/**
 * Everything the canvas knows and one block's editor does not: who its
 * neighbours are, where the caret was asked to go, whether the slash menu is
 * open on it.
 *
 * Provided per block. Absent means "this ProseRef is not a block", and the
 * editor falls back to the kit's plain behaviour.
 */
export type BlockProse = {
	blockId: string;
	/** Non-null when this block is the caret's target. */
	focusReq: FocusReq | null;
	/** Position of the `/` while the menu is open on this block. */
	slashFrom: number | null;
	onFocusConsumed: () => void;
	/** Caret left vertically. `x` is where it was on screen, which is what
	 *  lands it under itself in the neighbour. */
	onExit: (dir: ExitDir, column: number | undefined, x?: number) => void;
	/** Backspace at the very start. The canvas decides merge vs select. */
	onMergeUp: (content: string) => void;
	onSplit: (head: string, tail: string, insert: InsertTpl) => void;
	onSlashOpen: (offset: number, anchor: { x: number; y: number }) => void;
	onSlashQuery: (query: string) => void;
	onSlashClose: () => void;
	/** Return true if the menu consumed the key. */
	onSlashKey: (key: string) => boolean;
	onSelectSelf: () => void;
	registerHandle: (blockId: string, handle: ProseHandle | null) => void;
};

export const BlockProseContext = createContext<BlockProse | null>(null);

/* ============================== geometry ================================= */

type Textblock = { start: number; end: number };

function firstTextblock(doc: PMNode): Textblock | null {
	let found: Textblock | null = null;
	doc.descendants((node, pos) => {
		if (found) return false;
		if (node.isTextblock) {
			found = { start: pos + 1, end: pos + 1 + node.content.size };
			return false;
		}
		return true;
	});
	return found;
}

function lastTextblock(doc: PMNode): Textblock | null {
	let found: Textblock | null = null;
	doc.descendants((node, pos) => {
		if (node.isTextblock) {
			found = { start: pos + 1, end: pos + 1 + node.content.size };
			return false;
		}
		return true;
	});
	return found;
}

/** The caret is on the first visual line of the block's first textblock. */
function atTop(view: EditorView): boolean {
	const sel = view.state.selection;
	if (!(sel instanceof TextSelection) || !sel.empty) return false;
	const first = firstTextblock(view.state.doc);
	if (!first || sel.$from.start() !== first.start) return false;
	return view.endOfTextblock("up");
}

function atBottom(view: EditorView): boolean {
	const sel = view.state.selection;
	if (!(sel instanceof TextSelection) || !sel.empty) return false;
	const last = lastTextblock(view.state.doc);
	if (!last || sel.$from.start() !== last.start) return false;
	return view.endOfTextblock("down");
}

/** Where the caret is on screen, for the neighbour to land under. */
function caretX(view: EditorView): number | undefined {
	try {
		return view.coordsAtPos(view.state.selection.from).left;
	} catch {
		return undefined;
	}
}

/** Honour a focus request. Never throws; a bad position just clamps. */
function placeCaret(view: EditorView, req: FocusReq, parsed: Parsed): void {
	const doc = view.state.doc;
	const first = firstTextblock(doc);
	const last = lastTextblock(doc);
	const target = req.place === "start" ? first : last;
	let pos = target ? (req.place === "start" ? target.start : target.end) : 1;

	if (req.offset !== undefined && parsed.doc.eq(doc)) {
		// Exact: after a merge the caret belongs at the seam, and the seam is
		// a markdown offset, which only the parse knows how to translate.
		pos = posForOffset(parsed, req.offset);
	} else if (target) {
		view.focus();
		if (req.x !== undefined) {
			// The accurate path: aim at the pixel column the caret left from,
			// on the line we are entering, then clamp into that textblock so a
			// near-miss cannot land in a neighbouring paragraph.
			try {
				const edge = view.coordsAtPos(pos);
				const hit = view.posAtCoords({ left: req.x, top: (edge.top + edge.bottom) / 2 });
				if (hit) pos = Math.max(target.start, Math.min(hit.pos, target.end));
			} catch {
				/* keep the edge position */
			}
		} else if (req.column !== undefined && req.place === "start") {
			pos = Math.min(target.start + req.column, target.end);
		}
	}

	const clamped = Math.max(0, Math.min(pos, doc.content.size));
	const tr = view.state.tr.setSelection(TextSelection.near(doc.resolve(clamped)));
	view.dispatch(tr.scrollIntoView());
	view.focus();
}

/* ============================== slash actions ============================ */

const PREFIX_COMMANDS: Record<string, Command> = {
	"# ": setBlockType(nodeType.heading, { level: 1 }),
	"## ": setBlockType(nodeType.heading, { level: 2 }),
	"### ": setBlockType(nodeType.heading, { level: 3 }),
	"> ": wrapIn(nodeType.blockquote),
	"": setBlockType(nodeType.paragraph),
};

/** A list item toggles: asking for the list you are already in leaves it. */
function listCommand(ordered: boolean): Command {
	const type = ordered ? nodeType.orderedList : nodeType.bulletList;
	return (state, dispatch, view) => {
		const { $from } = state.selection;
		for (let d = $from.depth; d > 0; d--) {
			if ($from.node(d).type === type) {
				return liftListItem(nodeType.listItem)(state, dispatch, view);
			}
		}
		return wrapInList(type)(state, dispatch, view);
	};
}

/* ============================== the entry =============================== */

// Same contract as the kit's own ProseRef: a markdown string in `value`, plus
// the two presentation props the server can merge in. The handler is the kit's
// too, and for the kit's reason -- a null write has to land as "" so the
// editor never sees null and a following read answers "".

/** This ref's markdown, read outside a render. What a neighbour needs. */
export function proseValue(path: Path): string {
	return String(nodeAt(path)?.props.value ?? "");
}

/* ============================== component =============================== */

function ProseView({ path }: NodeProps) {
	const value = useStringProp(path, "value");
	const hint = useStringProp(path, "placeholder");
	const readOnly = useBoolProp(path, "read_only");
	const setValue = useSetValue(path);
	const send = useSend(path);
	const block = useContext(BlockProseContext);

	const viewRef = useRef<EditorView | null>(null);
	/** The last parse of the server's value, for merge-seam offsets. */
	const parsedRef = useRef<Parsed>(parseMarkdown(value));
	/** A pending merge seam, re-applied when the joined value arrives. */
	const seamRef = useRef<number | null>(null);
	/** Context identity churns every canvas render; the handlers do not. */
	const cb = useRef({ block, value });
	cb.current = { block, value };

	const commit = useCallback(
		(source: string) => {
			// Local first, so the read the notify provokes answers with the
			// text that provoked it.
			setValue(source);
			send(OPS.notify);
		},
		[setValue, send],
	);

	const onView = useCallback((v: EditorView | null) => {
		viewRef.current = v;
	}, []);

	/**
	 * Stop the kit editor's pending autosave from undoing a structural op.
	 *
	 * The editor commits on a quiet moment, and it drops a commit whose text
	 * equals the value it was given. So writing the post-op text into the
	 * node *is* how a host cancels the save it no longer wants -- without
	 * reaching for a dirty flag that is, rightly, the editor's own.
	 */
	const settle = useCallback(
		(text: string) => {
			setValue(text);
		},
		[setValue],
	);

	// -- server-owned value ---------------------------------------------------
	//
	// The kit editor adopts an inbound value itself (when it is not dirty), so
	// nothing here touches the document. What is left is the seam: after a
	// merge the caret was placed against the *old* document, and this is the
	// document it was really meant for. Child effects run before parent ones,
	// so by the time this fires the editor has already adopted.
	useEffect(() => {
		const parsed = parseMarkdown(value);
		parsedRef.current = parsed;
		const view = viewRef.current;
		const seam = seamRef.current;
		if (!view || seam === null || !view.hasFocus()) return;
		seamRef.current = null;
		placeCaret(view, { blockId: "", place: "end", offset: seam }, parsed);
	}, [value]);

	// -- focus routing --------------------------------------------------------

	const focusReq = block?.focusReq ?? null;
	useEffect(() => {
		const view = viewRef.current;
		if (!focusReq || !view) return;
		seamRef.current = focusReq.offset ?? null;
		placeCaret(view, focusReq, parsedRef.current);
		cb.current.block?.onFocusConsumed();
	}, [focusReq]);

	// -- the slash menu's imperative half -------------------------------------

	const applySlash = useCallback(
		(action: SlashAction) => {
			const view = viewRef.current;
			const ctx = cb.current.block;
			const from = ctx?.slashFrom ?? null;
			if (!view || !ctx || from === null) return;
			const state = view.state;
			const to = Math.min(Math.max(state.selection.from, from + 1), state.doc.content.size);

			if (action.act === "split") {
				// Everything before the `/` stays; everything after the query
				// becomes the tail.
				const head = serializeRange(state.doc, 0, from);
				const tail = serializeRange(state.doc, to, state.doc.content.size);
				view.dispatch(state.tr.delete(from, state.doc.content.size));
				settle(head);
				ctx.onSlashClose();
				ctx.onSplit(head, tail, action.insert);
				return;
			}

			// Drop the `/query`, then transform the block it was typed in.
			view.dispatch(state.tr.delete(from, to));
			ctx.onSlashClose();

			if (action.act === "literal") {
				view.dispatch(view.state.tr.replaceSelectionWith(nodeType.rule.create()));
			} else if (action.prefix === "- " || action.prefix === "1. ") {
				listCommand(action.prefix === "1. ")(view.state, view.dispatch, view);
			} else {
				PREFIX_COMMANDS[action.prefix]?.(view.state, view.dispatch, view);
			}
			view.focus();
		},
		[settle],
	);

	// Registered once. The handle closes over refs, so it never goes stale.
	const blockId = block?.blockId ?? "";
	useEffect(() => {
		const ctx = cb.current.block;
		if (!ctx) return;
		ctx.registerHandle(blockId, { applySlash });
		return () => ctx.registerHandle(blockId, null);
	}, [blockId, applySlash]);

	// -- the slash query ------------------------------------------------------
	//
	// The old island re-read this inside `dispatchTransaction`, which it owned.
	// The kit owns it now, so this runs on keyup and mouseup instead: both are
	// after ProseMirror has applied, and between them they cover every way the
	// query or the caret can move while the menu is open.
	const syncSlash = useCallback(() => {
		const view = viewRef.current;
		const ctx = cb.current.block;
		if (!view || !ctx || ctx.slashFrom === null) return;
		const from = ctx.slashFrom;
		const doc = view.state.doc;
		const caret = view.state.selection.from;
		if (from + 1 > doc.content.size || doc.textBetween(from, from + 1) !== "/" || caret <= from) {
			ctx.onSlashClose();
			return;
		}
		const query = doc.textBetween(from + 1, caret);
		if (/\s/.test(query)) {
			ctx.onSlashClose();
			return;
		}
		ctx.onSlashQuery(query);
	}, []);

	// -- the boundary keyboard ------------------------------------------------

	const onKeyDownCapture = useCallback(
		(e: React.KeyboardEvent) => {
			const view = viewRef.current;
			const ctx = cb.current.block;
			if (!view || !ctx) return;

			const consume = () => {
				e.preventDefault();
				e.stopPropagation();
			};
			// Only a BARE key ever leaves the block. `cmd+up` is "go to the top of
			// the document" and `shift+up` is "extend the selection"; neither is a
			// request to visit the neighbour.
			const bare = !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey;
			const mod = e.metaKey || e.ctrlKey;

			// The menu owns arrows / enter / escape while it is open, and it has to
			// win over ProseMirror's Enter or a pick would split the paragraph.
			if (ctx.slashFrom !== null && ctx.onSlashKey(e.key)) {
				consume();
				return;
			}

			if (e.key === "Escape" && bare) {
				if (ctx.slashFrom !== null) ctx.onSlashClose();
				ctx.onSelectSelf();
				consume();
				return;
			}

			if (e.key === "Enter" && mod) {
				const state = view.state;
				const at = state.selection.from;
				const head = serializeRange(state.doc, 0, at);
				const tail = serializeRange(state.doc, at, state.doc.content.size);
				view.dispatch(state.tr.delete(at, state.doc.content.size));
				settle(head);
				if (ctx.slashFrom !== null) ctx.onSlashClose();
				ctx.onSplit(head, tail, null);
				consume();
				return;
			}

			if ((e.key === "ArrowUp" || e.key === "ArrowDown") && bare) {
				const dir: ExitDir = e.key === "ArrowUp" ? "up" : "down";
				if (dir === "up" ? !atTop(view) : !atBottom(view)) return;
				const column = view.state.selection.$from.parentOffset;
				const x = caretX(view);
				ctx.onExit(dir, column, x);
				consume();
				return;
			}

			if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && bare) {
				const sel = view.state.selection;
				if (!sel.empty) return;
				const dir: ExitDir = e.key === "ArrowLeft" ? "up" : "down";
				const at =
					dir === "up"
						? sel.from <= (firstTextblock(view.state.doc)?.start ?? 1)
						: sel.from >= (lastTextblock(view.state.doc)?.end ?? view.state.doc.content.size);
				if (!at) return;
				ctx.onExit(dir, undefined, undefined);
				consume();
				return;
			}

			// Backspace only leaves the block from the very first position of a
			// top-level textblock. Inside a list item or a quote it falls through
			// to ProseMirror, so backspace outdents first and only then merges up
			// -- one keypress per level, which is what a person expects.
			if (e.key === "Backspace" && bare) {
				const sel = view.state.selection;
				if (!sel.empty || sel.$from.depth !== 1) return;
				if (sel.from !== (firstTextblock(view.state.doc)?.start ?? -1)) return;
				const text = serializeMarkdown(view.state.doc);
				// This block is about to be folded into the one above. Park its own
				// text so the blur that follows has nothing left to save.
				settle(text);
				ctx.onMergeUp(text);
				consume();
				return;
			}

			if (e.key === "/" && !e.metaKey && !e.ctrlKey) {
				const sel = view.state.selection;
				if (!sel.empty || sel.$from.parentOffset !== 0) return;
				// Let the character land first, then anchor to it. Not consumed.
				const at = sel.from;
				window.setTimeout(() => {
					const live = viewRef.current;
					if (!live) return;
					try {
						const c = live.coordsAtPos(at);
						cb.current.block?.onSlashOpen(at, { x: c.left, y: c.bottom });
					} catch {
						/* the document moved under us; no menu */
					}
				}, 0);
			}
		},
		[settle],
	);

	// While the caret is in a block, that block owns the keyboard outright.
	// Without this the canvas sees the same keydown a moment after the editor
	// has already acted on it and acts again: one ArrowDown would leave the
	// block *and* walk the block selection on, skipping a block.
	const stop = useCallback((e: React.KeyboardEvent) => {
		if (cb.current.block) e.stopPropagation();
	}, []);

	const onBlur = useCallback(() => {
		cb.current.block?.onSlashClose();
	}, []);

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the wrapper is a keyboard seam over a contenteditable, not a control
		<div
			onKeyDownCapture={onKeyDownCapture}
			onKeyDown={stop}
			onKeyUp={syncSlash}
			onMouseUp={syncSlash}
			onBlur={onBlur}
		>
			<ProseEditor
				value={value}
				placeholder={hint}
				readOnly={readOnly}
				onCommit={commit}
				schema={proseDialect}
				className={docProseEditor}
				onView={onView}
			/>
		</div>
	);
}

export const ProseRef: NodeEntry = {
	component: ProseView,
	handlers: {
		write: (ctx, payload) =>
			ctx.update((props) => {
				// Scalar form: a bare string (or nil) replaces just the source.
				if (payload == null || typeof payload === "string") {
					props.value = payload == null ? "" : payload;
					return;
				}
				if (typeof payload === "object" && !Array.isArray(payload)) {
					Object.assign(props, payload);
					if ("value" in payload) {
						props.value = props.value == null ? "" : String(props.value);
					}
				}
			}),
	},
};
