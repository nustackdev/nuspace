// A cell's controls, one thin row in each gutter of its row.
//
// Left, what you do to the cell's place on the plane: add a line below, and
// the grip, which drags and, clicked, opens the cell's menu. Right, what the
// cell is: the source toggle, its glyph tinted by the cell's status. A
// read-only plane has no place to change, so its left gutter keeps only the
// menu.
//
// Each row is one control tall, never taller than the shortest cell
// (`docCellRow` holds every row to it), so a row's controls never reach into
// its neighbour's and each row shows its own on its own: hovered, its
// controls reached by keyboard, it is the one selected cell, or its menu is
// open (`docGutterLane`). The source toggle also stays out while the source
// is open or the cell is broken, so either reads at a glance down the edge.
//
// Every glyph carries a tooltip and a label. A bare glyph in a margin is not
// self-explanatory, and `title` is not an affordance, it is a delay.

import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Toggle,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Code, Ellipsis, GripVertical, Hash, Plus, Trash2 } from "lucide-react";
import type * as React from "react";
import { useState } from "react";
import {
	CELL_STATUS,
	docDragHandle,
	docGutterControls,
	docGutterLane,
	docGutterStatus,
	docGutterToggle,
} from "../../design";
import type { CellState } from "../types";

/** States the source toggle stays out for, rather than waiting for a hover. */
const LOUD: ReadonlySet<CellState> = new Set(["invalid", "failed"]);

/** The left gutter: add, and the grip with the cell's menu. */
export function LeftGutter({
	editable,
	cellId,
	editing,
	onSetEditing,
	onDrag,
	onPlus,
	onDelete,
}: {
	/** The plane's setting. Off, only the menu remains, and it cannot delete. */
	editable: boolean;
	cellId: string;
	editing: boolean;
	onSetEditing: (on: boolean) => void;
	/** A press on the grip. `onClick` runs when it never becomes a drag. */
	onDrag: (e: React.PointerEvent, onClick: () => void) => void;
	/** Open a line below this cell. Not a cell: see ../Ghost.tsx. */
	onPlus: () => void;
	onDelete: () => void;
}) {
	// Controlled, so a press that turns into a drag never opens it
	// (../useCellDrag.ts).
	const [menu, setMenu] = useState(false);

	// The bare cell id, not the `cells.<id>` mount prefix: the id is what every
	// op on the wire is keyed by. See ./address.ts for the prefix.
	const copyId = () => {
		navigator.clipboard?.writeText(cellId).catch(() => {});
	};

	const label = editable ? "Drag to reorder, click for options" : "Cell options";
	return (
		<div className={docGutterLane("left")} data-cell-gutter="">
			<div className={docGutterControls}>
				{editable ? (
					<Tooltip>
						<TooltipTrigger asChild>
							<IconButton variant="ghost" size="sm" aria-label="Add a line below" onClick={onPlus}>
								<Plus />
							</IconButton>
						</TooltipTrigger>
						<TooltipContent side="top">Add a line below</TooltipContent>
					</Tooltip>
				) : null}
				<DropdownMenu open={menu} onOpenChange={setMenu}>
					<Tooltip>
						<TooltipTrigger asChild>
							<DropdownMenuTrigger asChild>
								<IconButton
									variant="ghost"
									size="sm"
									aria-label={label}
									data-cell-grip=""
									// Prevented here, so the menu's own press never opens it.
									onPointerDown={editable ? (e) => onDrag(e, () => setMenu(true)) : undefined}
									className={editable ? docDragHandle : undefined}
								>
									{editable ? <GripVertical /> : <Ellipsis />}
								</IconButton>
							</DropdownMenuTrigger>
						</TooltipTrigger>
						<TooltipContent side="top">{label}</TooltipContent>
					</Tooltip>
					<DropdownMenuContent
						align="start"
						// The caret goes where the action sends it, not back to the grip.
						onCloseAutoFocus={(e) => e.preventDefault()}
					>
						<DropdownMenuItem onSelect={() => onSetEditing(!editing)}>
							<Code />
							{editing ? "Hide source" : "Show source"}
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={copyId}>
							<Hash />
							Copy cell id
						</DropdownMenuItem>
						{editable ? (
							<>
								<DropdownMenuSeparator />
								<DropdownMenuItem variant="danger" onSelect={onDelete}>
									<Trash2 />
									Delete
								</DropdownMenuItem>
							</>
						) : null}
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		</div>
	);
}

/** The right gutter: the source toggle, which says the cell's state. */
export function RightGutter({
	state,
	editing,
	onSetEditing,
}: {
	state: CellState;
	editing: boolean;
	onSetEditing: (on: boolean) => void;
}) {
	const status = CELL_STATUS[state].label.toLowerCase();
	const label = `${editing ? "Hide source" : "Show source"} · ${status}`;
	return (
		<div
			className={docGutterLane("right")}
			data-cell-gutter=""
			data-pinned={editing || LOUD.has(state) ? "" : undefined}
		>
			<div className={docGutterControls}>
				<Tooltip>
					<TooltipTrigger asChild>
						<Toggle
							size="sm"
							pressed={editing}
							onPressedChange={onSetEditing}
							aria-label={label}
							data-cell-status={state}
							className={docGutterToggle}
						>
							<Code className={docGutterStatus(state)} />
						</Toggle>
					</TooltipTrigger>
					<TooltipContent side="top">{label}</TooltipContent>
				</Tooltip>
			</div>
		</div>
	);
}
