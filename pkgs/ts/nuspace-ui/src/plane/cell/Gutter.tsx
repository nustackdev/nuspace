// A cell's gutter: every affordance it has, hung outside the reading column.

import {
	IconButton,
	Toggle,
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Check, Code, GripVertical, Hash, Plus } from "lucide-react";
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
 * Every affordance a cell has, hung in the gutter outside the reading column.
 *
 * Three stacked rows of kit primitives, so they share a box, a hover tier, a
 * focus ring and one reveal. Top to bottom they read as what you do to the
 * cell, what you do with it, and what it is: add and drag, copy its id, open
 * its source next to the dot that says whether it is alive.
 *
 * Every glyph carries a tooltip and a label. A bare glyph in a margin is not
 * self-explanatory, and `title` is not an affordance, it is a delay.
 */
export function Gutter({
	cellId,
	editing,
	onSetEditing,
	onDrag,
	onPlus,
	onSelect,
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
	onDrag: (e: React.PointerEvent) => void;
	/** Open a line below this cell. Not a cell: see ../Ghost.tsx. */
	onPlus: () => void;
	onSelect: () => void;
}) {
	const [copied, setCopied] = useState(false);

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
			<span className={docStatusRail(state, pinned)} title={CELL_STATUS[state].label} />
			{/* Slower than the kit's 200ms, and with no instant reopen. The gutter
			    is a stack you walk THROUGH to reach one control, so at the kit's
			    delay a tooltip fires on every glyph you cross and lands portalled
			    over the cells below. 700ms is long enough that passing through
			    says nothing and resting says "tell me what this is"; the 0 skip
			    window is what stops the second and third from arriving instantly
			    once the first has spoken. Scoped here so the shell strip and the
			    rails keep the kit's snappier feel. */}
			<TooltipProvider delayDuration={700} skipDelayDuration={0}>
				<div className={docGutterAffordances(pinned)}>
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
						<Tooltip>
							<TooltipTrigger asChild>
								<IconButton
									variant="ghost"
									size="sm"
									aria-label="Drag to reorder, click to select"
									onPointerDown={onDrag}
									onClick={onSelect}
									data-cell-grip=""
									className={docDragHandle}
								>
									<GripVertical />
								</IconButton>
							</TooltipTrigger>
							<TooltipContent side="top">Drag to reorder, click to select</TooltipContent>
						</Tooltip>
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
			</TooltipProvider>
		</div>
	);
}
