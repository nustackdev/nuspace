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
//   useSlash.ts          the `/` menu's behaviour (SlashMenu.tsx draws it)
//   useGhosts.ts         the ghost inputs' wiring (Ghost.tsx draws one)
//   cell/               one cell: its row, gutter, program, source editor

import type { Path } from "@nustackdev/ui-core";
import { pathKey } from "@nustackdev/ui-kit";
import { Fragment, useCallback, useRef } from "react";
import { docColumn, docDropIndicator, docTail } from "../design";
import { cellUiPath } from "./cell/address";
import { Cell } from "./cell/Cell";
import { Ghost } from "./Ghost";
import type { PlaneModel } from "./model";
import type { Notify } from "./ops";
import { SlashMenu } from "./SlashMenu";
import { type EditorPatch, patchEditor, useEditorState } from "./state";
import type { ActivePlane, SlashSnippet } from "./types";
import { useCellDrag } from "./useCellDrag";
import { useCellKeys } from "./useCellKeys";
import { useFocusRouting } from "./useFocusRouting";
import { useGhosts } from "./useGhosts";
import { useSlash } from "./useSlash";
import { useStructure } from "./useStructure";

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

	const { focusCell, step, enterCell, setEditing, selectCell } = useFocusRouting(model);
	const { commitSource, createAfter, deleteCells, moveSelected } = useStructure(model);
	const onCellKeys = useCellKeys(model, { focusCell, enterCell, deleteCells, moveSelected });
	const startDrag = useCellDrag(model);
	const { slash, slashItems, pickSlash, slashKey, moveSlash } = useSlash(
		model,
		snippets,
		createAfter,
	);
	const ghostProps = useGhosts(model, { focusCell, createAfter, slashKey });

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

	// A read-only plane has no selection and no open source, whatever the
	// editor state still remembers from before the switch flipped.
	const selectedIds = editable ? editor.selected : NONE;
	const editingIds = editable ? editor.editing : NONE;
	const drag = editor.drag;
	const lastId = cells.length ? cells[cells.length - 1].id : null;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the plane is the keyboard owner in cell-selection mode
		<div
			ref={rootRef}
			tabIndex={-1}
			onKeyDown={editable ? onCellKeys : undefined}
			onFocus={onPlaneFocus}
			onBlur={onPlaneBlur}
			className={`${docColumn(wide, compact)} outline-none`}
		>
			{cells.map((cell, i) => {
				const selected = selectedIds.includes(cell.id);
				const editing = editingIds.includes(cell.id);
				return (
					<Fragment key={cell.id}>
						<Cell
							cell={cell}
							uiPath={cellUiPath(viewerPath, cell.id)}
							editable={editable}
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
							onDrag={(e) => startDrag(e, cell.id)}
							onPlus={() => {
								// Make room, do not make a cell. What goes here is
								// whatever gets picked next.
								//
								// On the last cell there is already a ghost directly
								// below -- the permanent one -- so summoning a second
								// would put two identical empty lines next to each
								// other and make vertical travel pick between them.
								if (cell.id === lastId) {
									patch({ ghost: null, slash: null });
									endGhost.current?.focus();
									return;
								}
								patch({
									ghost: cell.id,
									slash: null,
									selected: [],
									anchor: null,
									focus: null,
								});
							}}
							onSelect={() => selectCell(cell.id)}
							onFocusConsumed={() => patch({ focus: null })}
							onCommit={(src) => commitSource(cell.id, src)}
							onExit={(dir, column) => step(cell.id, dir, column)}
						/>
						{editable && editor.ghost === cell.id ? <Ghost {...ghostProps(cell.id, true)} /> : null}
					</Fragment>
				);
			})}
			{drag && drag.at >= cells.length ? (
				<div className="relative h-0">
					<span className={docDropIndicator} />
				</div>
			) : null}

			{/* The permanent ghost is how an empty Plane is written on without
			    hunting for a control, so it goes with the rest of the authoring
			    affordances. */}
			{editable ? <Ghost {...ghostProps(lastId, false)} /> : null}
			{/* The run-off under the last cell is the plane's compact setting, not
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
