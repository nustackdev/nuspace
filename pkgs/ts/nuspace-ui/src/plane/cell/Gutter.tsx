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
	docGutterStatus,
	docGutterToggle,
} from "../../design";
import type { CellState } from "../types";

/**
 * Every affordance a cell has, in the gutter beside the reading column.
 *
 * Two stacked rows of kit primitives, so they share a box, a hover tier, a
 * focus ring and one reveal. Top to bottom they read as what you do to the
 * cell and what it is: add and drag, then copy its id and open its source.
 * A read-only plane drops the first row, so the second takes its place on
 * the cell's first line and the source opens read-only. The source toggle's glyph is tinted by the cell's status, and
 * its label and tooltip say the state in words.
 *
 * Every glyph carries a tooltip and a label. A bare glyph in a margin is not
 * self-explanatory, and `title` is not an affordance, it is a delay.
 *
 * The grip drags, and a click on it opens the cell's controls in a menu
 * anchored to it: the source toggle, the id, delete. The menu is controlled,
 * so a press that turns into a drag never opens it (../useCellDrag.ts).
 */
export function Gutter({
	editable,
	cellId,
	editing,
	onSetEditing,
	onDrag,
	onPlus,
	onDelete,
	state,
	shown,
	menu,
	onMenu,
}: {
	/** The plane's setting. Off, only copy-id and the source toggle remain. */
	editable: boolean;
	cellId: string;
	/** The cell's state, painted on the source toggle's glyph. */
	state: CellState;
	/** This cell owns the plane's one visible gutter (`gutterOwner`). */
	shown: boolean;
	/** The grip's menu is open. Held by the plane, see `gutterOwner`. */
	menu: boolean;
	onMenu: (open: boolean) => void;
	editing: boolean;
	onSetEditing: (on: boolean) => void;
	/** A press on the grip. `onClick` runs when it never becomes a drag. */
	onDrag: (e: React.PointerEvent, onClick: () => void) => void;
	/** Open a line below this cell. Not a cell: see ../Ghost.tsx. */
	onPlus: () => void;
	onDelete: () => void;
}) {
	const [copied, setCopied] = useState(false);
	const status = CELL_STATUS[state].label.toLowerCase();
	const sourceLabel = `${editing ? "Hide source" : "Show source"} · ${status}`;

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
		<div className={docGutter} data-cell-gutter="">
			<div className={docGutterAffordances(shown)}>
				{editable ? (
					<div className={docGutterRow}>
						<Tooltip>
							<TooltipTrigger asChild>
								<IconButton
									variant="ghost"
									size="sm"
									aria-label="Add a line below"
									onClick={onPlus}
								>
									<Plus />
								</IconButton>
							</TooltipTrigger>
							<TooltipContent side="top">Add a line below</TooltipContent>
						</Tooltip>
						<DropdownMenu open={menu} onOpenChange={onMenu}>
							<Tooltip>
								<TooltipTrigger asChild>
									<DropdownMenuTrigger asChild>
										<IconButton
											variant="ghost"
											size="sm"
											aria-label="Drag to reorder, click for options"
											// Prevented here, so the menu's own press never opens it.
											onPointerDown={(e) => onDrag(e, () => onMenu(true))}
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
				) : null}
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
								aria-label={sourceLabel}
								data-cell-status={state}
								className={docGutterToggle}
							>
								<Code className={docGutterStatus(state)} />
							</Toggle>
						</TooltipTrigger>
						<TooltipContent side="top">{sourceLabel}</TooltipContent>
					</Tooltip>
				</div>
			</div>
		</div>
	);
}
