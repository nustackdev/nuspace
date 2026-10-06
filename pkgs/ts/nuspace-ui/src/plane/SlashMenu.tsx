// The slash menu: a command box over the plane.
//
// Opened from a ghost input -- the not-yet-a-cell line at the end of the
// plane, or the one a gutter `+` summons. The registered snippets, in
// sections (./slash.ts says which and in what order), each row an icon,
// a label and what a cell made from it is for. Picking a row makes a cell
// from that snippet. Focus stays in the ghost's own input (moving it would
// lose the query), so this component has no keyboard of its own: it draws
// and reports clicks, and the ghost forwards arrow/enter/escape. It wears
// the kit's command palette recipes, so it reads as one without being one.

import { EmptyState, Popover, PopoverAnchor, PopoverContent } from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { docSlashList, docSlashMenu, menuHeading, menuItem } from "../design";
import { MenuEntry, MenuKeys } from "../menu/Entry";
import { menuSections } from "../menu/rank";
import type { SlashAnchor } from "./state";
import type { SlashSnippet } from "./types";

/** The glyph a snippet that names none shows. */
const SNIPPET_ICON = { kind: "lucide", name: "square-terminal" } as const;

/** Gap from the line, and the least room kept to the window's edge. */
const GAP = 6;
const EDGE = 12;

export function SlashMenu({
	query,
	snippets,
	index,
	anchor,
	onPick,
	onMove,
	onClose,
}: {
	query: string;
	/** Every registered snippet: the menu sections them for `query` itself. */
	snippets: SlashSnippet[];
	index: number;
	anchor: SlashAnchor;
	onPick: (item: SlashSnippet) => void;
	onMove: (delta: number) => void;
	/** A press outside both the menu and its line. */
	onClose: () => void;
}) {
	const ref = useRef<HTMLDivElement | null>(null);
	const sections = menuSections(query, snippets);

	// Keep the highlighted row visible while filtering narrows the list.
	useEffect(() => {
		ref.current
			?.querySelector<HTMLElement>(`[data-slash-index="${index}"]`)
			?.scrollIntoView({ block: "nearest" });
	}, [index]);

	let at = 0;

	// A kit popover pinned to the ghost's input: it follows the line as the
	// page scrolls, and flips above it when the room below runs short. The
	// caret never leaves the input, so the popover takes no focus, on open
	// or on close, and a press back in the input is not a press outside.
	return (
		<Popover open onOpenChange={(open) => (open ? undefined : onClose())}>
			<PopoverAnchor virtualRef={{ current: anchor }} />
			<PopoverContent
				ref={ref}
				role="listbox"
				aria-label="Insert a cell"
				side="bottom"
				align="start"
				sideOffset={GAP}
				collisionPadding={EDGE}
				className={docSlashMenu}
				onOpenAutoFocus={(e) => e.preventDefault()}
				onCloseAutoFocus={(e) => e.preventDefault()}
				onInteractOutside={(e) => {
					if (e.target instanceof Node && anchor.contains(e.target)) e.preventDefault();
				}}
				// Every press in here would blur the ghost and close the menu.
				onMouseDown={(e) => e.preventDefault()}
			>
				<div className={docSlashList}>
					{sections.length === 0 ? (
						<EmptyState size="sm">Nothing matches “{query.trim()}”</EmptyState>
					) : null}
					{sections.map((section) => (
						<div key={section.heading ?? ""}>
							{section.heading ? <div className={menuHeading}>{section.heading}</div> : null}
							{section.items.map((item) => {
								const i = at++;
								const lit = i === index;
								return (
									<button
										key={item.name}
										type="button"
										role="option"
										aria-selected={lit}
										tabIndex={-1}
										data-slash-index={i}
										data-selected={lit}
										onClick={() => onPick(item)}
										onMouseMove={() => {
											if (!lit) onMove(i - index);
										}}
										className={menuItem}
									>
										<MenuEntry
											icon={item.icon}
											fallback={SNIPPET_ICON}
											label={item.label}
											description={item.description}
											query={query}
										/>
									</button>
								);
							})}
						</div>
					))}
				</div>
				{sections.length === 0 ? null : <MenuKeys action="Insert" />}
			</PopoverContent>
		</Popover>
	);
}
