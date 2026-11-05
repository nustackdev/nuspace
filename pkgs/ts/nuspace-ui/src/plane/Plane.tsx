// A plane: one Plane's cells, as a document you write in.
//
// `editable` is the plane's own setting and the thing here that branches on
// it: with it you get the insert affordances, the drag handle, a source you
// can edit and the keyboard. Without it the same cells render their output
// and keep a reduced gutter: copy the id, and read the source. `wide` is the full-width setting.
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
//   sugar/               the text sugar, a closed list (sugar/useTextSugar.ts)
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
import { Ghost } from "./Ghost";
import type { PlaneModel } from "./model";
import type { Notify } from "./ops";
import { SlashMenu } from "./SlashMenu";
import { type EditorPatch, patchEditor, useEditorState } from "./state";
import { Draft, useDraft } from "./sugar/Draft";
import { cellSurface } from "./sugar/surface";
import { NEW_CELL_HINT, useTextSugar, WRITE_HINT } from "./sugar/useTextSugar";
import { type ActivePlane, type CellSpec, hasText } from "./types";
import { useBoxSelect } from "./useBoxSelect";
import { useCellDrag } from "./useCellDrag";
import { useCellKeys } from "./useCellKeys";
import { useFocusRouting } from "./useFocusRouting";
import { useGhosts } from "./useGhosts";
import { useSlash } from "./useSlash";
import { useStructure } from "./useStructure";

const NO_CELL_SPECS: CellSpec[] = [];

export function Plane({
	viewerPath,
	plane,
	cellSpecs = NO_CELL_SPECS,
	editable,
	wide,
	compact,
	notify,
	entryRef,
	openRef,
	titleEndRef,
	selectRef,
}: {
	/** The ViewerRef node, which holds every pane's editor state and roots
	 *  every cell's refs. */
	viewerPath: Path;
	plane: ActivePlane;
	/** The registered Cells, in order: the `/` menu's rows. */
	cellSpecs?: CellSpec[];
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
	/** Set to "start an empty text cell at the top", from Enter in the title
	 *  above. Null while there is no such thing to start. */
	openRef?: React.RefObject<(() => boolean) | null>;
	/** Set by the title: the caret to its end, where Backspace in an empty
	 *  top text cell goes. */
	titleEndRef?: React.RefObject<(() => void) | null>;
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
	const { box, startBox, startSpill } = useBoxSelect(model);
	const { slash, pickSlash, slashKey, moveSlash } = useSlash(model, cellSpecs, createAfter);
	const { draft, boxRef, startDraft } = useDraft(model, viewerPath, cellSpecs, createAfter);
	const { ghostProps, openGhost, standIn, putAway } = useGhosts(model, {
		focusCell,
		slashKey,
		startDraft,
		hint: hasText(cellSpecs) ? WRITE_HINT : undefined,
	});
	const { isText, textKey, titleEnter, titleDown } = useTextSugar(model, cellSpecs, {
		focusCell,
		startDraft,
		openGhost,
		standIn,
		titleEnd: titleEndRef,
	});

	useEffect(() => {
		if (!entryRef) return;
		entryRef.current = editable ? () => titleDown() || enterTop() : null;
		return () => {
			entryRef.current = null;
		};
	}, [entryRef, editable, enterTop, titleDown]);

	useEffect(() => {
		if (!openRef) return;
		openRef.current = editable ? titleEnter : null;
		return () => {
			openRef.current = null;
		};
	}, [openRef, editable, titleEnter]);

	useEffect(() => {
		if (!selectRef) return;
		selectRef.current = startBox;
		return () => {
			selectRef.current = null;
		};
	}, [selectRef, startBox]);

	// -- Render ---------------------------------------------------------------

	const setEl = useCallback((id: string, el: HTMLElement | null) => {
		if (el) elRefs.current.set(id, el);
		else elRefs.current.delete(id);
	}, []);

	// A read-only plane keeps its selection (a box selects there too, to copy)
	// and its open sources, which show read-only.
	const selectedIds = editor.selected;
	const multi = selectedIds.length > 1;
	const editingIds = editor.editing;
	const drag = editor.drag;
	const lastId = cells.length ? cells[cells.length - 1].id : null;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the plane is the keyboard owner in cell-selection mode
		<div
			ref={rootRef}
			tabIndex={-1}
			onKeyDown={onCellKeys}
			className={`${docColumn(wide, compact)} outline-none`}
			// The text sugar's hint, drawn by CSS on a text cell's empty last line.
			style={{ "--sugar-new-cell": JSON.stringify(NEW_CELL_HINT) } as React.CSSProperties}
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
							hidden={
								draft?.id === cell.id ||
								editor.ghost?.replace === cell.id ||
								editor.leaving.includes(cell.id)
							}
							selected={selected}
							selectedStrong={selected && multi}
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
							onDelete={() => {
								// The cell above takes the selection, and the keyboard with it.
								deleteCells([cell.id]);
								rootRef.current?.focus({ preventScroll: true });
							}}
							onRestart={() => notify("cell.restart", { cell_id: cell.id })}
							onTextKey={editable && isText(cell) ? (e) => textKey(e, cell.id) : undefined}
							onTextPress={
								editable && isText(cell)
									? (e) => {
											// Only a press in the text itself: the grip has its own drag.
											if (cellSurface(rootRef.current, cell.id)?.contains(e.target as Node))
												startSpill(e, cell.id);
										}
									: undefined
							}
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
			{/* Not while a stand-in holds the last cell's place: one line there, not two. */}
			{editable && !(lastId && editor.ghost?.replace === lastId) ? (
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
					query={slash.query}
					cellSpecs={cellSpecs}
					index={slash.index}
					anchor={slash.anchor}
					onPick={pickSlash}
					onMove={moveSlash}
					onClose={putAway}
				/>
			) : null}
		</div>
	);
}
