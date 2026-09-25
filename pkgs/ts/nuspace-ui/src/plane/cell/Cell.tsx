// One cell on a plane: its row, its gutter, and the program inside.
//
// There is no cell kind to branch on. Each cell renders the subtree at its
// own address -- the ui refs its program mounted, which arrive as ordinary
// nodes -- through `NodeView`, inside the same `docCell`, with the same
// gutter: add and drag, copy the cell id, open the source. Every cell
// compiles, runs, is supervised and reports status identically. See
// ./address.ts for where that address is.
//
// `editable` is the plane's setting. Off, the cell draws its output and
// nothing else: no gutter, and its source never opens.

import type { Path } from "@nustackdev/ui-core";
import type * as React from "react";
import { docCell, docDropIndicator } from "../../design";
import type { FocusReq } from "../state";
import type { Cell as CellValue, ExitDir } from "../types";
import { Gutter } from "./Gutter";
import { ProgramCell } from "./Program";

export function Cell({
	cell,
	uiPath,
	editable,
	hidden,
	selected,
	selectedStrong,
	focused,
	editing,
	focusReq,
	dragging,
	dropAbove,
	setEl,
	onPointerIn,
	onSetEditing,
	onDrag,
	onPlus,
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
	/** The caret lives in here. */
	focused: boolean;
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
	onDrag: (e: React.PointerEvent) => void;
	/** Open a line below this cell. Not a cell: see ../Ghost.tsx. */
	onPlus: () => void;
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
			className={docCell({ selected, selectedStrong, focused, dragging })}
			onMouseDown={(e) => {
				// A plain click inside a cell leaves cell-selection mode;
				// the cell's own editor takes over from here.
				if (e.button === 0) onPointerIn();
			}}
		>
			{dropAbove ? <span className={`${docDropIndicator} top-0`} /> : null}
			{editable ? (
				<Gutter
					cellId={cell.id}
					state={cell.status.state}
					pinned={editing || selected}
					editing={editing}
					onSetEditing={onSetEditing}
					onDrag={onDrag}
					onPlus={onPlus}
					onSelect={onSelect}
				/>
			) : null}
			<ProgramCell
				source={cell.source}
				uiPath={uiPath}
				status={cell.status}
				editable={editable}
				editing={editing}
				focusReq={focusReq}
				onFocusConsumed={onFocusConsumed}
				onCommit={onCommit}
				onExit={onExit}
				onSelectSelf={onSelect}
				onSetEditing={onSetEditing}
			/>
		</div>
	);
}
