// The slash menu.
//
// Opened from a ghost input -- the not-yet-a-block line at the end of the
// page, or the one a gutter `+` summons. One row per registered snippet, in
// registry order, and nothing else: picking a row makes a block from that
// snippet. Focus stays in the ghost's own input (moving it would lose the
// query), so this component has no keyboard of its own: it draws a list and
// reports clicks, and the ghost forwards arrow/enter/escape.

import { SquareTerminal } from "lucide-react";
import { useEffect, useRef } from "react";
import {
	docSlashMenu,
	docSlashMenuHint,
	docSlashMenuItem,
	docSlashMenuItemLabel,
} from "../../design";
import type { SlashSnippet } from "./state";

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

	if (items.length === 0) return null;

	const top = Math.min(anchor.y + 6, window.innerHeight - 300);
	const left = Math.min(anchor.x, window.innerWidth - 280);

	return (
		<div ref={ref} className={`${docSlashMenu} fixed outline-none`} style={{ top, left }}>
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
					data-selected={i === index}
					className={docSlashMenuItem}
				>
					<SquareTerminal aria-hidden="true" />
					<span className={docSlashMenuItemLabel}>{item.label}</span>
					<span className={docSlashMenuHint}>{item.name}</span>
				</button>
			))}
		</div>
	);
}
