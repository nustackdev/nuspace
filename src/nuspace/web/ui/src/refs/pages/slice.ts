// The PagesRef slice: wire state + all browser-owned editor state.
//
// Two halves living on one slice.
//
// `value` is server-owned: the page tree and the active page's blocks. It is
// replaced wholesale by `set_tree` / `set_page`, patched by `set_status`.
//
// `editor` is browser-owned and the server never sees it: caret intent, block
// selection, which program blocks are open in code mode, the slash menu, the
// drag in flight, the rail's expanded set. None of it survives a reload, and
// none of it should.
//
// ## Registering a block's fields
//
// `store.mount()` only builds slices for the static mount envelope and there
// is no post-mount registration action. But `SliceCtx` hands every factory a
// `set(mutator)` that mutates `draft.refs` directly, and the kit exports
// `factories` + `FieldView`. So this slice registers a program block's fields
// itself when `set_page` lands. Inbound frames then route normally (same refs
// map), outbound goes through `ctx.send`, and `disposeAll` cleans up.
//
// Slices that outlive a `set_page` are kept, not rebuilt (see
// `registerFields`); only the ones that disappeared get disposed. We never
// remount the shell on navigation either -- a remount wipes every slice on the
// page, including Lens's.

import type { RefSlice, SliceCtx, SliceFactory } from "@nustackdev/ui-kit";
import { factories, useStore } from "@nustackdev/ui-kit";
import {
	type ActivePage,
	type Block,
	coerceBlocks,
	coerceNode,
	coerceStatus,
	coerceStrs,
	EMPTY_TREE,
	type PagesValue,
	type SectionStatus,
} from "./types";

// -- browser-owned editor state ----------------------------------------------

/** Where the caret should land next. Consumed by the block that owns it. */
export type FocusReq = {
	blockId: string;
	/** Which end of the target editor to enter from. */
	place: "start" | "end";
	/**
	 * Desired visual column, carried across a block boundary so arrowing
	 * down out of one block and into the next lands under the caret rather
	 * than at column 0. Best effort: monospace vs prose widths differ.
	 */
	column?: number;
	/**
	 * Where the caret actually was on screen when it left the previous block.
	 * A character column is a guess once text wraps or the fonts differ; a
	 * pixel column is not, so this wins over `column` wherever the target
	 * editor can resolve coordinates. Only prose produces it.
	 */
	x?: number;
	/**
	 * Exact character offset, used when we know it precisely -- after a merge
	 * the caret belongs at the seam, not at either end. Wins over `place`.
	 */
	offset?: number;
};

export type SlashState = {
	/** Block the menu will act on. */
	blockId: string;
	/** "inline": the trigger is a `/` typed in prose, and `from`..`to` is the
	 * query text to be removed on commit. "insert": opened from the gutter,
	 * nothing to remove, the new block goes after `blockId`. */
	mode: "inline" | "insert";
	query: string;
	from: number;
	to: number;
	anchor: { x: number; y: number };
	index: number;
};

export type DragState = {
	id: string;
	/** Insertion index in the current block list, 0..blocks.length. */
	at: number;
	y: number;
};

export type EditorState = {
	focus: FocusReq | null;
	/**
	 * The block that currently holds DOM focus, reported by the canvas.
	 *
	 * Distinct from `focus`, which is an *intent* ("put the caret here") and
	 * is consumed and cleared the moment the target editor honours it. The
	 * gutter's focus rail wants the opposite: the standing fact of where the
	 * caret lives, for as long as it lives there.
	 */
	focused: string | null;
	selected: string[];
	/** Anchor for shift-extended block selection. */
	anchor: string | null;
	/** Program blocks currently open in code mode. Per block, never global. */
	editing: string[];
	slash: SlashState | null;
	drag: DragState | null;
	expanded: string[];
	/**
	 * Desired visual column, parked while the caret is "between" editors --
	 * i.e. while a live program block is merely *selected*. Without this the
	 * column resets every time vertical travel hops over a program block, and
	 * arrowing down through a document drifts back to the left margin.
	 */
	column: number | null;
	/** The pixel column, parked alongside `column` and for the same reason. */
	x: number | null;
};

export const EMPTY_EDITOR: EditorState = {
	focus: null,
	focused: null,
	selected: [],
	anchor: null,
	editing: [],
	slash: null,
	drag: null,
	expanded: [],
	column: null,
	x: null,
};

type PagesSlice = RefSlice & {
	value: PagesValue;
	editor: EditorState;
	sectionPaths: string[];
};

// -- factory -----------------------------------------------------------------

/**
 * Reconcile the block field slices, keeping the ones that survive.
 *
 * A `set_page` lands after *any* structural op anywhere on the page, but the
 * supervisor only restarts the sections that actually changed. A section that
 * was left alone will not re-send its values, so rebuilding its slices from
 * scratch would blank a running block's output for no reason. So: create what
 * is new, dispose what is gone, and leave everything else exactly where it is.
 */
function registerFields(
	refs: Record<string, RefSlice>,
	ctx: SliceCtx,
	blocks: Block[],
	previous: string[],
): string[] {
	const registered: string[] = [];
	const wanted = new Set<string>();

	for (const block of blocks) {
		for (const f of block.fields) {
			wanted.add(f.path);
			registered.push(f.path);
			// Same path *and* same type survives; a type change is a new slice.
			if (refs[f.path]?.type === f.type) continue;
			const build = factories[f.type];
			if (!build) {
				console.warn(`nuspace: no factory for block field "${f.type}"`);
				continue;
			}
			const childPaths = (f.fields ?? []).map((c) => c.path);
			refs[f.path] = build(f.path, ctx, f.props, childPaths);
		}
	}

	for (const p of previous) {
		if (wanted.has(p)) continue;
		const s = refs[p];
		if (s?.dispose) {
			try {
				s.dispose();
			} catch (err) {
				console.warn(`nuspace: dispose threw for ${p}`, err);
			}
		}
		delete refs[p];
	}
	return registered;
}

export const pagesSliceFactory: SliceFactory = (path, ctx, _props) =>
	({
		type: "PagesRef",
		value: { tree: EMPTY_TREE, page: null } as PagesValue,
		editor: { ...EMPTY_EDITOR },
		sectionPaths: [] as string[],
		write: (v) =>
			ctx.set((refs) => {
				const slice = refs[path] as PagesSlice | undefined;
				if (!slice) return;
				const p = (v ?? {}) as Record<string, unknown>;
				const op = String(p.op ?? "");

				if (op === "set_tree") {
					slice.value = { ...slice.value, tree: coerceNode(p.tree, null) };
					return;
				}

				if (op === "set_status") {
					const page = slice.value.page;
					if (!page) return;
					const byId = new Map<string, SectionStatus>();
					for (const raw of Array.isArray(p.statuses) ? p.statuses : []) {
						const st = coerceStatus(raw);
						if (st?.section_id) byId.set(st.section_id, st);
					}
					if (byId.size === 0) return;
					slice.value = {
						...slice.value,
						page: {
							...page,
							blocks: page.blocks.map((b) =>
								byId.has(b.id) ? { ...b, status: byId.get(b.id) ?? b.status } : b,
							),
						},
					};
					return;
				}

				if (op !== "set_page") return;

				const blocks = coerceBlocks(p.blocks);
				const page: ActivePage = {
					page_id: p.page_id == null ? null : String(p.page_id),
					path: coerceStrs(p.path),
					title: String(p.title ?? ""),
					blocks,
				};

				slice.sectionPaths = registerFields(refs, ctx, blocks, slice.sectionPaths ?? []);
				slice.value = { ...slice.value, page };

				// Prune editor state that points at blocks which no longer exist.
				// Focus and drag are dropped outright -- a re-ship means the
				// document moved under them and guessing is worse than nothing.
				const live = new Set(blocks.map((b) => b.id));
				const ed = slice.editor;
				slice.editor = {
					...ed,
					focus: ed.focus && live.has(ed.focus.blockId) ? ed.focus : null,
					focused: ed.focused && live.has(ed.focused) ? ed.focused : null,
					selected: ed.selected.filter((id) => live.has(id)),
					anchor: ed.anchor && live.has(ed.anchor) ? ed.anchor : null,
					editing: ed.editing.filter((id) => live.has(id)),
					slash: ed.slash && live.has(ed.slash.blockId) ? ed.slash : null,
					drag: null,
				};
			}),
		dispose: () => {
			// Block field slices live in the same refs map, so the kit's
			// disposeAll already reaches them.
		},
	}) as PagesSlice;

// -- reads -------------------------------------------------------------------

export function usePagesValue(path: string): PagesValue | null {
	return useStore((s) => (s.refs[path]?.value as PagesValue | undefined) ?? null);
}

export function useEditorState(path: string): EditorState {
	return useStore((s) => (s.refs[path] as PagesSlice | undefined)?.editor ?? EMPTY_EDITOR);
}

/** Narrow subscription so a keystroke in one block does not rerender the rest. */
export function useEditorSlot<T>(path: string, pick: (e: EditorState) => T): T {
	return useStore((s) => pick((s.refs[path] as PagesSlice | undefined)?.editor ?? EMPTY_EDITOR));
}

// -- writes ------------------------------------------------------------------

/**
 * Patch the browser-owned editor state. Module-level rather than a hook so
 * event handlers deep in the tree can call it without prop-drilling, and so
 * it never participates in a render.
 */
export function patchEditor(
	path: string,
	patch: Partial<EditorState> | ((e: EditorState) => Partial<EditorState>),
): void {
	useStore.setState((s) => {
		const slice = s.refs[path] as PagesSlice | undefined;
		if (!slice) return;
		const next = typeof patch === "function" ? patch(slice.editor) : patch;
		slice.editor = { ...slice.editor, ...next };
	});
}
