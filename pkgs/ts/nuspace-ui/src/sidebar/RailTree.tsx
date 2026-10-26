// The rail's tree: the visible rows, the keyboard, and where a dragged row
// would land.
//
// ## The interaction model
//
// Two affordances, two jobs, no overlap:
//
//   * **the row navigates and reveals.** Opening a Plane that has children
//     shows them. It never hides them - a click that sometimes opens and
//     sometimes closes, depending on where you happened to be standing, is
//     what made this feel broken. Reveal is idempotent.
//   * **the chevron only folds.** It toggles both ways and never navigates,
//     so you can look inside a branch without leaving the Plane you are
//     reading. It shows in the icon's place while the row is hovered. Every
//     plane folds, leaf or not; an open leaf shows "No planes inside".
//
// The rows are flat siblings, never nested in each other's DOM, so a row's
// `group/row` hover is its own and hovering a child leaves its parent alone.
//
// No indent guides: the indent alone carries the depth, and a hairline per
// level was the loudest thing in a quiet rail.
//
// The tree's rows are in the rail body's one tab stop (./useRailFocus.ts),
// which owns the by-key focus and the four moves across every section. What
// this adds on top is the two arrows that fold and open-and-reveal. Drag and drop is ./useRailDrag.ts; this draws its
// insertion line and its target, and drops them once the drag leaves for the
// pinned rows.

import { EmptyState } from "@nustackdev/ui-kit";
import type * as React from "react";
import { Fragment, useCallback } from "react";
import { openBeside, openHere } from "../core/router";
import {
	railDragging,
	railDropInto,
	railDropLine,
	railDropLineStyle,
	railDropTail,
	railIndent,
	railNoPlanes,
	railRowWrap,
	railTreeList,
} from "../design";
import { planeIcon } from "../icon/parse";
import type { Notify } from "./ops";
import { PlaneRow } from "./PlaneRow";
import type { Pins } from "./pin";
import { showsNoPlanes, type VisibleRow } from "./tree";
import type { PlaneTree } from "./types";
import { useDraft } from "./useDraft";
import { useRailDrag } from "./useRailDrag";
import { useRailNav } from "./useRailFocus";

export function RailTree({
	tree,
	rows,
	routes,
	selKey,
	onToggle,
	reveal,
	notify,
	pins,
}: {
	tree: PlaneTree;
	rows: VisibleRow[];
	routes: string[];
	/** The focused pane's Plane, which is the cursor. */
	selKey: string;
	onToggle: (key: string) => void;
	reveal: (key: string) => void;
	notify: Notify;
	pins: Pins;
}) {
	const { tabKey, setActiveKey, focusKey, arrows } = useRailNav();
	const { draft, startRename, commitDraft, cancelDraft } = useDraft({ notify, focusKey });
	const { dragKey, target, rowProps, tailProps, leaveProps } = useRailDrag({
		tree,
		rows,
		notify,
		reveal,
	});

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent, row: VisibleRow, index: number) => {
			if (arrows(e, row.key)) return;
			switch (e.key) {
				case "ArrowRight":
					// Unfold a folded row; step into an open one's first child.
					e.preventDefault();
					if (!row.open) onToggle(row.key);
					else if (row.hasKids && rows[index + 1]) focusKey(rows[index + 1].key);
					break;
				case "ArrowLeft":
					// Fold an open row; otherwise climb to the parent.
					e.preventDefault();
					if (row.open) onToggle(row.key);
					else if (row.parent !== null) focusKey(row.parent);
					break;
				case "Enter":
				case " ":
					// Same contract as the click: open it and reveal what is
					// inside it. With Option, beside the others, like an
					// Option-click.
					e.preventDefault();
					if (row.hasKids) reveal(row.key);
					if (e.altKey && e.key === "Enter") openBeside(row.id);
					else openHere(row.id);
					break;
				default:
					break;
			}
		},
		[arrows, rows, focusKey, onToggle, reveal],
	);

	return (
		// `contents`: a box for the drag's leave only, the rows and the tail
		// stay laid out by the rail's scroll body.
		<div className="contents" data-rail-tree="" {...leaveProps}>
			<div role="tree" aria-label="Planes" className={railTreeList}>
				{rows.map((row, index) => {
					const aimed = target?.key === row.key ? target.edge : null;
					return (
						<Fragment key={row.key}>
							<div role="none" className={railRowWrap}>
								<PlaneRow
									row={row}
									index={index}
									icon={planeIcon(row.icon)}
									selected={row.key === selKey}
									open={routes.includes(row.id)}
									tabbable={row.key === tabKey}
									renaming={draft?.key === row.key}
									drag={rowProps(row.key)}
									dragging={dragKey !== null}
									className={
										aimed === "into" ? railDropInto : dragKey === row.key ? railDragging : undefined
									}
									onToggle={onToggle}
									reveal={reveal}
									onFocus={setActiveKey}
									onKeyDown={onKeyDown}
									onRename={startRename}
									onCommit={commitDraft}
									onCancel={cancelDraft}
									notify={notify}
									tree={tree}
									pins={pins}
								/>
								{aimed === "before" || aimed === "after" ? (
									<span
										className={railDropLine(aimed)}
										style={railDropLineStyle(row.depth)}
										aria-hidden="true"
									/>
								) : null}
							</div>
							{showsNoPlanes(row) ? (
								<EmptyState
									role="none"
									size="sm"
									className={railNoPlanes}
									style={railIndent(row.depth + 1)}
								>
									No planes inside
								</EmptyState>
							) : null}
						</Fragment>
					);
				})}
				{rows.length === 0 ? <EmptyState size="sm">Nothing here yet</EmptyState> : null}
			</div>
			{/* The rest of the rail: a drop here goes to the top level, last. */}
			<div className={railDropTail} {...tailProps}>
				{target?.key === "" ? (
					<span className={railDropLine("before")} style={railDropLineStyle(0)} />
				) : null}
			</div>
		</div>
	);
}
