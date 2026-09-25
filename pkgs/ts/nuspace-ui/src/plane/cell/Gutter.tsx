// A cell's gutter: every affordance it has, in the left track of its row.

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
import { Check, Code, GripVertical, Hash, Plus, Trash2 } from "lucide-react";
import type * as React from "react";
import { useCallback, useState } from "react";
import {
	CELL_STATUS,
	docDragHandle,
	docGutter,
	docGutterAffordances,
	docGutterRow,
	docGutterToggle,
	docStatusRail,
} from "../../design";
import type { CellState } from "../types";

/**
 * Every affordance a cell has, in the gutter beside the reading column.
 *
 * Three stacked rows of kit primitives, so they share a box, a hover tier, a
 * focus ring and one reveal. Top to bottom they read as what you do to the
 * cell, what you do with it, and what it is: add and drag, copy its id, open
 * its source next to the dot that says whether it is alive.
 *
 * Every glyph carries a tooltip and a label. A bare glyph in a margin is not
 * self-explanatory, and `title` is not an affordance, it is a delay.
 *
 * The grip drags, and a click on it opens the cell's controls in a menu
 * anchored to it: the source toggle, the id, delete. The menu is controlled,
 * so a press that turns into a drag never opens it (../useCellDrag.ts).
 */
export function Gutter({
	cellId,
	editing,
	onSetEditing,
	onDrag,
	onPlus,
	onDelete,
	state,
	pinned,
}: {
	cellId: string;
	/** The cell's state, painted as the rail on the lane's edge. */
	state: CellState;
	/** Keep controls + rail visible off hover: source open, or cell-selected. */
	pinned: boolean;
	editing: boolean;
	onSetEditing: (on: boolean) => void;
	/** A press on the grip. `onClick` runs when it never becomes a drag. */
	onDrag: (e: React.PointerEvent, onClick: () => void) => void;
	/** Open a line below this cell. Not a cell: see ../Ghost.tsx. */
	onPlus: () => void;
	onDelete: () => void;
}) {
	const [copied, setCopied] = useState(false);
	const [menu, setMenu] = useState(false);

	// The bare cell id, not the `cells.<id>` mount prefix: the id is what
	// every op on the wire is keyed by, so it is the string worth having on the
	// clipboard. See ./address.ts for the prefix and where it comes from.
	const copyId = useCallback(() => {
		navigator.clipboard
			?.writeText(cellId)
			.then(() => {
				setCopied(true);
				window.setTimeout(() => setCopied(false), 1200);
			})
			.catch(() => {});
	}, [cellId]);

	return (
		<div className={docGutter}>
			<Tooltip>
				<TooltipTrigger asChild>
					<span className={docStatusRail(state, pinned)} />
				</TooltipTrigger>
				<TooltipContent side="top">{CELL_STATUS[state].label}</TooltipContent>
			</Tooltip>
			<div className={docGutterAffordances(pinned || menu)}>
				<div className={docGutterRow}>
					<Tooltip>
						<TooltipTrigger asChild>
							<IconButton variant="ghost" size="sm" aria-label="Add a line below" onClick={onPlus}>
								<Plus />
							</IconButton>
						</TooltipTrigger>
						<TooltipContent side="top">Add a line below</TooltipContent>
					</Tooltip>
					<DropdownMenu open={menu} onOpenChange={setMenu}>
						<Tooltip>
							<TooltipTrigger asChild>
								<DropdownMenuTrigger asChild>
									<IconButton
										variant="ghost"
										size="sm"
										aria-label="Drag to reorder, click for options"
										// Prevented here, so the menu's own press never opens it.
										onPointerDown={(e) => onDrag(e, () => setMenu(true))}
										data-cell-grip=""
										className={docDragHandle}
									>
										<GripVertical />
									</IconButton>
								</DropdownMenuTrigger>
							</TooltipTrigger>
							<TooltipContent side="top">Drag to reorder, click for options</TooltipContent>
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
							<DropdownMenuSeparator />
							<DropdownMenuItem variant="danger" onSelect={onDelete}>
								<Trash2 />
								Delete
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
				<div className={docGutterRow}>
					<Tooltip>
						<TooltipTrigger asChild>
							<IconButton
								variant="ghost"
								size="sm"
								aria-label="Copy this cell's cell id"
								onClick={copyId}
							>
								{copied ? <Check className="text-status-ok" /> : <Hash />}
							</IconButton>
						</TooltipTrigger>
						<TooltipContent side="top">{copied ? "Copied" : "Copy cell id"}</TooltipContent>
					</Tooltip>
					<Tooltip>
						<TooltipTrigger asChild>
							<Toggle
								size="sm"
								pressed={editing}
								onPressedChange={onSetEditing}
								aria-label="Show this cell's source"
								className={docGutterToggle}
							>
								<Code />
							</Toggle>
						</TooltipTrigger>
						<TooltipContent side="top">{editing ? "Hide source" : "Show source"}</TooltipContent>
					</Tooltip>
				</div>
			</div>
		</div>
	);
}
