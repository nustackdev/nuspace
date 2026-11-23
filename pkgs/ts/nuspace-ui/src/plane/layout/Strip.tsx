// A strip on a plane: its columns side by side at their shares, the cells of
// each stacked, drawn by the plane (`renderCell`) as on any row.
//
// The columns are the kit's resizable group. Dragging a handle between two
// previews locally and, on release, hands the new shares up (`onResize`),
// one `layout.set` of the whole rows; a read-only plane draws no handles. The shares the
// server ships are what the group shows: a new set (this tab's write
// landing, or another tab's) is laid on it as it comes, and that echo is
// not sent back.
//
// The drop line above it is the plane's mark for a gap there (./drag.ts).
// A strip itself is not dragged: its cells are, one at a time, and the
// keyboard moves it as one row. It has no id: it is named by its first cell.

import {
	ResizableHandle,
	ResizablePanel,
	ResizablePanelGroup,
	type ResizablePanelGroupHandle,
} from "@nustackdev/ui-kit";
import type * as React from "react";
import { Fragment, useEffect, useRef } from "react";
import {
	docStrip,
	docStripColumn,
	docStripDrop,
	docStripGroup,
	docStripHandle,
} from "../../design";
import type { StripRow } from "../types";
import { LAYOUT_COLUMN, LAYOUT_ROW } from "./drag";
import { rowKey, sameShares, sharesOf } from "./model";

/** The narrowest a column may be dragged to, percent of the strip. */
const MIN_COLUMN = 15;

export function Strip({
	row,
	editable,
	dropAbove,
	renderCell,
	onResize,
}: {
	row: StripRow;
	editable: boolean;
	/** A drop would land right above it. */
	dropAbove: boolean;
	/** One cell's row, and anything the plane draws after it (an input line). */
	renderCell: (cell: string) => React.ReactNode;
	/** The columns resized: their new shares, summing to 1. */
	onResize: (shares: number[]) => void;
}) {
	const group = useRef<ResizablePanelGroupHandle | null>(null);
	const key = rowKey(row);
	const shares = row.columns.map((c) => c.share);
	const latest = useRef(shares);
	latest.current = shares;
	const sharesKey = shares.join(",");

	// The server's shares, laid on the group when they change.
	// biome-ignore lint/correctness/useExhaustiveDependencies: the shares are compared by their key.
	useEffect(() => {
		const g = group.current;
		if (!g || sameShares(sharesOf(g.getLayout()), latest.current)) return;
		g.setLayout(latest.current.map((s) => s * 100));
	}, [sharesKey]);

	const layout = (sizes: number[]) => {
		const next = sharesOf(sizes);
		if (!sameShares(next, latest.current)) onResize(next);
	};

	return (
		<div className={docStrip} {...{ [LAYOUT_ROW]: key }}>
			{dropAbove ? <span className={docStripDrop} /> : null}
			<ResizablePanelGroup
				ref={group}
				orientation="horizontal"
				className={docStripGroup}
				onLayout={layout}
			>
				{/* Flat: the group reads its panels and handles off its direct children. */}
				{row.columns.flatMap((column, k) => [
					k > 0 && editable ? (
						<ResizableHandle
							// biome-ignore lint/suspicious/noArrayIndexKey: a column is its place in the strip; its cells move between them.
							key={`handle-${k}`}
							className={docStripHandle}
							// Not a press for the pane's box selection.
							onPointerDown={(e) => e.stopPropagation()}
						/>
					) : null,
					<ResizablePanel
						// biome-ignore lint/suspicious/noArrayIndexKey: as the handle's.
						key={`column-${k}`}
						id={`strip-${key}-${k}`}
						defaultSize={column.share * 100}
						minSize={MIN_COLUMN}
						className={docStripColumn}
						{...{ [LAYOUT_COLUMN]: k }}
					>
						{column.cells.map((cell) => (
							<Fragment key={cell}>{renderCell(cell)}</Fragment>
						))}
					</ResizablePanel>,
				])}
			</ResizablePanelGroup>
		</div>
	);
}
