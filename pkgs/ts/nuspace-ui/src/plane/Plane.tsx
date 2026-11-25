// A plane: one Plane's cells, as a document you write in.
//
// `editable` is the plane's own setting and the thing here that branches on
// it: with it you get the insert affordances, the drag handle, a source you
// can edit and the keyboard. Without it the same cells render their output
// and keep a reduced gutter: copy the id, and read the source. `width` is the
// plane's width setting, how wide its grid runs at most.
//
// Everything structural lives in this directory and nowhere else: ordering,
// keyboard, selection, focus, the input lines and the slash menu, drag
// reorder, cell lifecycle. No library supplies any of it, because no library
// knows what a running Nu cell is. This file is the composition root: it
// builds the plane's one API (./api.ts) out of the concern folders, renders
// the cells, and routes intents (./intents.ts):
//
//   structure/   create, the one remove, reorder
//   layout/      how the cells are drawn (rows, strips), and dragging
//                them within the pane, to another pane or a sidebar row
//   selection/   the cell-selection keyboard, box and range select
//   focus/       focus requests, navigation, the cells' documents
//   input/       the input lines and the `/` menu
//   cell/        one cell: its row, gutter, program, source editor, the
//                plane picker its menu opens to move it (./transfer.ts)
//   sugar/       the sets of rules bound to a class, the only class-aware code
//
// The core is kind-blind and works with no sugar at all: the input line
// opens the menu, cells are created, selected, moved and deleted, and the
// caret travels as it always has.
//
// The cells draw from the plane's layout (./layout/model.ts): a cell alone
// on its row, or a strip of columns side by side at their shares (./layout/
// Strip.tsx). A row has no id: React keys it, and a drag reads it, by its
// first cell. Every row is the same `Cell` either way. The core reads the
// cells in the layout's reading order, so the caret and the selection walk
// what is drawn. A cell's markdown editor is found through
// the kit by the cell's address and talks back only in intents, so
// nothing here reads an editor's DOM or moves its caret from outside.

import type { Path } from "@nustackdev/ui-core";
import { markdownAt, pathKey } from "@nustackdev/ui-kit";
import type * as React from "react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
	docBoxSelect,
	docColumn,
	docContentTrack,
	docDropIndicator,
	docRow,
	docTail,
	type PlaneWidth,
} from "../design";
import { clearPaneTargets, usePaneTargets } from "../pane/state";
import { deletedCells } from "../refs/toast";
import type { FocusRequest, PlaneApi, PlaneHandle, PlaneModel } from "./api";
import { cellUiPath } from "./cell/address";
import { Cell } from "./cell/Cell";
import { TransferPicker } from "./cell/TransferPicker";
import { keyboardBusy } from "./focus/focusable";
import { useCaret } from "./focus/useCaret";
import { useEditors } from "./focus/useEditors";
import { useFocusRouting } from "./focus/useFocusRouting";
import { Ghost } from "./input/Ghost";
import { SlashMenu } from "./input/SlashMenu";
import { useGhosts } from "./input/useGhosts";
import { useSlash } from "./input/useSlash";
import { defaultSpecOf, type InputIntent, inputHint, type Router, router } from "./intents";
import {
	LAYOUT_PLANE,
	LAYOUT_TAKES,
	type Mark,
	startDrag,
	useDragged,
	useDragMark,
} from "./layout/drag";
import { inReadingOrder, plainLayout, resized, rowKey } from "./layout/model";
import { Strip } from "./layout/Strip";
import type { Notify } from "./ops";
import { useBoxSelect } from "./selection/useBoxSelect";
import { useCellKeys } from "./selection/useCellKeys";
import { type EditorPatch, type InputLine, patchEditor, readEditor, useEditorState } from "./state";
import { useStructure } from "./structure/useStructure";
import { sugars as SUGARS, type Sugar } from "./sugar";
import { targetsFrom } from "./transfer";
import { type ActivePlane, type CellSpec, isBad } from "./types";

const NO_CELL_SPECS: CellSpec[] = [];

export function Plane({
	viewerPath,
	panePath,
	plane,
	cellSpecs = NO_CELL_SPECS,
	editable,
	width,
	notify,
	handleRef,
	onTitle,
	focused = false,
	sugars = SUGARS,
}: {
	/** The ViewerRef node, which roots every cell's refs. */
	viewerPath: Path;
	/** The pane's own PaneRef node, which holds this plane's editor state. */
	panePath: Path;
	plane: ActivePlane;
	/** The registered Cells, in order: the `/` menu's rows. */
	cellSpecs?: CellSpec[];
	/** The plane's setting. False draws the same cells, output only. */
	editable: boolean;
	/** The plane's width setting: how wide its grid runs, at most. */
	width: PlaneWidth;
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
	const planeId = plane.plane_id;
	const layout = useMemo(() => plane.layout ?? plainLayout(plane.cells), [plane]);
	// The layout's reading order: what the caret, the selection and the keys walk.
	const cells = useMemo(() => inReadingOrder(plane.cells, layout), [plane.cells, layout]);
	// Per pane: two planes side by side never share a selection or a ghost.
	const editor = useEditorState(panePath);
	const viewerKey = pathKey(viewerPath);
	const paneKey = pathKey(panePath);

	const rootRef = useRef<HTMLDivElement | null>(null);
	const elRefs = useRef(new Map<string, HTMLElement>());
	const endGhost = useRef<HTMLInputElement | null>(null);
	const plusGhost = useRef<HTMLInputElement | null>(null);

	const index = useCallback((id: string) => cells.findIndex((b) => b.id === id), [cells]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const patch = useCallback((p: EditorPatch) => patchEditor(panePath, p), [paneKey]);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const read = useCallback(() => readEditor(panePath), [paneKey]);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const editorOf = useCallback(
		(id: string) => markdownAt(cellUiPath(viewerPath, id))?.handle ?? null,
		[viewerKey],
	);

	const model: PlaneModel = {
		planeId,
		cells,
		layout,
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
	// A cell's grip: a drag within the pane, to another, or to
	// a sidebar row (./layout/drag.ts). A cell dragged is the one selected.
	const dragCell = (e: React.PointerEvent, id: string, onClick?: () => void) =>
		startDrag(
			e,
			{ kind: "cell", plane: planeId, cell: id },
			{ viewerPath, notify, onClick, onStart: () => patch({ selected: [id], anchor: id }) },
		);
	const mark = useDragMark(planeId);
	const dragged = useDragged();
	const { box, startBox, startRange } = useBoxSelect(model);
	const { slash, pickSlash, slashKey, moveSlash } = useSlash(model, cellSpecs, {
		create,
		withdraw,
	});

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

	// The cell whose "Move to plane" picker is open, null for none. Opening
	// asks for the list afresh; it loads until the answer lands. A pick sends
	// the op and nothing else: the cell leaves when the cells ship again.
	const [transferring, setTransferring] = useState<string | null>(null);
	const answered = usePaneTargets(panePath);
	const targets = answered ? targetsFrom(answered, planeId) : null;
	const openTransfer = (id: string) => {
		clearPaneTargets(panePath);
		notify("cell.targets", {});
		setTransferring(id);
	};

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
	const lastId = cells.length ? cells[cells.length - 1].id : null;

	// One cell's row, and the input line under it when one is open there.
	const byId = new Map(cells.map((c) => [c.id, c]));
	const renderCell = (id: string, alone?: boolean) => {
		const cell = byId.get(id);
		if (!cell) return null;
		const selected = selectedIds.includes(cell.id);
		const editing = editingIds.includes(cell.id);
		const source = editor.requests.find((r) => r.cellId === cell.id && r.to === "source") ?? null;
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
			<>
				<Cell
					cell={cell}
					uiPath={cellUiPath(viewerPath, cell.id)}
					editable={editable}
					hidden={fed || editor.ghost?.replace === cell.id || editor.leaving.includes(cell.id)}
					selected={selected}
					selectedStrong={selected && multi}
					editing={editing}
					focusReq={source}
					dragging={dragged === cell.id}
					drop={markOn(mark, cell.id)}
					alone={alone}
					setEl={(el) => setEl(cell.id, el)}
					onPointerIn={() => {
						if (editor.selected.length > 0) patch({ selected: [], anchor: null });
					}}
					onSetEditing={(on) => setEditing(cell.id, on)}
					onDrag={(e, onClick) => dragCell(e, cell.id, onClick)}
					onDelete={() => {
						remove([cell.id]);
						deletedCells([cell.id]);
					}}
					onRestart={() => notify("cell.restart", { cell_id: cell.id })}
					onTransfer={() => openTransfer(cell.id)}
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
			</>
		);
	};

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the plane is the keyboard owner in cell-selection mode
		<div
			ref={rootRef}
			tabIndex={-1}
			onKeyDown={onCellKeys}
			className={`${docColumn(width)} outline-none`}
			{...{ [LAYOUT_PLANE]: planeId }}
			{...(editable && !plane.system ? { [LAYOUT_TAKES]: "" } : {})}
		>
			{editable && editor.ghost?.after === null ? (
				<div className={docRow}>
					<Ghost {...ghostProps(null, true)} />
				</div>
			) : null}
			{layout.map((row) =>
				row.kind === "cell" ? (
					<Fragment key={row.cell}>{renderCell(row.cell, true)}</Fragment>
				) : (
					<Strip
						key={rowKey(row)}
						row={row}
						editable={editable}
						dropAbove={mark?.kind === "strip" && mark.row === rowKey(row)}
						renderCell={(id) => renderCell(id)}
						onResize={(shares) => {
							const rows = resized(layout, rowKey(row), shares);
							if (rows) notify("layout.set", { rows });
						}}
					/>
				),
			)}
			{mark?.kind === "end" ? (
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
			{/* The run-off under the last cell, on every plane, editable or not.
			    Clicking it aims at the ghost when there is one. It spans all three
			    tracks: the whole width under the plane is somewhere to click. */}
			{/* biome-ignore lint/a11y/noStaticElementInteractions: the run-off under a document is a click target, not a control -- the keyboard reaches the same ghost by arrowing down */}
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

			<TransferPicker
				open={transferring !== null}
				targets={targets}
				onPick={(to) => {
					if (transferring) notify("cell.transfer", { cell_id: transferring, plane_id: to });
				}}
				onClose={(picked) => {
					// Dismissed, the cell stays selected, so its keys work straight after.
					if (!picked && transferring) select([transferring]);
					setTransferring(null);
				}}
			/>
		</div>
	);
}

/** The part of a drag's mark that is drawn on cell `id`, null for none. */
function markOn(mark: Mark | null, id: string): Mark | null {
	return mark && "cell" in mark && mark.cell === id ? mark : null;
}
