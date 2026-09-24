// A page: one Plane's blocks, as a document you write in.
//
// `editable` is the page's own setting and the thing here that branches on
// it: with it you get the gutter, the insert affordances, the drag handle,
// the code toggle and the keyboard, and without it the same blocks render
// their output with none of them. `wide` is the full-width setting.
//
// Everything structural lives in this directory and nowhere else: ordering,
// keyboard, selection, focus routing, the slash menu, drag reorder, block
// lifecycle. No library supplies any of it, because no library knows what a
// running Nu section is. This file wires it together and draws the list:
//
//   useFocusRouting.ts   where the caret goes, across block boundaries
//   useStructure.ts      save, create, delete, move
//   useBlockKeys.ts      the block-selection keyboard
//   useBlockDrag.ts      drag reorder
//   useSlash.ts          the `/` menu's behaviour (SlashMenu.tsx draws it)
//   useGhosts.ts         the ghost inputs' wiring (Ghost.tsx draws one)
//   block/               one block: its row, gutter, program, source editor

import type { Path } from "@nustackdev/ui-core";
import { pathKey } from "@nustackdev/ui-kit";
import { Fragment, useCallback, useRef } from "react";
import { docColumn, docDropIndicator, docTail } from "../design";
import { blockUiPath } from "./block/address";
import { Block } from "./block/Block";
import { Ghost } from "./Ghost";
import type { PageModel } from "./model";
import type { Notify } from "./ops";
import { SlashMenu } from "./SlashMenu";
import { type EditorPatch, patchEditor, useEditorState } from "./state";
import type { ActivePage, SlashSnippet } from "./types";
import { useBlockDrag } from "./useBlockDrag";
import { useBlockKeys } from "./useBlockKeys";
import { useFocusRouting } from "./useFocusRouting";
import { useGhosts } from "./useGhosts";
import { useSlash } from "./useSlash";
import { useStructure } from "./useStructure";

const NO_SNIPPETS: SlashSnippet[] = [];
const NONE: string[] = [];

export function Page({
	viewerPath,
	page,
	snippets = NO_SNIPPETS,
	editable,
	wide,
	compact,
	notify,
}: {
	/** The ViewerRef node, which holds every pane's editor state and roots
	 *  every block's refs. */
	viewerPath: Path;
	page: ActivePage;
	/** The registered snippets, in order: the `/` menu's rows. */
	snippets?: SlashSnippet[];
	/** The page's setting. False draws the same blocks, output only. */
	editable: boolean;
	/** The page's full-width setting. */
	wide: boolean;
	/** The page's compact setting: no run-off under the last block. */
	compact: boolean;
	notify: Notify;
}) {
	const blocks = page.blocks;
	const pageId = page.page_id;
	// Per pane: two pages side by side never share a selection or a ghost.
	const editor = useEditorState(viewerPath, pageId);
	const viewerKey = pathKey(viewerPath);

	const rootRef = useRef<HTMLDivElement | null>(null);
	const elRefs = useRef(new Map<string, HTMLElement>());
	const endGhost = useRef<HTMLInputElement | null>(null);
	const plusGhost = useRef<HTMLInputElement | null>(null);

	const index = useCallback((id: string) => blocks.findIndex((b) => b.id === id), [blocks]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const patch = useCallback(
		(p: EditorPatch) => patchEditor(viewerPath, pageId, p),
		[viewerKey, pageId],
	);

	const model: PageModel = {
		pageId,
		blocks,
		editor,
		patch,
		notify,
		index,
		rootRef,
		elRefs,
		endGhost,
		plusGhost,
	};

	const { focusBlock, step, enterBlock, setEditing, selectBlock } = useFocusRouting(model);
	const { commitSource, createAfter, deleteBlocks, moveSelected } = useStructure(model);
	const onBlockKeys = useBlockKeys(model, { focusBlock, enterBlock, deleteBlocks, moveSelected });
	const startDrag = useBlockDrag(model);
	const { slash, slashItems, pickSlash, slashKey, moveSlash } = useSlash(
		model,
		snippets,
		createAfter,
	);
	const ghostProps = useGhosts(model, { focusBlock, createAfter, slashKey });

	// -- where the caret actually is ------------------------------------------
	//
	// `editor.focus` is an intent and is consumed the instant a block honours
	// it, so it cannot answer "which block is the caret in" -- which is what
	// the gutter's focus rail needs. Focus events bubble (focusin/focusout), so
	// one listener on the page root reports the standing fact for every editor
	// inside it, including ones we do not own (Monaco, a block's refs).

	const onPageFocus = useCallback(
		(e: React.FocusEvent) => {
			const host = (e.target as HTMLElement).closest?.("[data-block]");
			const id = host?.getAttribute("data-block") ?? null;
			patch((ed) => (ed.focused === id ? {} : { focused: id }));
		},
		[patch],
	);

	const onPageBlur = useCallback(
		(e: React.FocusEvent) => {
			// Focus moving between two editors inside the page fires blur
			// before focus; only a departure that leaves the page clears it.
			const next = e.relatedTarget as Node | null;
			if (next && rootRef.current?.contains(next)) return;
			patch((ed) => (ed.focused === null ? {} : { focused: null }));
		},
		[patch],
	);

	// -- render ---------------------------------------------------------------

	const setEl = useCallback((id: string, el: HTMLElement | null) => {
		if (el) elRefs.current.set(id, el);
		else elRefs.current.delete(id);
	}, []);

	// A read-only page has no selection and no open source, whatever the
	// editor state still remembers from before the switch flipped.
	const selectedIds = editable ? editor.selected : NONE;
	const editingIds = editable ? editor.editing : NONE;
	const drag = editor.drag;
	const lastId = blocks.length ? blocks[blocks.length - 1].id : null;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the page is the keyboard owner in block-selection mode
		<div
			ref={rootRef}
			tabIndex={-1}
			onKeyDown={editable ? onBlockKeys : undefined}
			onFocus={onPageFocus}
			onBlur={onPageBlur}
			className={`${docColumn(wide, compact)} outline-none`}
		>
			{blocks.map((block, i) => {
				const selected = selectedIds.includes(block.id);
				const editing = editingIds.includes(block.id);
				return (
					<Fragment key={block.id}>
						<Block
							block={block}
							uiPath={blockUiPath(viewerPath, block.id)}
							editable={editable}
							selected={selected}
							selectedStrong={selected && selectedIds.length > 1}
							focused={editor.focused === block.id}
							editing={editing}
							focusReq={editor.focus?.blockId === block.id ? editor.focus : null}
							dragging={drag?.id === block.id}
							dropAbove={drag != null && drag.at === i}
							setEl={(el) => setEl(block.id, el)}
							onPointerIn={() => {
								if (editor.selected.length > 0) patch({ selected: [], anchor: null });
							}}
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
							onSelect={() => selectBlock(block.id)}
							onFocusConsumed={() => patch({ focus: null })}
							onCommit={(src) => commitSource(block.id, src)}
							onExit={(dir, column) => step(block.id, dir, column)}
						/>
						{editable && editor.ghost === block.id ? (
							<Ghost {...ghostProps(block.id, true)} />
						) : null}
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
			    affordances. */}
			{editable ? <Ghost {...ghostProps(lastId, false)} /> : null}
			{/* The run-off under the last block is the page's compact setting, not
			    its editable one. Clicking it aims at the ghost when there is one. */}
			{compact ? null : (
				// biome-ignore lint/a11y/noStaticElementInteractions: the run-off under a document is a click target, not a control -- the keyboard reaches the same ghost by arrowing down
				<div
					className={docTail}
					onMouseDown={(e) => {
						// mousedown and not click, and preventDefault: the caret has to
						// land in the ghost, not in the empty div that was clicked.
						if (!editable || e.button !== 0) return;
						e.preventDefault();
						endGhost.current?.focus();
					}}
				/>
			)}

			{editable && slash ? (
				<SlashMenu
					items={slashItems}
					index={slash.index}
					anchor={slash.anchor}
					onPick={pickSlash}
					onMove={moveSlash}
				/>
			) : null}
		</div>
	);
}
