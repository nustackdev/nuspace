// One cell on a plane: its row, its controls, and the program inside. The row
// is a plane grid row (see ../../design/document.ts): the cell's box in the
// content track, its controls in the gutters either side (./Gutter.tsx).
//
// There is no cell kind to branch on. Each cell renders the subtree at its
// own address -- the ui refs its program mounted, which arrive as ordinary
// nodes -- through `NodeView`, inside the same `docCell`, with the same
// controls: add and drag with the cell's menu, and the source. Every cell
// compiles, runs, is supervised and reports status identically. See
// ./address.ts for where that address is.
//
// `editable` is the plane's setting. Off, the cell is read-only: its menu
// cannot delete, there is nothing to add or drag, and the source opens in a
// read-only editor that never saves.
//
// The controls are always mounted. Whether they show is the row's own CSS
// (`docGutterLane`): `data-selected` marks it as the one selected cell.
//
// A text cell's keys (../useTextCells.ts) are caught on the row, before the
// editor inside it sees them.

import type { Path } from "@nustackdev/ui-core";
import type * as React from "react";
import { docCell, docCellRow, docDropIndicator } from "../../design";
import type { FocusReq } from "../state";
import type { Cell as CellValue, ExitDir } from "../types";
import { LeftGutter, RightGutter } from "./Gutter";
import { ProgramCell } from "./Program";

export function Cell({
	cell,
	uiPath,
	editable,
	hidden,
	selected,
	selectedStrong,
	editing,
	focusReq,
	dragging,
	dropAbove,
	setEl,
	onPointerIn,
	onSetEditing,
	onDrag,
	onPlus,
	onDelete,
	onTextKey,
	onSelect,
	onFocusConsumed,
	onCommit,
	onExit,
}: {
	cell: CellValue;
	/** Where this cell's own refs live in the tree. */
	uiPath: Path;
	editable: boolean;
	/** Drawn but not shown: a draft stands in for it (../Draft.tsx). */
	hidden?: boolean;
	selected: boolean;
	/** Part of a multi-cell selection. */
	selectedStrong: boolean;
	/** Source open. */
	editing: boolean;
	focusReq: FocusReq | null;
	dragging: boolean;
	/** A drag would drop right above this cell. */
	dropAbove: boolean;
	setEl: (el: HTMLElement | null) => void;
	/** A plain primary-button press landed inside the cell. */
	onPointerIn: () => void;
	onSetEditing: (on: boolean) => void;
	onDrag: (e: React.PointerEvent, onClick: () => void) => void;
	/** Open a line below this cell. Not a cell: see ../Ghost.tsx. */
	onPlus: () => void;
	onDelete: () => void;
	/** Set on a text cell of an editable plane. */
	onTextKey?: (e: React.KeyboardEvent) => void;
	onSelect: () => void;
	onFocusConsumed: () => void;
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
}) {
	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: a mousedown anywhere in a cell hands control to that cell's own editor
		<div
			ref={setEl}
			data-cell={cell.id}
			hidden={hidden}
			data-selected={selected && !selectedStrong ? "" : undefined}
			className={docCellRow({ dragging })}
			onKeyDownCapture={onTextKey}
			onMouseDown={(e) => {
				// A plain click inside a cell leaves cell-selection mode;
				// the cell's own editor takes over from here.
				if (e.button === 0) onPointerIn();
			}}
		>
			<LeftGutter
				editable={editable}
				cellId={cell.id}
				editing={editing}
				onSetEditing={onSetEditing}
				onDrag={onDrag}
				onPlus={onPlus}
				onDelete={onDelete}
			/>
			{/* Before the body in the DOM, though the grid puts it on the right: the
			    row's controls come first in the tab order, so Tab out of what the
			    cell draws goes on to the next row, not back to its own toggle. */}
			<RightGutter state={cell.status.state} editing={editing} onSetEditing={onSetEditing} />
			<div className={docCell({ selected, selectedStrong })} data-cell-body="">
				{dropAbove ? <span className={`${docDropIndicator} top-0`} /> : null}
				<ProgramCell
					source={cell.source}
					draws={cell.has_ui}
					uiPath={uiPath}
					status={cell.status}
					editing={editing}
					focusReq={focusReq}
					onFocusConsumed={onFocusConsumed}
					onCommit={onCommit}
					onExit={onExit}
					onSelectSelf={onSelect}
					onSetEditing={onSetEditing}
					readOnly={!editable}
				/>
			</div>
		</div>
	);
}
