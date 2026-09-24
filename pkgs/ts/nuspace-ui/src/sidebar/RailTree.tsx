// The rail's tree: the visible rows, the keyboard, the indent guides, and the
// phantom row a create types into.
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
// and open-and-reveal.

import { FileText } from "lucide-react";
import type * as React from "react";
import { useCallback, useMemo } from "react";
import { openPane, replacePane } from "../app/router";
import {
	railEmpty,
	railGuide,
	railGuideStyle,
	railIndent,
	railLane,
	railLaneStyle,
	railLeafIcon,
	railRow,
	railRowWrap,
} from "../design";
import type { Notify } from "./ops";
import { PlaneRow } from "./PlaneRow";
import { RailRowInput } from "./RailRowInput";
import { folds, type VisibleRow } from "./tree";
import { KIND_GROUP, type PageTree } from "./types";
import { useDraft } from "./useDraft";
import { useRailFocus } from "./useRailFocus";

export function RailTree({
	tree,
	rows,
	routes,
	selKey,
	onToggle,
	reveal,
	notify,
}: {
	tree: PageTree;
	rows: VisibleRow[];
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
	const { draft, startRename, startCreate, commitDraft, cancelDraft } = useDraft({
		reveal,
		notify,
		focusKey,
	});

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
					// Same contract as the click: a section only folds, a Plane
					// opens and reveals what is inside it. Cmd/ctrl opens a split.
					e.preventDefault();
					if (row.kind === KIND_GROUP) onToggle(row.key);
					else {
						if (row.hasKids) reveal(row.key);
						if (e.metaKey || e.ctrlKey) openPane(row.id);
						else replacePane(row.id);
					}
					break;
				case "F2":
					e.preventDefault();
					if (row.kind !== KIND_GROUP) startRename(row);
					break;
				default:
					break;
			}
		},
		[handleArrows, focusIndex, focusKey, onToggle, reveal, startRename],
	);

	return (
		<div role="tree" aria-label="Planes" ref={containerRef}>
			{rows.map((row, index) => (
				<div key={row.key} role="none">
					<div className={railRowWrap}>
						<Guides depth={row.depth} />
						<PlaneRow
							row={row}
							index={index}
							selected={row.key === selKey}
							open={routes.includes(row.id)}
							tabbable={row.key === tabKey}
							renaming={draft?.kind === "rename" && draft.key === row.key}
							onToggle={onToggle}
							reveal={reveal}
							onFocus={setActiveKey}
							onKeyDown={onKeyDown}
							onRename={startRename}
							onCreate={startCreate}
							onCommit={commitDraft}
							onCancel={cancelDraft}
							notify={notify}
							tree={tree}
						/>
					</div>
					{draft?.kind === "create" && draft.key === row.key ? (
						<div className={railRowWrap}>
							<Guides depth={row.depth + 1} />
							<div className={railRow(false)} style={railIndent(row.depth + 1)}>
								<span className={railLane} style={railLaneStyle}>
									<FileText className={railLeafIcon} aria-hidden="true" />
								</span>
								<RailRowInput
									initial={draft.initial}
									label="Title for the new Plane"
									onCommit={commitDraft}
									onCancel={cancelDraft}
								/>
							</div>
						</div>
					) : null}
					{/* Only under a section that is open and genuinely
					    empty. A folded one draws a row too, and
					    "nothing here yet" under a branch you just
					    folded shut is a lie. */}
					{row.kind === KIND_GROUP && row.open && !row.hasKids && draft?.key !== row.key ? (
						<p className={railEmpty}>nothing here yet</p>
					) : null}
				</div>
			))}
		</div>
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
