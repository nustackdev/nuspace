// A plane: one Plane's cells, as a document you write in.
//
// `editable` is the plane's own setting and the thing here that branches on
// it: with it you get the gutter, the insert affordances, the drag handle,
// the code toggle and the keyboard, and without it the same cells render
// their output with none of them. `wide` is the full-width setting.
//
// Everything structural lives in this directory and nowhere else: ordering,
// keyboard, selection, focus routing, the slash menu, drag reorder, cell
// lifecycle. No library supplies any of it, because no library knows what a
// running Nu cell is. This file wires it together and draws the list:
//
//   useFocusRouting.ts   where the caret goes, across cell boundaries
//   useStructure.ts      save, create, delete, move
//   useCellKeys.ts      the cell-selection keyboard
//   useCellDrag.ts      drag reorder
//   useBoxSelect.ts      selecting cells by dragging a box around them
//   useSlash.ts          the `/` menu's behaviour (SlashMenu.tsx draws it)
//   useGhosts.ts         the ghost inputs' wiring (Ghost.tsx draws one)
//   Draft.tsx            typing into a ghost, carried into a new text cell
//   useTextCells.ts      text cells: Cmd+Enter, Backspace, Enter in the title
//   cell/               one cell: its row, gutter, program, source editor

import type { Path } from "@nustackdev/ui-core";
import { pathKey } from "@nustackdev/ui-kit";
import { Fragment, useCallback, useEffect, useRef } from "react";
import {
	docBoxSelect,
	docColumn,
	docContentTrack,
	docDropIndicator,
	docRow,
	docTail,
} from "../design";
import { cellUiPath } from "./cell/address";
import { Cell } from "./cell/Cell";
import { Draft, useDraft } from "./Draft";
import { Ghost } from "./Ghost";
import type { PlaneModel } from "./model";
import type { Notify } from "./ops";
import { SlashMenu } from "./SlashMenu";
import { type EditorPatch, patchEditor, useEditorState } from "./state";
import type { ActivePlane, SlashSnippet } from "./types";
import { useBoxSelect } from "./useBoxSelect";
import { useCellDrag } from "./useCellDrag";
import { useCellKeys } from "./useCellKeys";
import { useFocusRouting } from "./useFocusRouting";
import { useGhosts } from "./useGhosts";
import { useSlash } from "./useSlash";
import { useStructure } from "./useStructure";
import { useTextCells } from "./useTextCells";

const NO_SNIPPETS: SlashSnippet[] = [];
const NONE: string[] = [];

export function Plane({
	viewerPath,
	plane,
	snippets = NO_SNIPPETS,
	editable,
	wide,
	compact,
	notify,
	entryRef,
	splitRef,
	openRef,
	selectRef,
}: {
	/** The ViewerRef node, which holds every pane's editor state and roots
	 *  every cell's refs. */
	viewerPath: Path;
	plane: ActivePlane;
	/** The registered snippets, in order: the `/` menu's rows. */
	snippets?: SlashSnippet[];
	/** The plane's setting. False draws the same cells, output only. */
	editable: boolean;
	/** The plane's full-width setting. */
	wide: boolean;
	/** The plane's compact setting: no run-off under the last cell. */
	compact: boolean;
	notify: Notify;
	/** Set to "take the caret from the title above", null while the plane is
	 *  read-only and has nowhere to put one. */
	entryRef?: React.RefObject<(() => boolean) | null>;
	/** Set to "start a text cell at the top holding this", from Enter in the
	 *  title above. Null while there is no such thing to start. */
	splitRef?: React.RefObject<((tail: string) => boolean) | null>;
	/** Set to "open a ghost at the top, Escape going to `home`", from Enter
	 *  at the end of the title. Null while there is no such thing to open. */
	openRef?: React.RefObject<((home: () => void) => boolean) | null>;
	/** Set to "a press landed in the pane": where box selection starts, so
	 *  the margins beside the plane count. */
	selectRef?: React.RefObject<((e: React.PointerEvent) => void) | null>;
}) {
	const cells = plane.cells;
	const planeId = plane.plane_id;
	// Per pane: two planes side by side never share a selection or a ghost.
	const editor = useEditorState(viewerPath, planeId);
	const viewerKey = pathKey(viewerPath);

	const rootRef = useRef<HTMLDivElement | null>(null);
	const elRefs = useRef(new Map<string, HTMLElement>());
	const endGhost = useRef<HTMLInputElement | null>(null);
	const plusGhost = useRef<HTMLInputElement | null>(null);

	const index = useCallback((id: string) => cells.findIndex((b) => b.id === id), [cells]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const patch = useCallback(
		(p: EditorPatch) => patchEditor(viewerPath, planeId, p),
		[viewerKey, planeId],
	);

	const model: PlaneModel = {
		planeId,
		cells,
		editor,
		patch,
		notify,
		index,
		rootRef,
		elRefs,
		endGhost,
		plusGhost,
	};

	const { focusCell, step, enterCell, setEditing, selectCell, enterTop } = useFocusRouting(model);
	const { commitSource, createAfter, deleteCells, moveSelected } = useStructure(model);
	const onCellKeys = useCellKeys(model, editable, {
		focusCell,
		enterCell,
		deleteCells,
		moveSelected,
	});
	const startDrag = useCellDrag(model);
	const { box, startBox } = useBoxSelect(model);
	const { slash, slashItems, pickSlash, slashKey, moveSlash } = useSlash(
		model,
		snippets,
		createAfter,
	);
	const { draft, boxRef, startDraft } = useDraft(model, viewerPath, snippets, createAfter);
	const { ghostProps, openGhost } = useGhosts(model, {
		focusCell,
		createAfter,
		slashKey,
		startDraft,
	});
	const { isText, textKey, splitTitle, openTop } = useTextCells(model, snippets, {
		focusCell,
		startDraft,
		openGhost,
	});

	useEffect(() => {
		if (!entryRef) return;
		entryRef.current = editable ? enterTop : null;
		return () => {
			entryRef.current = null;
		};
	}, [entryRef, editable, enterTop]);

	useEffect(() => {
		if (!splitRef) return;
		splitRef.current = editable ? splitTitle : null;
		return () => {
			splitRef.current = null;
		};
	}, [splitRef, editable, splitTitle]);

	useEffect(() => {
		if (!openRef) return;
		openRef.current = editable ? openTop : null;
		return () => {
			openRef.current = null;
		};
	}, [openRef, editable, openTop]);

	useEffect(() => {
		if (!selectRef) return;
		selectRef.current = startBox;
		return () => {
			selectRef.current = null;
		};
	}, [selectRef, startBox]);

	// -- Where the caret actually is ------------------------------------------
	//
	// `editor.focus` is an intent and is consumed the instant a cell honours
	// it, so it cannot answer "which cell is the caret in" -- which is what
	// the gutter's focus rail needs. Focus events bubble (focusin/focusout), so
	// one listener on the plane root reports the standing fact for every editor
	// inside it, including ones we do not own (Monaco, a cell's refs).

	const onPlaneFocus = useCallback(
		(e: React.FocusEvent) => {
			const host = (e.target as HTMLElement).closest?.("[data-cell]");
			const id = host?.getAttribute("data-cell") ?? null;
			patch((ed) => (ed.focused === id ? {} : { focused: id }));
		},
		[patch],
	);

	const onPlaneBlur = useCallback(
		(e: React.FocusEvent) => {
			// Focus moving between two editors inside the plane fires blur
			// before focus; only a departure that leaves the plane clears it.
			const next = e.relatedTarget as Node | null;
			if (next && rootRef.current?.contains(next)) return;
			patch((ed) => (ed.focused === null ? {} : { focused: null }));
		},
		[patch],
	);

	// -- Render ---------------------------------------------------------------

	const setEl = useCallback((id: string, el: HTMLElement | null) => {
		if (el) elRefs.current.set(id, el);
		else elRefs.current.delete(id);
	}, []);

	// A read-only plane has no open source, whatever the editor state still
	// remembers from before the switch flipped. It keeps its selection: a box
	// selects there too, to copy.
	const selectedIds = editor.selected;
	const editingIds = editable ? editor.editing : NONE;
	const drag = editor.drag;
	const lastId = cells.length ? cells[cells.length - 1].id : null;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the plane is the keyboard owner in cell-selection mode
		<div
			ref={rootRef}
			tabIndex={-1}
			onKeyDown={onCellKeys}
			onFocus={onPlaneFocus}
			onBlur={onPlaneBlur}
			className={`${docColumn(wide, compact)} outline-none`}
		>
			{/* A draft at the top: Enter in the title, or the first line of an
			    empty plane. It stays above its cell once that arrives. */}
			{editable && draft && draft.after === null ? (
				<div className={docRow}>
					<Draft boxRef={boxRef} text={draft.text} caret={draft.caret} />
				</div>
			) : null}
			{editable && editor.ghost?.after === null ? (
				<div className={docRow}>
					<Ghost {...ghostProps(null, true)} />
				</div>
			) : null}
			{cells.map((cell, i) => {
				const selected = selectedIds.includes(cell.id);
				const editing = editingIds.includes(cell.id);
				return (
					<Fragment key={cell.id}>
						<Cell
							cell={cell}
							uiPath={cellUiPath(viewerPath, cell.id)}
							editable={editable}
							hidden={draft?.id === cell.id}
							selected={selected}
							selectedStrong={selected && selectedIds.length > 1}
							focused={editor.focused === cell.id}
							editing={editing}
							focusReq={editor.focus?.cellId === cell.id ? editor.focus : null}
							dragging={drag?.id === cell.id}
							dropAbove={drag != null && drag.at === i}
							setEl={(el) => setEl(cell.id, el)}
							onPointerIn={() => {
								if (editor.selected.length > 0) patch({ selected: [], anchor: null });
							}}
							onSetEditing={(on) => setEditing(cell.id, on)}
							onDrag={(e, onClick) => startDrag(e, cell.id, onClick)}
							onDelete={() => deleteCells([cell.id])}
							onTextKey={editable && isText(cell) ? (e) => textKey(e, cell.id) : undefined}
							// Make room, do not make a cell. What goes here is
							// whatever gets picked next.
							onPlus={() => openGhost(cell.id, null)}
							onSelect={() => selectCell(cell.id)}
							onFocusConsumed={() => patch({ focus: null })}
							onCommit={(src) => commitSource(cell.id, src)}
							onExit={(dir, column) => step(cell.id, dir, column)}
						/>
						{/* A draft stays where its ghost was, which is right above its
						    cell once that arrives. */}
						{editable && draft?.after === cell.id ? (
							<div className={docRow}>
								<Draft boxRef={boxRef} text={draft.text} caret={draft.caret} />
							</div>
						) : null}
						{editable && editor.ghost?.after === cell.id ? (
							<div className={docRow}>
								<Ghost {...ghostProps(cell.id, true)} />
							</div>
						) : null}
					</Fragment>
				);
			})}
			{drag && drag.at >= cells.length ? (
				<div className={docRow}>
					<div className={`${docContentTrack} relative h-0`}>
						<span className={docDropIndicator} />
					</div>
				</div>
			) : null}

			{/* The permanent ghost is how an empty Plane is written on without
			    hunting for a control, so it goes with the rest of the authoring
			    affordances. */}
			{editable ? (
				<div className={docRow}>
					<Ghost {...ghostProps(lastId, false)} hinted={cells.length === 0 && !draft} />
				</div>
			) : null}
			{/* The run-off under the last cell is the plane's compact setting, not
			    its editable one. Clicking it aims at the ghost when there is one.
			    It spans all three tracks: the whole width under the plane is
			    somewhere to click. */}
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

			{box ? <div className={docBoxSelect} style={box} /> : null}

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
