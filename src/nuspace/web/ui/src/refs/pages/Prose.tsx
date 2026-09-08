// The prose island.
//
// One island == one section == one editable. Contiguous prose is a single
// block, so inside it you get everything a text editor gives you for free:
// multi-paragraph selection, retype a range, undo, lists. That fluidity is the
// whole point of the island, and it is why we do not split prose per
// paragraph.
//
// The leaf is deliberately the simplest thing that works: a textarea over
// markdown, rendered on blur. It is a *swappable* leaf -- everything outside
// this file knows only the props below (source in; commit / split / merge /
// exit out) plus one imperative handle for the slash menu. Replacing it with
// a real inline editor is a one-file change. The test the task sets is
// whether the borrowed engine has any concept of a multi-block document; a
// textarea has no concept of anything, which is exactly the point.
//
// What this file really owns, and what makes or breaks the feel, is caret
// behaviour at the boundary: arrowing out of the first or last line into the
// neighbouring block and landing under where you were.

import {
	forwardRef,
	useCallback,
	useEffect,
	useImperativeHandle,
	useLayoutEffect,
	useRef,
	useState,
} from "react";
import { docProse } from "../../design";
import { renderMarkdown } from "./markdown";
import type { SlashAction } from "./Slash";
import type { FocusReq } from "./slice";

export type ExitDir = "up" | "down";
export type InsertKind = "prose" | "program" | null;

export type ProseHandle = {
	/** Apply a slash-menu action against the live buffer and caret. */
	applySlash: (action: SlashAction) => void;
};

export type ProseProps = {
	blockId: string;
	source: string;
	/** Non-null when this block is the caret's target. */
	focusReq: FocusReq | null;
	/** Called once the focus request has been honoured. */
	onFocusConsumed: () => void;
	/** Persist. Only fires when the text actually changed. */
	onCommit: (source: string) => void;
	/** Caret left the island vertically. `column` is the desired visual column. */
	onExit: (dir: ExitDir, column: number | undefined) => void;
	/** Backspace at offset 0. The parent decides merge vs select-previous. */
	onMergeUp: (source: string) => void;
	/** Split the island at the caret, optionally inserting a block between. */
	onSplit: (head: string, tail: string, insert: InsertKind) => void;
	/** `/` typed at the start of a line. */
	onSlashOpen: (offset: number, anchor: { x: number; y: number }) => void;
	onSlashQuery: (query: string) => void;
	onSlashClose: () => void;
	/** Return true if the menu consumed the key. */
	onSlashKey: (key: string) => boolean;
	/** Offset of the `/` while the menu is open on this block. */
	slashFrom: number | null;
	onSelectSelf: () => void;
};

// -- caret geometry ----------------------------------------------------------

type LineInfo = {
	index: number;
	start: number;
	end: number;
	column: number;
	count: number;
};

function lineInfo(text: string, offset: number): LineInfo {
	const before = text.slice(0, offset);
	const index = before.split("\n").length - 1;
	const start = before.lastIndexOf("\n") + 1;
	const nl = text.indexOf("\n", offset);
	const end = nl === -1 ? text.length : nl;
	return {
		index,
		start,
		end,
		column: offset - start,
		count: text.split("\n").length,
	};
}

/** Where the caret lands when entering this island. */
function entryOffset(text: string, req: FocusReq): number {
	if (req.offset !== undefined)
		return Math.max(0, Math.min(req.offset, text.length));
	const lines = text.split("\n");
	if (req.place === "start") {
		return Math.min(req.column ?? 0, (lines[0] ?? "").length);
	}
	if (req.column === undefined) return text.length;
	const last = lines[lines.length - 1] ?? "";
	return text.length - last.length + Math.min(req.column, last.length);
}

/** Strip an existing markdown line prefix so prefix items are idempotent. */
function stripPrefix(line: string): string {
	return line.replace(/^\s*(#{1,3}\s+|[-*+]\s+|\d+[.)]\s+|>\s?)/, "");
}

// -- component ---------------------------------------------------------------

export const ProseIsland = forwardRef<ProseHandle, ProseProps>(
	function ProseIsland(props, handleRef) {
		const {
			source,
			focusReq,
			onFocusConsumed,
			onCommit,
			onExit,
			onMergeUp,
			onSplit,
			onSlashOpen,
			onSlashQuery,
			onSlashClose,
			onSlashKey,
			slashFrom,
			onSelectSelf,
		} = props;

		const [editing, setEditing] = useState(false);
		const [text, setText] = useState(source);
		const ref = useRef<HTMLTextAreaElement | null>(null);
		const pendingCaret = useRef<number | null>(null);
		const textRef = useRef(text);
		textRef.current = text;
		const editingRef = useRef(editing);
		editingRef.current = editing;
		const slashFromRef = useRef(slashFrom);
		slashFromRef.current = slashFrom;

		// Re-seed from the server only while we are not the active editor. A
		// re-ship lands on every structural op anywhere on the page and must
		// never yank text out from under someone who is typing.
		useEffect(() => {
			if (!editingRef.current) setText(source);
		}, [source]);

		const autosize = useCallback(() => {
			const el = ref.current;
			if (!el) return;
			el.style.height = "0px";
			el.style.height = `${el.scrollHeight}px`;
		}, []);

		useLayoutEffect(() => {
			if (editing) autosize();
		}, [editing, autosize]);

		// Honour a focus request: enter edit mode, then place the caret once
		// the textarea exists.
		useEffect(() => {
			if (!focusReq) return;
			pendingCaret.current = entryOffset(textRef.current, focusReq);
			setEditing(true);
			onFocusConsumed();
		}, [focusReq, onFocusConsumed]);

		useLayoutEffect(() => {
			const el = ref.current;
			if (!el || pendingCaret.current === null) return;
			const at = pendingCaret.current;
			pendingCaret.current = null;
			el.focus({ preventScroll: true });
			el.setSelectionRange(at, at);
			autosize();
		});

		const commit = useCallback(() => {
			if (textRef.current !== source) onCommit(textRef.current);
		}, [onCommit, source]);

		const leave = useCallback(() => {
			if (slashFromRef.current !== null) onSlashClose();
			setEditing(false);
			commit();
		}, [commit, onSlashClose]);

		// -- slash application (imperative: the buffer lives here) -------------

		useImperativeHandle(
			handleRef,
			() => ({
				applySlash: (action: SlashAction) => {
					const el = ref.current;
					const from = slashFromRef.current;
					if (!el || from === null) return;
					const value = el.value;
					const to = Math.max(el.selectionStart, from + 1);
					const li = lineInfo(value, from);

					if (action.kind === "split") {
						// Everything above the `/` line stays; everything after the
						// query becomes the tail.
						const head = value.slice(0, li.start).replace(/\n+$/, "");
						const tail = value.slice(to);
						onSlashClose();
						setEditing(false);
						onSplit(head, tail, action.insert);
						return;
					}

					const rest = stripPrefix(value.slice(to));
					const next =
						action.kind === "prefix"
							? value.slice(0, li.start) + action.prefix + rest
							: value.slice(0, li.start) + action.text + rest;
					const caret =
						li.start +
						(action.kind === "prefix"
							? action.prefix.length
							: action.text.length);
					setText(next);
					pendingCaret.current = caret;
					onSlashClose();
					window.setTimeout(() => {
						const t = ref.current;
						if (!t) return;
						t.focus({ preventScroll: true });
						t.setSelectionRange(caret, caret);
					}, 0);
				},
			}),
			[onSlashClose, onSplit],
		);

		// -- entering from a click --------------------------------------------

		const enterAtClick = useCallback((e: React.MouseEvent) => {
			// Best-effort caret placement. Exact character placement inside a
			// rendered heading or list marker is not recoverable without a real
			// inline editor, so we land at the start of the clicked line.
			const target = e.target as HTMLElement | null;
			const line =
				target?.closest("p,li,h1,h2,h3,blockquote")?.textContent ?? "";
			const src = textRef.current;
			let at = src.length;
			if (line) {
				const probe = line.slice(0, 24);
				const hit = probe ? src.indexOf(probe) : -1;
				if (hit >= 0) at = hit;
			}
			pendingCaret.current = at;
			setEditing(true);
		}, []);

		// -- keys --------------------------------------------------------------

		const syncSlash = useCallback(
			(el: HTMLTextAreaElement) => {
				const from = slashFromRef.current;
				if (from === null) return;
				const value = el.value;
				const caret = el.selectionStart;
				if (value[from] !== "/" || caret <= from) {
					onSlashClose();
					return;
				}
				const query = value.slice(from + 1, caret);
				if (/\s/.test(query)) {
					onSlashClose();
					return;
				}
				onSlashQuery(query);
			},
			[onSlashClose, onSlashQuery],
		);

		const onKeyDown = useCallback(
			(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
				const el = e.currentTarget;
				const value = el.value;
				const start = el.selectionStart;
				const end = el.selectionEnd;
				const collapsed = start === end;

				if (slashFromRef.current !== null && onSlashKey(e.key)) {
					e.preventDefault();
					return;
				}

				if (e.key === "Escape") {
					e.preventDefault();
					leave();
					onSelectSelf();
					return;
				}

				if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
					// Explicit split. An island stays one section until someone
					// says otherwise.
					e.preventDefault();
					onSplit(value.slice(0, start), value.slice(end), null);
					setEditing(false);
					return;
				}

				// A modifier means "move within this field" (cmd+up = go to the
				// top of the textarea, shift+up = extend a selection). Only a
				// bare arrow ever leaves the block.
				const bare = !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey;

				if (e.key === "ArrowUp" && collapsed && bare) {
					const li = lineInfo(value, start);
					if (li.index === 0) {
						e.preventDefault();
						commit();
						setEditing(false);
						onExit("up", li.column);
					}
					return;
				}

				if (e.key === "ArrowDown" && collapsed && bare) {
					const li = lineInfo(value, start);
					if (li.index === li.count - 1) {
						e.preventDefault();
						commit();
						setEditing(false);
						onExit("down", li.column);
					}
					return;
				}

				if (e.key === "ArrowLeft" && collapsed && bare && start === 0) {
					e.preventDefault();
					commit();
					setEditing(false);
					onExit("up", undefined);
					return;
				}

				if (
					e.key === "ArrowRight" &&
					collapsed &&
					bare &&
					start === value.length
				) {
					e.preventDefault();
					commit();
					setEditing(false);
					onExit("down", 0);
					return;
				}

				if (
					e.key === "Backspace" &&
					collapsed &&
					start === 0 &&
					!e.metaKey &&
					!e.ctrlKey
				) {
					e.preventDefault();
					setEditing(false);
					onMergeUp(value);
					return;
				}

				if (e.key === "/") {
					const li = lineInfo(value, start);
					if (start === li.start) {
						// Let the character land first, then anchor to the caret.
						const rect = el.getBoundingClientRect();
						const lineH = el.scrollHeight / Math.max(1, li.count);
						window.setTimeout(
							() =>
								onSlashOpen(start, {
									x: rect.left,
									y: rect.top + (li.index + 1) * lineH,
								}),
							0,
						);
					}
				}
			},
			[
				commit,
				leave,
				onExit,
				onMergeUp,
				onSelectSelf,
				onSlashKey,
				onSlashOpen,
				onSplit,
			],
		);

		// -- render ------------------------------------------------------------

		if (!editing) {
			return (
				// biome-ignore lint/a11y/noStaticElementInteractions: clicking the rendered markdown is how you enter the island's editor
				<div className={`${docProse} cursor-text`} onMouseUp={enterAtClick}>
					{source.trim() === "" ? (
						<p className="text-text-muted">Write, or press / for blocks</p>
					) : (
						renderMarkdown(source)
					)}
				</div>
			);
		}

		return (
			<textarea
				ref={ref}
				value={text}
				spellCheck
				onChange={(e) => {
					setText(e.target.value);
					autosize();
					syncSlash(e.currentTarget);
				}}
				onKeyUp={(e) => syncSlash(e.currentTarget)}
				onClick={(e) => syncSlash(e.currentTarget)}
				onKeyDown={onKeyDown}
				onBlur={leave}
				className={`${docProse} block w-full resize-none overflow-hidden bg-transparent outline-none placeholder:text-text-muted`}
				placeholder="Write, or press / for blocks"
			/>
		);
	},
);
