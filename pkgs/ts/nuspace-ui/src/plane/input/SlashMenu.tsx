// The slash menu: a command box over the plane.
//
// Opened from a ghost input -- the not-yet-a-cell line at the end of the
// plane, or the one a gutter `+` summons. The empty program on top, then the
// registered Cells in sections (./slash.ts says which and in what order),
// each row an icon, a label and what a cell made from it is for. Picking a
// row makes a cell from it. Focus stays in the ghost's own input (moving it would
// lose the query), so this component has no keyboard of its own: it draws
// and reports clicks, and the ghost forwards arrow/enter/escape. It wears
// the kit's command palette recipes, so it reads as one without being one.
//
// Over the sections, the packages (../../menu/rank.ts): nuverse's rows on
// top, every other package a title, open while the lit row is in it. The
// arrows step every row, folded or not, so a folded package's rows stay
// drawn, hidden; a click on a title lights its first row.

import { EmptyState, Popover, PopoverAnchor, PopoverContent } from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { docSlashList, docSlashMenu, menuHeading, menuItem, menuPackage } from "../../design";
import { MenuEntry, MenuKeys, PackageEntry } from "../../menu/Entry";
import type { SlashAnchor } from "../state";
import type { CellSpec } from "../types";
import { slashItems, slashPackages } from "./slash";

/** The glyph a Cell that names none shows. */
const CELL_ICON = { kind: "lucide", name: "square-terminal" } as const;

/** Gap from the line, and the least room kept to the window's edge. */
const GAP = 6;
const EDGE = 12;

export function SlashMenu({
	query,
	cellSpecs,
	index,
	anchor,
	onPick,
	onMove,
	onClose,
}: {
	query: string;
	/** Every registered Cell: the menu sections them for `query` itself. */
	cellSpecs: CellSpec[];
	index: number;
	anchor: SlashAnchor;
	onPick: (item: CellSpec) => void;
	onMove: (delta: number) => void;
	/** A press outside both the menu and its line. */
	onClose: () => void;
}) {
	const ref = useRef<HTMLDivElement | null>(null);
	const packages = slashPackages(query, cellSpecs, slashItems(query, cellSpecs)[index]?.name);

	// Keep the highlighted row visible while filtering narrows the list.
	useEffect(() => {
		ref.current
			?.querySelector<HTMLElement>(`[data-slash-index="${index}"]`)
			?.scrollIntoView({ block: "nearest" });
	}, [index]);

	let at = 0;
	// One stop: lit when the arrows are on it, lit by hover too.
	const stop = () => {
		const i = at++;
		const lit = i === index;
		return {
			role: "option",
			"aria-selected": lit,
			tabIndex: -1,
			"data-slash-index": i,
			"data-selected": lit,
			onMouseMove: () => {
				if (!lit) onMove(i - index);
			},
		} as const;
	};

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
				// Escape is the line's, like every other key here: the line knows
				// whether it closes the menu or takes a stand-in back home.
				onEscapeKeyDown={(e) => e.preventDefault()}
				onCloseAutoFocus={(e) => e.preventDefault()}
				onInteractOutside={(e) => {
					if (e.target instanceof Node && anchor.contains(e.target)) e.preventDefault();
				}}
				// Every press in here would blur the ghost and close the menu.
				onMouseDown={(e) => e.preventDefault()}
			>
				<div className={docSlashList}>
					{packages.length === 0 ? (
						<EmptyState size="sm">Nothing matches “{query.trim()}”</EmptyState>
					) : null}
					{packages.map((pkg) => {
						const first = at;
						return (
							<div key={pkg.key ?? `_${pkg.sections[0]?.items[0]?.name}`}>
								{pkg.key === null ? null : (
									// A title, not a stop: a click lights its first row, which opens it.
									// biome-ignore lint/a11y/useKeyWithClickEvents lint/a11y/noStaticElementInteractions: the arrows reach the same rows
									<div
										data-open={pkg.open}
										onClick={() => onMove(first - index)}
										className={menuPackage}
									>
										<PackageEntry {...pkg} />
									</div>
								)}
								<div hidden={!pkg.open}>
									{pkg.sections.map((section) => (
										// The pinned program and an ungrouped list are both headless.
										<div key={section.heading ?? `_${section.items[0]?.name}`}>
											{section.heading ? (
												<div className={menuHeading}>{section.heading}</div>
											) : null}
											{section.items.map((item) => (
												<button
													key={item.name}
													type="button"
													{...stop()}
													onClick={() => onPick(item)}
													className={menuItem}
												>
													<MenuEntry
														icon={item.icon}
														fallback={CELL_ICON}
														label={item.label}
														description={item.description}
														query={query}
													/>
												</button>
											))}
										</div>
									))}
								</div>
							</div>
						);
					})}
				</div>
				{packages.length === 0 ? null : <MenuKeys action="Insert" />}
			</PopoverContent>
		</Popover>
	);
}
