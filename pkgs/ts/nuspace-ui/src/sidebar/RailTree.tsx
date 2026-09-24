// The rail's tree: the visible rows, the keyboard, the indent guides, and
// where a dragged row would land.
//
// ## The interaction model
//
// Two affordances, two jobs, no overlap:
//
//   * **the row navigates and reveals.** Opening a Plane that has children
//     shows them. It never hides them - a click that sometimes opens and
//     sometimes closes, depending on where you happened to be standing, is
//     what made this feel broken. Reveal is idempotent.
//   * **the twisty only folds.** It toggles both ways and never navigates, so
//     you can look inside a branch without leaving the Plane you are reading.
//
// The tree is one tab stop; `useRailFocus` owns the tab stop, the by-key
// focus and the four moves. What this adds on top is the two arrows that fold
// and open-and-reveal. Drag and drop is ./useRailDrag.ts; this draws its
// insertion line and its target.

import type * as React from "react";
import { useCallback, useEffect, useMemo } from "react";
import { openPane, replacePane } from "../core/router";
import {
	railDragging,
	railDropInto,
	railDropLine,
	railDropLineStyle,
	railDropTail,
	railEmpty,
	railGuide,
	railGuideStyle,
	railRowWrap,
} from "../design";
import { clearPendingRename, usePendingRename } from "./add";
import { iconFor } from "./icons";
import type { Notify } from "./ops";
import { PlaneRow } from "./PlaneRow";
import { folds, type VisibleRow } from "./tree";
import type { PlaneTree, Registered } from "./types";
import { useDraft } from "./useDraft";
import { useRailDrag } from "./useRailDrag";
import { useRailFocus } from "./useRailFocus";

export function RailTree({
	tree,
	rows,
	registered,
	routes,
	selKey,
	onToggle,
	reveal,
	notify,
}: {
	tree: PlaneTree;
	rows: VisibleRow[];
	registered: Registered[];
	routes: string[];
	/** The focused pane's Plane, which is the cursor. */
	selKey: string;
	onToggle: (key: string) => void;
	reveal: (key: string) => void;
	notify: Notify;
}) {
	const keys = useMemo(() => rows.map((r) => r.key), [rows]);
	const { containerRef, tabKey, setActiveKey, focusKey, focusIndex, handleArrows } = useRailFocus(
		keys,
		selKey,
	);
	const { draft, startRename, commitDraft, cancelDraft } = useDraft({ notify, focusKey });
	const { dragKey, target, rowProps, tailProps } = useRailDrag({ tree, rows, notify, reveal });

	// A Plane made from the Add plane popup is renamed as soon as its row shows.
	const pending = usePendingRename();
	useEffect(() => {
		if (!pending) return;
		const row = rows.find((r) => r.key === pending);
		if (!row) return;
		clearPendingRename();
		startRename(row);
	}, [pending, rows, startRename]);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent, row: VisibleRow, index: number) => {
			if (handleArrows(e, index)) return;
			const foldable = folds(row);
			switch (e.key) {
				case "ArrowRight":
					// Open a folded branch; step into an open one.
					e.preventDefault();
					if (foldable && !row.open) onToggle(row.key);
					else if (row.hasKids) focusIndex(index + 1);
					break;
				case "ArrowLeft":
					// Fold an open branch; otherwise climb to the parent.
					e.preventDefault();
					if (foldable && row.open) onToggle(row.key);
					else if (row.parent !== null) focusKey(row.parent);
					break;
				case "Enter":
				case " ":
					// Same contract as the click: open it and reveal what is
					// inside it. Cmd/ctrl opens a split.
					e.preventDefault();
					if (row.hasKids) reveal(row.key);
					if (e.metaKey || e.ctrlKey) openPane(row.id);
					else replacePane(row.id);
					break;
				case "F2":
					e.preventDefault();
					startRename(row);
					break;
				default:
					break;
			}
		},
		[handleArrows, focusIndex, focusKey, onToggle, reveal, startRename],
	);

	return (
		<>
			<div role="tree" aria-label="Planes" ref={containerRef}>
				{rows.map((row, index) => {
					const aimed = target?.key === row.key ? target.edge : null;
					return (
						<div key={row.key} role="none" className={railRowWrap}>
							<Guides depth={row.depth} />
							<PlaneRow
								row={row}
								index={index}
								icon={iconFor(registered, row.made_by)}
								selected={row.key === selKey}
								open={routes.includes(row.id)}
								tabbable={row.key === tabKey}
								renaming={draft?.key === row.key}
								drag={rowProps(row.key)}
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
							/>
							{aimed === "before" || aimed === "after" ? (
								<span
									className={railDropLine(aimed)}
									style={railDropLineStyle(row.depth)}
									aria-hidden="true"
								/>
							) : null}
						</div>
					);
				})}
				{rows.length === 0 ? <p className={railEmpty}>Nothing here yet</p> : null}
			</div>
			{/* The rest of the rail: a drop here goes to the top level, last. */}
			<div className={railDropTail} {...tailProps}>
				{target?.key === "" ? (
					<span className={railDropLine("before")} style={railDropLineStyle(0)} />
				) : null}
			</div>
		</>
	);
}

/**
 * One hairline per crossed level, running down the ancestors' twisty lanes.
 *
 * Levels start at 1, not 0: a guide marking the top level's lane carries no
 * information and only reads as a second rail border. A depth-1 row therefore
 * gets no guide at all.
 */
function Guides({ depth }: { depth: number }) {
	if (depth < 2) return null;
	return (
		<>
			{Array.from({ length: depth - 1 }, (_, i) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: the index IS the level
				<span key={i} className={railGuide} style={railGuideStyle(i + 1)} aria-hidden="true" />
			))}
		</>
	);
}
