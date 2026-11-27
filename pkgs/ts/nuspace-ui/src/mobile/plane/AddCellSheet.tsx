// The + sheet: the same cell types as desktop's `/` menu, from the same
// source (./model.ts `addCellGroups`). A tap adds that cell at the end of the
// plane and closes the sheet. The dock's Add cell opens it (../addCell.ts).

import { BottomSheet, BottomSheetContent, BottomSheetItem } from "@nustackdev/ui-kit";
import { Fragment } from "react";
import { mobileSheetGroup, mobileSheetLabel } from "../../design";
import { PlaneIcon } from "../../icon/PlaneIcon";
import { parseIcon } from "../../icon/parse";
import type { CellSpec } from "../../plane/types";
import { closeAddCell, useAddCellOpen } from "../addCell";
import { addCellGroups } from "./model";

/** The glyph a Cell that names none shows, as in the `/` menu. */
const CELL_ICON = { kind: "lucide", name: "square-terminal" } as const;

export function AddCellSheet({
	cellSpecs,
	onPick,
}: {
	cellSpecs: CellSpec[];
	/** Add a cell made from this one at the end of the plane. */
	onPick: (spec: CellSpec) => void;
}) {
	const open = useAddCellOpen();
	return (
		<BottomSheet open={open} onOpenChange={(next) => (next ? null : closeAddCell())}>
			<BottomSheetContent title="Add cell" data-add-cell-sheet="">
				{addCellGroups(cellSpecs).map((group, g) => (
					<Fragment key={group.title ?? `_${g}`}>
						{group.title ? <div className={mobileSheetGroup}>{group.title}</div> : null}
						{group.sections.map((section) => (
							<Fragment key={section.heading ?? `_${section.items[0]?.name}`}>
								{section.heading && section.heading !== group.title ? (
									<div className={mobileSheetGroup}>{section.heading}</div>
								) : null}
								{section.items.map((spec) => (
									<BottomSheetItem
										key={spec.name || "_empty"}
										data-spec={spec.name}
										onClick={() => {
											closeAddCell();
											onPick(spec);
										}}
									>
										<PlaneIcon icon={parseIcon(spec.icon) ?? CELL_ICON} />
										<span className={mobileSheetLabel}>{spec.label}</span>
									</BottomSheetItem>
								))}
							</Fragment>
						))}
					</Fragment>
				))}
			</BottomSheetContent>
		</BottomSheet>
	);
}
