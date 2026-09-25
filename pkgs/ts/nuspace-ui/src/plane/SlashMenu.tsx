// The slash menu.
//
// Opened from a ghost input -- the not-yet-a-cell line at the end of the
// plane, or the one a gutter `+` summons. One row per registered snippet, in
// registry order, and nothing else: picking a row makes a cell from that
// snippet. Focus stays in the ghost's own input (moving it would lose the
// query), so this component has no keyboard of its own: it draws a list and
// reports clicks, and the ghost forwards arrow/enter/escape. It wears the
// kit's menu classes, so it looks like every other menu without being one.

import { EmptyState, menuItemClasses, menuShortcutClasses } from "@nustackdev/ui-kit";
import { SquareTerminal } from "lucide-react";
import { useEffect, useRef } from "react";
import { docSlashMenu, docSlashMenuItemLabel } from "../design";
import type { SlashSnippet } from "./types";

/** The menu's rows, narrowed by what has been typed. */
export function filterSlash(query: string, items: SlashSnippet[]): SlashSnippet[] {
	const q = query.trim().toLowerCase();
	if (!q) return items;
	return items.filter((i) => i.label.toLowerCase().includes(q) || i.name.toLowerCase().includes(q));
}

export function SlashMenu({
	items,
	index,
	anchor,
	onPick,
	onMove,
}: {
	items: SlashSnippet[];
	index: number;
	anchor: { x: number; y: number };
	onPick: (item: SlashSnippet) => void;
	onMove: (delta: number) => void;
}) {
	const ref = useRef<HTMLDivElement | null>(null);

	// Keep the highlighted row visible while filtering narrows the list.
	useEffect(() => {
		ref.current
			?.querySelector<HTMLElement>(`[data-slash-index="${index}"]`)
			?.scrollIntoView({ block: "nearest" });
	}, [index]);

	const top = Math.min(anchor.y + 6, window.innerHeight - 300);
	const left = Math.min(anchor.x, window.innerWidth - 280);

	return (
		<div ref={ref} className={docSlashMenu} style={{ top, left }}>
			{items.length === 0 ? <EmptyState size="sm">Nothing matches</EmptyState> : null}
			{items.map((item, i) => (
				<button
					key={item.name}
					type="button"
					data-slash-index={i}
					onMouseDown={(e) => {
						// mousedown, not click: click would land after the
						// input's blur has already collapsed the caret.
						e.preventDefault();
						onPick(item);
					}}
					onMouseEnter={() => onMove(i - index)}
					data-highlighted={i === index ? "" : undefined}
					className={`${menuItemClasses} w-full`}
				>
					<SquareTerminal aria-hidden="true" />
					<span className={docSlashMenuItemLabel}>{item.label}</span>
					<span className={menuShortcutClasses}>{item.name}</span>
				</button>
			))}
		</div>
	);
}
