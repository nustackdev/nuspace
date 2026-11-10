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
// Nothing here knows what the cell draws. A press inside it is reported
// (`onPress`) and the plane decides what a drag from there means; the keys
// of what it draws are that editor's own, and its document reports what it
// had no use for through the kit registry, never through this row. Where
// the caret is, it does say (`onCaret`): in what the cell draws, elsewhere
// in its row, or gone from it. That is the row's own focus, nothing read
// out of the editor.

import type { Path } from "@nustackdev/ui-core";
import type * as React from "react";
import { useState } from "react";
import { docCell, docCellRow, docDropIndicator } from "../../design";
import { Identity } from "../Identity";
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
	onRestart,
	onPress,
	onSelect,
	onFocusConsumed,
	onDrawn,
	onCommit,
	onKey,
	onExit,
	onCaret,
}: {
	cell: CellValue;
	/** Where this cell's own refs live in the tree. */
	uiPath: Path;
	editable: boolean;
	/** Drawn but not shown: an input line stands in for it, or it is leaving (../state.ts). */
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
	/** Run the cell again. */
	onRestart: () => void;
	/** A press anywhere in the row: the plane may start a range select from it. */
	onPress?: (e: React.PointerEvent) => void;
	onSelect: () => void;
	onFocusConsumed: () => void;
	/** What the program draws has mounted. */
	onDrawn?: () => void;
	onCommit: (source: string) => void;
	/** Set or change the cell's key, "" to remove it. Left out on a read-only plane. */
	onKey?: (key: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
	/**
	 * The caret arrived in what the cell draws ("ui") or elsewhere in its
	 * row, or left it (null); `nowhere` when it left for no other element.
	 */
	onCaret?: (where: "ui" | "row" | null, nowhere?: boolean) => void;
}) {
	// The identity block is the cell's own business, like a menu being open:
	// nothing else reads it, so it is held here.
	const [identity, setIdentity] = useState(false);
	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: a mousedown anywhere in a cell hands control to that cell's own editor
		<div
			ref={setEl}
			data-cell={cell.id}
			hidden={hidden}
			data-selected={selected && !selectedStrong ? "" : undefined}
			className={docCellRow({ dragging })}
			onPointerDown={onPress}
			onMouseDown={(e) => {
				// A plain click inside a cell leaves cell-selection mode;
				// the cell's own editor takes over from here.
				if (e.button === 0) onPointerIn();
			}}
			onFocus={(e) => onCaret?.((e.target as Element).closest?.("[data-cell-ui]") ? "ui" : "row")}
			onBlur={(e) => {
				// Within the row, the focus that follows says where it went.
				// Nowhere at all (the window lost focus, or the row is being
				// removed and the browser says so first) is told apart.
				const to = e.relatedTarget as Node | null;
				if (!e.currentTarget.contains(to)) onCaret?.(null, to === null);
			}}
		>
			<LeftGutter
				editable={editable}
				cellId={cell.id}
				cellKey={cell.key}
				editing={editing}
				onSetEditing={onSetEditing}
				onDrag={onDrag}
				onPlus={onPlus}
				onDelete={onDelete}
				onRestart={onRestart}
				onSelect={onSelect}
			/>
			{/* Before the body in the DOM, though the grid puts it on the right: the
			    row's controls come first in the tab order, so Tab out of what the
			    cell draws goes on to the next row, not back to its own toggle. */}
			<RightGutter
				state={cell.status.state}
				editing={editing}
				onSetEditing={onSetEditing}
				identity={identity}
				onSetIdentity={setIdentity}
			/>
			<div className={docCell({ selected })} data-cell-body="">
				{dropAbove ? <span className={`${docDropIndicator} top-0`} /> : null}
				{identity ? (
					<Identity
						kind="cell"
						id={cell.id}
						value={cell.key}
						onSave={onKey}
						onClose={() => {
							setIdentity(false);
							onSelect();
						}}
					/>
				) : null}
				<ProgramCell
					source={cell.source}
					draws={cell.draws}
					uiPath={uiPath}
					status={cell.status}
					editing={editing}
					focusReq={focusReq}
					onFocusConsumed={onFocusConsumed}
					onDrawn={onDrawn}
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
