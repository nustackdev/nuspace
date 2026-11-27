// What the dock's + opens: one short sheet of what can be done from here
// (./model.ts `controlsFor`), each row handing off to the sheet or mode that
// does it.
//
//   Add cell           the plane's add sheet (../plane/AddCellSheet.tsx)
//   Add plane          the sidebar's add sheet (../sidebar/AddPlaneSheet.tsx), at the top
//   Add plane inside   the same sheet, a child of the plane on screen
//   Edit cells         the plane's cells, a tap each for its options (../plane/editing.ts)
//
// A pick waits for this sheet to finish sliding away before the next one
// opens, so two sheets never move at once.

import { BottomSheet, BottomSheetContent, BottomSheetItem } from "@nustackdev/ui-kit";
import { FilePlus, FilePlusCorner, SquarePen, SquarePlus } from "lucide-react";
import type * as React from "react";
import { useEffect, useRef } from "react";
import { mobileSheetLabel } from "../../design";
import { openAddPlane } from "../../sidebar/add";
import { ROOT_ID } from "../../sidebar/types";
import { openAddCell } from "../addCell";
import { editCells } from "../plane/editing";
import { type Control, controlsFor, type Screen } from "./model";

/** How long a pick waits for the close to end, where the sheet never says it did. */
const HANDOFF_MS = 600;

const ROWS: Record<Control, { label: string; icon: React.ReactNode }> = {
	cell: { label: "Add cell", icon: <SquarePlus aria-hidden="true" /> },
	plane: { label: "Add plane", icon: <FilePlusCorner aria-hidden="true" /> },
	inside: { label: "Add plane inside", icon: <FilePlus aria-hidden="true" /> },
	edit: { label: "Edit cells", icon: <SquarePen aria-hidden="true" /> },
};

export function ControlSheet({
	screen,
	open,
	onClose,
}: {
	screen: Screen;
	open: boolean;
	onClose: () => void;
}) {
	// The pick waiting for the close, run once.
	const pending = useRef<(() => void) | null>(null);
	const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
	const run = () => {
		if (timer.current) clearTimeout(timer.current);
		timer.current = null;
		const next = pending.current;
		pending.current = null;
		next?.();
	};
	useEffect(
		() => () => {
			if (timer.current) clearTimeout(timer.current);
		},
		[],
	);

	const pick = (control: Control) => {
		const plane = screen?.plane;
		pending.current = () => {
			if (control === "cell") openAddCell();
			else if (control === "plane") openAddPlane({ parent: ROOT_ID });
			else if (!plane) return;
			else if (control === "inside") openAddPlane({ parent: plane, pane: plane });
			else editCells(plane);
		};
		timer.current = setTimeout(run, HANDOFF_MS);
		onClose();
	};

	return (
		<BottomSheet
			open={open}
			onOpenChange={(next) => (next ? null : onClose())}
			onAnimationEnd={(isOpen) => {
				if (!isOpen) run();
			}}
		>
			<BottomSheetContent label="Add or edit" data-control-sheet="">
				<div role="menu">
					{controlsFor(screen).map((control) => (
						<BottomSheetItem
							key={control}
							role="menuitem"
							data-control={control}
							onClick={() => pick(control)}
						>
							{ROWS[control].icon}
							<span className={mobileSheetLabel}>{ROWS[control].label}</span>
						</BottomSheetItem>
					))}
				</div>
			</BottomSheetContent>
		</BottomSheet>
	);
}
