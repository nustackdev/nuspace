// A cell's controls, one thin row in the left gutter of its row: add a line
// below, and the grip, which drags and, clicked, opens the cell's menu. The menu opens
// on the cell's facts (./InfoBlock.tsx), asked for as it opens, then its
// id, a row that copies, and its key, a row with a submenu (./KeySub.tsx),
// then what to do. Editing the key closes the menu and opens a popover on
// // the grip, once the menu has let go of the focus. It can also move the
// cell to another plane (../transfer.ts). The source opens from the menu
// too; a broken cell says so in its body. A read-only plane has no place
// to change, so its gutter keeps only the menu.
//
// Each row is one control tall, never taller than the shortest cell
// (`docCellRow` holds every row to it), so a row's controls never reach into
// its neighbour's and each row shows its own on its own: hovered, its
// controls reached by keyboard, it is the one selected cell, or its menu is
// open (`docGutterLane`).
//
// Every glyph carries a tooltip and a label. A bare glyph in a margin is not
// self-explanatory, and `title` is not an affordance, it is a delay.

import type { Path } from "@nustackdev/ui-core";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuShortcut,
	DropdownMenuTrigger,
	IconButton,
	Popover,
	PopoverAnchor,
	PopoverContent,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import {
	ArrowRightLeft,
	Check,
	Code,
	Ellipsis,
	GripVertical,
	Hash,
	Plus,
	RotateCw,
	Trash2,
} from "lucide-react";
import type * as React from "react";
import { useRef, useState } from "react";
import { useCopyRow } from "../../core/clipboard";
import { docDragHandle, docGutterControls, docGutterLane } from "../../design";
import type { CellState } from "../types";
import { CellInfoBlock } from "./InfoBlock";
import { KeyEditor, KeySub } from "./KeySub";

/** The left gutter: add, and the grip with the cell's menu. */
export function LeftGutter({
	editable,
	cellId,
	cellKey,
	panePath,
	state,
	error,
	editing,
	onSetEditing,
	onDrag,
	onPlus,
	onDelete,
	onRestart,
	onTransfer,
	onSelect,
	onAskInfo,
	onKey,
}: {
	/** The plane's setting. Off, only the menu remains, and it cannot delete or move. */
	editable: boolean;
	cellId: string;
	/** The cell's key, "" for none: no row copies it then. */
	cellKey: string;
	/** The pane node the cell's info lands on. */
	panePath: Path;
	/** Its live status, which heads the menu. */
	state: CellState;
	error: string | null;
	editing: boolean;
	onSetEditing: (on: boolean) => void;
	/** A press on the grip. `onClick` runs when it never becomes a drag. */
	onDrag: (e: React.PointerEvent, onClick: () => void) => void;
	/** Open a line below this cell. Not a cell: see ../Ghost.tsx. */
	onPlus: () => void;
	onDelete: () => void;
	/** Run the cell again. */
	onRestart: () => void;
	/** Open the plane picker for this cell. */
	onTransfer: () => void;
	/** Select the cell and hand the plane the keyboard. */
	onSelect: () => void;
	/** Ask for the cell's info: the menu is opening. */
	onAskInfo: () => void;
	/** Set or change the cell's key, "" to remove it. Left out on a read-only plane. */
	onKey?: (key: string) => void;
}) {
	// Controlled, so a press that turns into a drag never opens it
	// (../useCellDrag.ts).
	const [menu, setMenu] = useState(false);
	// Set by a pick that sends the caret somewhere of its own: the source, or
	// away with the cell. Anything else, a dismiss included, leaves the cell
	// selected, so its keys (Delete, arrows, Enter) work straight after.
	const sent = useRef(false);
	// The key editor, open on the grip. Asked for from the menu, it opens as
	// the menu finishes closing, so the two never pass the focus back and forth.
	const [keying, setKeying] = useState(false);
	const keyNext = useRef(false);
	// Opening it selects this cell alone, so the menu reads as about this
	// cell and nothing else stays selected under it.
	const openMenu = (open: boolean) => {
		if (open) {
			sent.current = false;
			keyNext.current = false;
			onSelect();
			onAskInfo();
		}
		setMenu(open);
	};

	// The bare cell id, not the `cells.<id>` mount prefix: the id is what every
	// op on the wire is keyed by. See ./address.ts for the prefix.
	const copy = useCopyRow(cellId);

	const label = editable ? "Drag to reorder, click for options" : "Cell options";
	return (
		<div
			className={docGutterLane("left")}
			data-cell-gutter=""
			data-pinned={keying ? "" : undefined}
		>
			<Popover open={keying} onOpenChange={setKeying}>
				<PopoverAnchor asChild>
					<div className={docGutterControls}>
						{editable ? (
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
						) : null}
						<DropdownMenu open={menu} onOpenChange={openMenu}>
							<Tooltip>
								<TooltipTrigger asChild>
									<DropdownMenuTrigger asChild>
										<IconButton
											variant="ghost"
											size="sm"
											aria-label={label}
											data-cell-grip=""
											// Its own mark: the tooltip's `data-state` wins the merge on this button.
											data-menu={menu ? "open" : undefined}
											// Prevented here, so the menu's own press never opens it.
											onPointerDown={editable ? (e) => onDrag(e, () => openMenu(true)) : undefined}
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
								className="w-72"
								// The caret goes where the action sends it, not back to the grip.
								onCloseAutoFocus={(e) => {
									e.preventDefault();
									if (keyNext.current) setKeying(true);
									else if (!sent.current) onSelect();
								}}
							>
								<CellInfoBlock panePath={panePath} cellId={cellId} state={state} error={error} />
								<DropdownMenuSeparator />
								<DropdownMenuItem onSelect={copy.onSelect} aria-label="Copy cell ID">
									{copy.copied ? <Check /> : <Hash />}
									<span className="min-w-0 truncate font-mono text-xs">{cellId}</span>
									<DropdownMenuShortcut>{copy.copied ? "Copied" : "Copy"}</DropdownMenuShortcut>
								</DropdownMenuItem>
								<KeySub
									cellKey={cellKey}
									onEdit={
										onKey
											? () => {
													sent.current = true;
													keyNext.current = true;
												}
											: undefined
									}
									onRemove={onKey ? () => onKey("") : undefined}
								/>
								<DropdownMenuSeparator />
								<DropdownMenuItem
									onSelect={() => {
										sent.current = true;
										onSetEditing(!editing);
									}}
								>
									<Code />
									{editing ? "Hide source" : "Show source"}
								</DropdownMenuItem>
								<DropdownMenuItem onSelect={onRestart}>
									<RotateCw />
									Restart cell
								</DropdownMenuItem>
								{editable ? (
									<>
										<DropdownMenuSeparator />
										<DropdownMenuItem
											onSelect={() => {
												sent.current = true;
												onTransfer();
											}}
										>
											<ArrowRightLeft />
											Move to plane…
										</DropdownMenuItem>
										<DropdownMenuItem
											variant="danger"
											onSelect={() => {
												sent.current = true;
												onDelete();
											}}
										>
											<Trash2 />
											Delete
										</DropdownMenuItem>
									</>
								) : null}
							</DropdownMenuContent>
						</DropdownMenu>
					</div>
				</PopoverAnchor>
				{onKey ? (
					<PopoverContent
						align="start"
						side="bottom"
						// Back to the cell, selected, its keys working.
						onCloseAutoFocus={(e) => {
							e.preventDefault();
							onSelect();
						}}
					>
						<KeyEditor value={cellKey} onSave={onKey} onClose={() => setKeying(false)} />
					</PopoverContent>
				) : null}
			</Popover>
		</div>
	);
}
