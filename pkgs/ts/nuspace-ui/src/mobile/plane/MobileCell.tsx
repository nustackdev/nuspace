// One cell on the phone: what its program draws, and nothing else. No
// gutter, no grip, no source editor: the source opens read-only from the
// long-press sheet (./CellSheet.tsx).
//
// The inside follows desktop's (../../plane/cell/Program.tsx) minus the
// editor: the error in place of the view, the view once it lands, a skeleton
// if it is slow, a "No view" chip for a cell that draws nothing. No tooltip on
// the chip: a phone has no hover.
//
// A long-press anywhere on it opens its sheet, except in a field being typed
// in, where a long-press is the phone's own text selection.

import type { Path } from "@nustackdev/ui-core";
import {
	Alert,
	AlertDescription,
	AlertIcon,
	AlertTitle,
	Badge,
	NodeView,
	Skeleton,
} from "@nustackdev/ui-kit";
import type * as React from "react";
import { useRef } from "react";
import { useAfter } from "../../core/delay";
import {
	CELL_STATUS,
	docProgram,
	docProgramFields,
	docProgramHeadless,
	docProgramHeadlessChip,
	docProgramLoading,
	docProgramLoadingLine,
	docProgramLoadingLineShort,
	docStatusTrace,
	mobileCell,
} from "../../design";
import { useCellHasUi } from "../../plane/cell/address";
import { VIEW_LOADER_DELAY_MS } from "../../plane/cell/Program";
import type { Cell } from "../../plane/types";
import { useLongPress } from "../gestures";

/** Whether `target` sits in a field that has the keyboard: its long-press selects text. */
export function inActiveField(target: EventTarget | null): boolean {
	const active = document.activeElement;
	if (!(target instanceof Node) || !(active instanceof HTMLElement)) return false;
	const typing =
		active instanceof HTMLInputElement ||
		active instanceof HTMLTextAreaElement ||
		active.isContentEditable === true;
	return typing && active.contains(target);
}

export function MobileCell({
	cell,
	uiPath,
	pressed,
	onLongPress,
}: {
	cell: Cell;
	/** Where this cell's own refs live in the tree. */
	uiPath: Path;
	/** Its sheet is open. */
	pressed: boolean;
	onLongPress: () => void;
}) {
	const press = useLongPress(onLongPress);
	const onPointerDown = (e: React.PointerEvent<HTMLElement>) => {
		if (!inActiveField(e.target)) press.onPointerDown?.(e);
	};
	return (
		<div
			data-cell={cell.id}
			className={mobileCell(pressed)}
			{...press}
			onPointerDown={onPointerDown}
		>
			<CellOutput cell={cell} uiPath={uiPath} />
		</div>
	);
}

/** What the program produced: its error, its view, or a note that it has none. */
function CellOutput({ cell, uiPath }: { cell: Cell; uiPath: Path }) {
	const { status, draws } = cell;
	const hasUi = useCellHasUi(uiPath);
	const token = CELL_STATUS[status.state];
	// Once a view has shown, an empty cell cleared it: no waiting again.
	const drewOnce = useRef(false);
	if (hasUi) drewOnce.current = true;
	const waiting = !hasUi && !drewOnce.current && !status.error && draws !== false;
	const loader = useAfter(waiting, VIEW_LOADER_DELAY_MS);

	return (
		<div className={docProgram}>
			{status.error ? (
				<Alert tone={token.tone}>
					<AlertIcon />
					<div className="min-w-0 flex-1">
						<AlertTitle>
							{status.state === "invalid" ? "Does not compile" : "Ran and died"}
						</AlertTitle>
						<AlertDescription className={docStatusTrace}>{status.error}</AlertDescription>
					</div>
				</Alert>
			) : null}
			{hasUi ? (
				<div className={docProgramFields} data-cell-ui="">
					<NodeView path={uiPath} />
				</div>
			) : waiting ? (
				loader ? (
					<div className={docProgramLoading} aria-busy="true" data-view-loading="">
						<Skeleton shape="text" className={docProgramLoadingLine} />
						<Skeleton shape="text" className={docProgramLoadingLineShort} />
					</div>
				) : null
			) : !status.error ? (
				<div className={docProgramHeadless}>
					<Badge variant="dashed" size="sm" className={docProgramHeadlessChip}>
						No view
					</Badge>
				</div>
			) : null}
		</div>
	);
}
