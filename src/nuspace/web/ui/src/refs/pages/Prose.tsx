// The prose island.
//
// One island == one section == one editable. Contiguous prose is a single
// block, so inside it you get everything a text editor gives you for free:
// multi-paragraph selection, retype a range, undo, lists. That fluidity is
// the whole point of the island, and it is why we do not split prose per
// paragraph.
//
// ## What is borrowed and what is not
//
// The leaf is a ProseMirror view over a schema that can express paragraphs,
// three heading levels, two list flavours, a quote, a rule and four inline
// marks -- see ./prose/schema.ts. The test the task sets is whether the
// borrowed engine has any concept of a multi-block document, and the answer
// is that its schema cannot represent one: there is no node for a program
// block, a section or a page, so it has nowhere to put the things Nu owns.
// Ordering, lifecycle, the slash menu's structural half and every caret
// decision at a block boundary stay in Canvas.tsx and in this file.
//
// Within an island a document model is exactly right, because an island *is*
// a small document. That is the line.
//
// ## Always live
//
// There is no edit mode. The old leaf swapped a textarea for rendered
// markdown on blur, which meant a heading was heading-sized when you read it
// and 16px when you typed in it, and clicking put the caret at the start of
// whichever line string-matched. Both of those are gone by construction: the
// schema's `toDOM` hands out the same design recipes the reader sees, and a
// contenteditable puts the caret where you clicked.
//
// ## What this file really owns
//
// Caret behaviour at the boundary. Arrowing out of the first or last visual
// line into the neighbouring block and landing under where you were;
// backspace at the very start merging up; escape handing control back to
// block selection. All of it is bound so that only a *bare* arrow ever
// leaves the island -- prosemirror-keymap matches on the full key name, so
// `cmd+up` and `shift+up` cannot reach these handlers at all.

import { baseKeymap, chainCommands, setBlockType, toggleMark, wrapIn } from "prosemirror-commands";
import { history, redo, undo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import type { Node as PMNode } from "prosemirror-model";
import { liftListItem, sinkListItem, splitListItem, wrapInList } from "prosemirror-schema-list";
import { type Command, EditorState, TextSelection, type Transaction } from "prosemirror-state";
import { EditorView } from "prosemirror-view";
import {
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useLayoutEffect,
	useRef,
} from "react";
import { docProseEditor } from "../../design";
import {
	type Parsed,
	parseMarkdown,
	posForOffset,
	serializeMarkdown,
	serializeRange,
} from "./prose/markdown";
import { placeholder, proseInputRules } from "./prose/rules";
import { markType, nodeType } from "./prose/schema";
import type { SlashAction } from "./Slash";
import type { FocusReq } from "./slice";

export type ExitDir = "up" | "down";
export type InsertKind = "prose" | "program" | null;

const PLACEHOLDER = "Write, or press / for blocks";

/** Quiet-moment autosave. Long enough that a typist never triggers it. */
const SAVE_DELAY = 800;

export type ProseHandle = {
	/** Apply a slash-menu action against the live document and caret. */
	applySlash: (action: SlashAction) => void;
};

export type ProseProps = {
	blockId: string;
	source: string;
	/** Non-null when this block is the caret's target. */
	focusReq: FocusReq | null;
	/** Called once the focus request has been honoured. */
	onFocusConsumed: () => void;
	/** Persist. Only fires when the document actually changed. */
	onCommit: (source: string) => void;
	/**
	 * Caret left the island vertically. `column` is the desired character
	 * column; `x` is where the caret actually was on screen, which is what
	 * lands the caret under itself when the neighbour is also prose.
	 */
	onExit: (dir: ExitDir, column: number | undefined, x?: number) => void;
	/** Backspace at the very start. The parent decides merge vs select-previous. */
	onMergeUp: (source: string) => void;
	/** Split the island at the caret, optionally inserting a block between. */
	onSplit: (head: string, tail: string, insert: InsertKind) => void;
	/** `/` typed at the start of a line. `offset` is a document position. */
	onSlashOpen: (offset: number, anchor: { x: number; y: number }) => void;
	onSlashQuery: (query: string) => void;
	onSlashClose: () => void;
	/** Return true if the menu consumed the key. */
	onSlashKey: (key: string) => boolean;
	/** Position of the `/` while the menu is open on this block. */
	slashFrom: number | null;
	onSelectSelf: () => void;
};

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

/** The caret is on the first visual line of the island's first textblock. */
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
				const hit = view.posAtCoords({
					left: req.x,
					top: (edge.top + edge.bottom) / 2,
				});
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

/* ============================== component ================================ */

export const ProseIsland = forwardRef<ProseHandle, ProseProps>(
	function ProseIsland(props, handleRef) {
		const hostRef = useRef<HTMLDivElement | null>(null);
		const viewRef = useRef<EditorView | null>(null);
		/** The last parse of the server's source, for merge-seam offsets. */
		const parsedRef = useRef<Parsed>(parseMarkdown(props.source));
		/** The document changed since the last commit. Gates every write. */
		const dirtyRef = useRef(false);
		/** A pending merge seam, re-applied when the joined source arrives. */
		const seamRef = useRef<number | null>(null);
		/** Pending autosave. */
		const saveTimer = useRef<number | null>(null);
		/** Callbacks change identity every render; the view binds once. */
		const cb = useRef(props);
		cb.current = props;

		const serialize = useCallback((): string => {
			const view = viewRef.current;
			return view ? serializeMarkdown(view.state.doc) : cb.current.source;
		}, []);

		const commit = useCallback((): void => {
			if (saveTimer.current !== null) {
				window.clearTimeout(saveTimer.current);
				saveTimer.current = null;
			}
			if (!dirtyRef.current) return;
			dirtyRef.current = false;
			const next = serialize();
			if (next !== cb.current.source) cb.current.onCommit(next);
		}, [serialize]);

		// An always-live editor almost never blurs, so blur alone is not a save
		// story: reload the page mid-paragraph and the paragraph is gone. This
		// is the whole autosave -- a quiet moment is a save point. It is safe
		// to fire while the caret is here because a commit that round-trips to
		// the same markdown is dropped, and the re-ship is ignored unless the
		// document is clean.
		const queueSave = useCallback(() => {
			if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
			saveTimer.current = window.setTimeout(() => {
				saveTimer.current = null;
				commit();
			}, SAVE_DELAY);
		}, [commit]);

		// -- the slash query --------------------------------------------------

		const syncSlash = useCallback((view: EditorView) => {
			const from = cb.current.slashFrom;
			if (from === null) return;
			const doc = view.state.doc;
			const caret = view.state.selection.from;
			if (from + 1 > doc.content.size || doc.textBetween(from, from + 1) !== "/" || caret <= from) {
				cb.current.onSlashClose();
				return;
			}
			const query = doc.textBetween(from + 1, caret);
			if (/\s/.test(query)) {
				cb.current.onSlashClose();
				return;
			}
			cb.current.onSlashQuery(query);
		}, []);

		// -- the view ---------------------------------------------------------

		useLayoutEffect(() => {
			const host = hostRef.current;
			if (!host) return;

			const exit =
				(dir: ExitDir): Command =>
				(state, _dispatch, view) => {
					if (!view) return false;
					if (dir === "up" ? !atTop(view) : !atBottom(view)) return false;
					const column = state.selection.$from.parentOffset;
					const x = caretX(view);
					commit();
					cb.current.onExit(dir, column, x);
					return true;
				};

			const exitHorizontal =
				(dir: ExitDir): Command =>
				(state) => {
					const sel = state.selection;
					if (!sel.empty) return false;
					const edge = dir === "up" ? 0 : state.doc.content.size;
					const at =
						dir === "up"
							? sel.from <= (firstTextblock(state.doc)?.start ?? 1)
							: sel.from >= (lastTextblock(state.doc)?.end ?? edge);
					if (!at) return false;
					commit();
					cb.current.onExit(dir, undefined, undefined);
					return true;
				};

			// Backspace only leaves the island from the very first position of
			// a top-level textblock. Inside a list item or a quote it falls
			// through, so backspace outdents first and only then merges up --
			// one keypress per level, which is what a person expects.
			const mergeUp: Command = (state) => {
				const sel = state.selection;
				if (!sel.empty || sel.$from.depth !== 1) return false;
				if (sel.from !== (firstTextblock(state.doc)?.start ?? -1)) return false;
				dirtyRef.current = false;
				cb.current.onMergeUp(serializeMarkdown(state.doc));
				return true;
			};

			const splitHere: Command = (state) => {
				const at = state.selection.from;
				const head = serializeRange(state.doc, 0, at);
				const tail = serializeRange(state.doc, at, state.doc.content.size);
				dirtyRef.current = false;
				if (cb.current.slashFrom !== null) cb.current.onSlashClose();
				cb.current.onSplit(head, tail, null);
				return true;
			};

			const leaveIsland: Command = () => {
				if (cb.current.slashFrom !== null) cb.current.onSlashClose();
				commit();
				cb.current.onSelectSelf();
				return true;
			};

			const link: Command = (state, dispatch) => {
				const { from, to } = state.selection;
				if (from === to) return false;
				const href = window.prompt("Link to", "https://");
				if (!href) return true;
				dispatch?.(state.tr.addMark(from, to, markType.link.create({ href })));
				return true;
			};

			const boundary = keymap({
				Escape: leaveIsland,
				"Mod-Enter": splitHere,
				ArrowUp: exit("up"),
				ArrowDown: exit("down"),
				ArrowLeft: exitHorizontal("up"),
				ArrowRight: exitHorizontal("down"),
				Backspace: mergeUp,
			});

			const editing = keymap({
				Enter: chainCommands(splitListItem(nodeType.listItem), baseKeymap.Enter),
				Tab: sinkListItem(nodeType.listItem),
				"Shift-Tab": liftListItem(nodeType.listItem),
				"Mod-b": toggleMark(markType.strong),
				"Mod-i": toggleMark(markType.em),
				"Mod-e": toggleMark(markType.code),
				"Mod-k": link,
				"Mod-z": undo,
				"Mod-y": redo,
				"Shift-Mod-z": redo,
			});

			const state = EditorState.create({
				doc: parsedRef.current.doc,
				plugins: [
					boundary,
					proseInputRules(),
					editing,
					keymap(baseKeymap),
					history(),
					placeholder(PLACEHOLDER),
				],
			});

			const view = new EditorView(host, {
				state,
				attributes: { class: docProseEditor, spellcheck: "true" },
				dispatchTransaction(tr: Transaction) {
					const next = view.state.apply(tr);
					view.updateState(next);
					if (tr.docChanged) {
						dirtyRef.current = true;
						queueSave();
					}
					syncSlash(view);
				},
				handleKeyDown(v, event) {
					// The menu owns arrows / enter / escape while it is open.
					if (cb.current.slashFrom !== null && cb.current.onSlashKey(event.key)) {
						event.preventDefault();
						return true;
					}
					if (
						event.key === "/" &&
						!event.metaKey &&
						!event.ctrlKey &&
						v.state.selection.empty &&
						v.state.selection.$from.parentOffset === 0
					) {
						// Let the character land first, then anchor to it.
						const at = v.state.selection.from;
						window.setTimeout(() => {
							const live = viewRef.current;
							if (!live) return;
							try {
								const c = live.coordsAtPos(at);
								cb.current.onSlashOpen(at, { x: c.left, y: c.bottom });
							} catch {
								/* the document moved under us; no menu */
							}
						}, 0);
					}
					return false;
				},
				handleDOMEvents: {
					// While the caret is in an island, the island owns the
					// keyboard outright. Without this the canvas sees the same
					// keydown a moment after we have already acted on it and
					// acts again -- one ArrowDown would leave the island *and*
					// walk the block selection on, skipping a block, and Escape
					// would select this block and immediately deselect it.
					keydown: (_v, event) => {
						event.stopPropagation();
						return false;
					},
					blur: () => {
						if (cb.current.slashFrom !== null) cb.current.onSlashClose();
						commit();
						return false;
					},
				},
			});
			viewRef.current = view;

			return () => {
				if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
				saveTimer.current = null;
				viewRef.current = null;
				view.destroy();
			};
			// The view is built once and driven imperatively from here on.
		}, [commit, queueSave, syncSlash]);

		// -- server-owned source ----------------------------------------------

		// A re-ship lands on every structural op anywhere on the page and must
		// never yank text out from under someone who is typing -- but "typing"
		// means *uncommitted edits*, not merely holding focus. A merge lands
		// the caret here one render before the joined source arrives, so
		// refusing to adopt a clean re-ship would leave the merged text
		// invisible in the block that just swallowed it.
		useEffect(() => {
			const view = viewRef.current;
			if (!view || dirtyRef.current) return;
			if (serializeMarkdown(view.state.doc) === props.source) return;
			const parsed = parseMarkdown(props.source);
			parsedRef.current = parsed;
			const tr = view.state.tr.replaceWith(0, view.state.doc.content.size, parsed.doc.content);
			tr.setMeta("addToHistory", false);
			view.dispatch(tr);
			// Re-honour the seam: the offset was resolved against the old
			// document, and this is the document it was actually meant for.
			const seam = seamRef.current;
			if (seam !== null && view.hasFocus()) {
				seamRef.current = null;
				placeCaret(view, { blockId: "", place: "end", offset: seam }, parsed);
			}
		}, [props.source]);

		// -- focus routing -----------------------------------------------------

		const { focusReq, onFocusConsumed } = props;
		useEffect(() => {
			const view = viewRef.current;
			if (!focusReq || !view) return;
			seamRef.current = focusReq.offset ?? null;
			placeCaret(view, focusReq, parsedRef.current);
			onFocusConsumed();
		}, [focusReq, onFocusConsumed]);

		// -- the slash menu's imperative half ----------------------------------

		useImperativeHandle(
			handleRef,
			() => ({
				applySlash: (action: SlashAction) => {
					const view = viewRef.current;
					const from = cb.current.slashFrom;
					if (!view || from === null) return;
					const state = view.state;
					const to = Math.min(Math.max(state.selection.from, from + 1), state.doc.content.size);

					if (action.kind === "split") {
						// Everything before the `/` stays; everything after the
						// query becomes the tail.
						const head = serializeRange(state.doc, 0, from);
						const tail = serializeRange(state.doc, to, state.doc.content.size);
						dirtyRef.current = false;
						cb.current.onSlashClose();
						cb.current.onSplit(head, tail, action.insert);
						return;
					}

					// Drop the `/query`, then transform the block it was typed in.
					view.dispatch(state.tr.delete(from, to));
					cb.current.onSlashClose();

					if (action.kind === "literal") {
						view.dispatch(view.state.tr.replaceSelectionWith(nodeType.rule.create()));
					} else if (action.prefix === "- " || action.prefix === "1. ") {
						listCommand(action.prefix === "1. ")(view.state, view.dispatch, view);
					} else {
						PREFIX_COMMANDS[action.prefix]?.(view.state, view.dispatch, view);
					}
					view.focus();
				},
			}),
			[],
		);

		return <div ref={hostRef} />;
	},
);
