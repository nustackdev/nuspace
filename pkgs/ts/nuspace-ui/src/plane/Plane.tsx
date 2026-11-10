// A plane: one Plane's cells, as a document you write in.
//
// `editable` is the plane's own setting and the thing here that branches on
// it: with it you get the insert affordances, the drag handle, a source you
// can edit and the keyboard. Without it the same cells render their output
// and keep a reduced gutter: copy the id, and read the source. `wide` is the full-width setting.
//
// Everything structural lives in this directory and nowhere else: ordering,
// keyboard, selection, focus, the input lines and the slash menu, drag
// reorder, cell lifecycle. No library supplies any of it, because no library
// knows what a running Nu cell is. This file is the composition root: it
// builds the plane's one API (./api.ts) out of the concern folders, renders
// the cells, and routes intents (./intents.ts):
//
//   structure/   create, the one remove, reorder, drag
//   selection/   the cell-selection keyboard, box and range select
//   focus/       focus requests, navigation, the cells' documents
//   input/       the input lines and the `/` menu
//   cell/        one cell: its row, gutter, program, source editor
//   sugar/       the sets of rules bound to a class, the only class-aware code
//
// The core is kind-blind and works with no sugar at all: the input line
// opens the menu, cells are created, selected, moved and deleted, and the
// caret travels as it always has. A cell's markdown editor is found through
// the kit by the cell's address and talks back only in intents, so
// nothing here reads an editor's DOM or moves its caret from outside.

import type { Path } from "@nustackdev/ui-core";
import { markdownAt, pathKey } from "@nustackdev/ui-kit";
import type * as React from "react";
import { Fragment, useCallback, useEffect, useRef } from "react";
import {
	docBoxSelect,
	docColumn,
	docContentTrack,
	docDropIndicator,
	docRow,
	docTail,
} from "../design";
import type { FocusRequest, PlaneApi, PlaneHandle, PlaneModel } from "./api";
import { cellUiPath } from "./cell/address";
import { Cell } from "./cell/Cell";
import { keyboardBusy } from "./focus/focusable";
import { useCaret } from "./focus/useCaret";
import { useEditors } from "./focus/useEditors";
import { useFocusRouting } from "./focus/useFocusRouting";
import { Ghost } from "./input/Ghost";
import { SlashMenu } from "./input/SlashMenu";
import { useGhosts } from "./input/useGhosts";
import { useSlash } from "./input/useSlash";
import { defaultSpecOf, type InputIntent, inputHint, type Router, router } from "./intents";
import type { Notify } from "./ops";
import { useBoxSelect } from "./selection/useBoxSelect";
import { useCellKeys } from "./selection/useCellKeys";
import { type EditorPatch, type InputLine, patchEditor, readEditor, useEditorState } from "./state";
import { useCellDrag } from "./structure/useCellDrag";
import { useStructure } from "./structure/useStructure";
import { sugars as SUGARS, type Sugar } from "./sugar";
import { type ActivePlane, type CellSpec, isBad } from "./types";

const NO_CELL_SPECS: CellSpec[] = [];

export function Plane({
	viewerPath,
	plane,
	cellSpecs = NO_CELL_SPECS,
	editable,
	wide,
	compact,
	notify,
	handleRef,
	onTitle,
	focused = false,
	sugars = SUGARS,
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
	/** Filled with what the pane above holds of this plane (./api.ts). */
	handleRef?: React.RefObject<PlaneHandle | null>;
	/** The caret into the title above, at its start or end. Left out for a
	 *  host with no title, and the plane takes the keyboard instead. */
	onTitle?: (at: "start" | "end") => void;
	/** Its pane is the focused one as it opens: an empty plane takes the caret. */
	focused?: boolean;
	/** The sugar sets. The registry's (./sugar) unless a test hands its own. */
	sugars?: readonly Sugar[];
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
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const read = useCallback(() => readEditor(viewerPath, planeId), [viewerKey, planeId]);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const editorOf = useCallback(
		(id: string) => markdownAt(cellUiPath(viewerPath, id))?.handle ?? null,
		[viewerKey],
	);

	const model: PlaneModel = {
		planeId,
		cells,
		editor,
		patch,
		read,
		notify,
		index,
		editorOf,
		rootRef,
		elRefs,
		endGhost,
		plusGhost,
	};

	const {
		request,
		drop,
		release,
		registered,
		abandon,
		wake,
		focus,
		select,
		focusCell,
		step,
		beside,
		enterCell,
		setEditing,
		enterTop,
	} = useFocusRouting(model, { onTitle });
	const { commitSource, create, remove, withdraw, reorder, moveSelected } = useStructure(model, {
		request,
		drop,
		focus,
		select,
	});
	const onCellKeys = useCellKeys(model, editable, {
		focusCell,
		enterCell,
		remove,
		moveSelected,
		release,
	});
	const startDrag = useCellDrag(model, reorder);
	const { box, startBox, startRange } = useBoxSelect(model);
	const { slash, pickSlash, slashKey, moveSlash } = useSlash(model, cellSpecs, { create, remove });

	// Intents are heard at event time, from the input lines and the cells'
	// markdown editors: they reach this render's routing through a ref.
	const routing = useRef<Router | null>(null);
	const line = useRef<((l: InputLine) => PlaneApi) | null>(null);
	const route = useCallback((after: string | null, i: InputIntent, l: InputLine) => {
		const lineApi = line.current?.(l);
		return lineApi ? (routing.current?.input(after, i, lineApi) ?? false) : false;
	}, []);

	const { ghostProps, openInput, standIn, putAway } = useGhosts(model, {
		focusCell,
		focus,
		select,
		drop,
		wake,
		slashKey,
		route,
		hint: editable ? inputHint(sugars, cellSpecs) : undefined,
	});

	const api: PlaneApi = {
		cells,
		index,
		editor: editorOf,
		defaultSpec: (cls) => defaultSpecOf(cellSpecs, cls),
		beside,
		create: (at, spec, want) => create(at, spec, want),
		remove,
		withdraw,
		reorder,
		focus: (target) => focus(target),
		select,
		openInput,
		standIn,
	};
	// What a sugar gets for an intent from an input line: the same api, with
	// a create that asks for focus fed by that line until it lands, so the
	// keys typed meanwhile stay in the line and go along with the request,
	// and a focus that takes a summoned line away as the caret leaves it.
	line.current = (l) => ({
		...api,
		create: (at, spec, want?: FocusRequest) => create(at, spec, want, want ? l : undefined),
		focus: (target) => {
			if (l === "summoned") patch({ ghost: null });
			focus(target);
		},
	});
	routing.current = router({
		sugars,
		cellSpecs,
		editable,
		cells,
		api,
		core: { step: (c, dir) => step(c, dir), enterTop },
	});

	const { caret } = useCaret(model, { sugars, editable, focus });

	useEditors(viewerPath, cells, {
		intent: (cell, i) => routing.current?.editor(cell, i) ?? false,
		registered,
		vanished: abandon,
	});

	// A cell that ships saying it draws nothing, or whose program died or
	// stopped, will never draw a markdown editor: what waits for one is let go,
	// and text an input line fed it goes back into the line.
	useEffect(() => {
		for (const c of cells) {
			const over = c.draws === false || isBad(c.status.state) || c.status.state === "stopped";
			if (!over || editorOf(c.id)) continue;
			if (editor.requests.some((r) => r.cellId === c.id && r.to === "document")) abandon(c.id);
		}
	}, [cells, editor.requests, editorOf, abandon]);

	// What the pane holds: the title's intents, and a press anywhere in it.
	const pressRef = useRef(startBox);
	pressRef.current = startBox;
	useEffect(() => {
		if (!handleRef) return;
		handleRef.current = {
			title: (i) => routing.current?.title(i) ?? false,
			press: (e) => {
				release();
				pressRef.current(e);
			},
		};
		return () => {
			handleRef.current = null;
		};
	}, [handleRef, release]);

	// An empty plane opens with the caret in its end line: there is nothing
	// else on it to write in, so a new plane is typed into at once. Once, as
	// it opens, and only in the focused pane. One with cells keeps the
	// keyboard where it was, and so does a dialog or a field being typed in.
	// biome-ignore lint/correctness/useExhaustiveDependencies: on open, never again
	useEffect(() => {
		if (focused && cells.length === 0 && !keyboardBusy()) endGhost.current?.focus();
	}, []);

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
		>
			{editable && editor.ghost?.after === null ? (
				<div className={docRow}>
					<Ghost {...ghostProps(null, true)} />
				</div>
			) : null}
			{cells.map((cell, i) => {
				const selected = selectedIds.includes(cell.id);
				const editing = editingIds.includes(cell.id);
				const source =
					editor.requests.find((r) => r.cellId === cell.id && r.to === "source") ?? null;
				// An input line is showing what this cell is waiting to take, or
				// another cell still holds the markdown it will be handed (a
				// split's tail), so the cell stays out of sight until it has it
				// rather than flash empty. One that died shows its error instead,
				// and one that will never take it is let go (the exits above).
				// An editor drawn but not yet open for editing is still waiting:
				// the cell shows in the render that readies its request, and the
				// text lands in it before that render paints (./focus/useFocusRouting.ts),
				// so the line hands over to the cell in place, in one frame. Until
				// then the text stays in sight where it is, in the line or in the
				// cell it is cut from, and Escape in the line lets it go.
				const fed =
					!cell.status.error &&
					editor.requests.some((r) => r.cellId === cell.id && (r.line || r.markdown) && !r.ready);
				return (
					<Fragment key={cell.id}>
						<Cell
							cell={cell}
							uiPath={cellUiPath(viewerPath, cell.id)}
							editable={editable}
							hidden={fed || editor.ghost?.replace === cell.id || editor.leaving.includes(cell.id)}
							selected={selected}
							selectedStrong={selected && multi}
							editing={editing}
							focusReq={source}
							dragging={drag?.id === cell.id}
							dropAbove={drag != null && drag.at === i}
							setEl={(el) => setEl(cell.id, el)}
							onPointerIn={() => {
								if (editor.selected.length > 0) patch({ selected: [], anchor: null });
							}}
							onSetEditing={(on) => setEditing(cell.id, on)}
							onDrag={(e, onClick) => startDrag(e, cell.id, onClick)}
							onDelete={() => remove([cell.id])}
							onRestart={() => notify("cell.restart", { cell_id: cell.id })}
							// A text selection dragged out of what a document draws
							// becomes a cell selection. The grip has its own drag.
							onPress={
								editable
									? (e) => {
											const inUi = (e.target as Element).closest?.("[data-cell-ui]");
											if (inUi && editorOf(cell.id)) startRange(e, cell.id);
										}
									: undefined
							}
							// Make room, do not make a cell. What goes here is
							// whatever gets picked next.
							onPlus={() => openInput(cell.id)}
							onSelect={() => select([cell.id])}
							// Drawn, and its markdown editor (if it has one) mounted in the same
							// commit, before this hears it: none, open for editing or
							// not, means none is coming. One mounted read-only waits.
							onDrawn={() => {
								if (markdownAt(cellUiPath(viewerPath, cell.id)) === null) {
									abandon(cell.id);
								}
							}}
							onFocusConsumed={() => {
								if (source) drop((r) => r.id === source.id);
							}}
							onCommit={(src) => commitSource(cell.id, src)}
							onKey={
								editable
									? (key) =>
											key === ""
												? notify("cell.remove_key", { cell_id: cell.id })
												: notify("cell.key", { cell_id: cell.id, key })
									: undefined
							}
							onExit={(dir, column) => step(cell.id, dir, column)}
							onCaret={(where, nowhere) => caret(cell, where, nowhere)}
						/>
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
					<Ghost {...ghostProps(lastId, false)} hinted={cells.length === 0} />
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
