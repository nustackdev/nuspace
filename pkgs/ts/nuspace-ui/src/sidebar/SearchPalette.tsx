// Search: the popup the rail's search entry (./SearchTrigger.tsx) opens.
//
// The popup is the Add plane popup's pattern (./AddPlane.tsx): a kit
// `CommandPalette`, opened through a module level store (./search.ts), sending
// one sidebar op. Here the input is the query and the rows are where to look:
// an All row, plane titles, then every snippet the space registered with a
// search, as the server seeded them (`searchable`), folded under their groups.
// Enter or the button sends `search.run` and opens the search Plane, which
// shows the newest search.
//
// Nothing is filtered: the input is the query, never a filter on the rows.
// So the keys that edit text stay the input's, and the rows take the rest:
// the arrows move, Tab ticks or unticks the lit row (a group's or the All
// row's box ticks every kind under it), Left and Right fold and unfold the
// lit group. A click ticks a row; a click on a chevron folds.

import {
	Button,
	Checkbox,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
	CommandPalette,
	CommandSeparator,
	Shortcut,
	useCommandPaletteHotkey,
} from "@nustackdev/ui-kit";
import { ChevronRight } from "lucide-react";
import type * as React from "react";
import { useState } from "react";
import { replacePane } from "../core/router";
import {
	searchChevron,
	searchChildItem,
	searchCount,
	searchDescription,
	searchFooter,
	searchGroupItem,
	searchHint,
	searchItem,
	searchKeys,
	searchLabel,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { type Icon, parseIcon } from "../icon/parse";
import type { Notify } from "./ops";
import {
	closeSearch,
	FOLD_OVER,
	SEARCH_PLANE,
	searchGroups,
	setFold,
	setKinds,
	TITLES,
	type Tick,
	tickOf,
	toggleKind,
	useFolds,
	useSearchOpen,
	useSearchSetter,
	useUnticked,
} from "./search";
import type { Searchable } from "./types";

/** The glyph a snippet that names none shows, as in the / menu. */
const SNIPPET_ICON: Icon = { kind: "lucide", name: "square-terminal" };

/** What a row is, by its cmdk value: what Tab and the arrows act on. */
type Row =
	| { kind: "all" }
	| { kind: "titles" }
	| { kind: "group"; heading: string; names: string[] }
	| { kind: "snippet"; name: string; group: string | null };

const ALL_ROW = "all";
const TITLES_ROW = "titles";
const groupRow = (heading: string) => `group:${heading}`;
const snippetRow = (name: string) => `snippet:${name}`;

export function SearchPopup({ searchable, notify }: { searchable: Searchable[]; notify: Notify }) {
	const open = useSearchOpen();
	const unticked = useUnticked();
	const folds = useFolds();
	const [query, setQuery] = useState("");
	// The lit row, held here so Tab and the arrows know what they act on.
	const [lit, setLit] = useState("");
	useCommandPaletteHotkey(useSearchSetter());

	const groups = searchGroups(searchable);
	const grouped = groups.some((g) => g.heading !== null);
	const folded = (heading: string) => folds.get(heading) ?? searchable.length > FOLD_OVER;
	const every = [TITLES, ...searchable.map((s) => s.name)];
	const ticked = (name: string) => !unticked.has(name);
	const snippets = searchable.filter((s) => ticked(s.name)).map((s) => s.name);
	const titles = ticked(TITLES);
	const on = (titles ? 1 : 0) + snippets.length;
	const ready = query.trim() !== "" && on > 0;

	const rows = new Map<string, Row>([
		[ALL_ROW, { kind: "all" }],
		[TITLES_ROW, { kind: "titles" }],
	]);
	for (const g of groups) {
		if (g.heading !== null) {
			rows.set(groupRow(g.heading), {
				kind: "group",
				heading: g.heading,
				names: g.items.map((s) => s.name),
			});
		}
		for (const s of g.items)
			rows.set(snippetRow(s.name), { kind: "snippet", name: s.name, group: g.heading });
	}

	const toggle = (row: Row) => {
		if (row.kind === "all") setKinds(every, tickOf(every, unticked) !== true);
		else if (row.kind === "titles") toggleKind(TITLES);
		else if (row.kind === "group") setKinds(row.names, tickOf(row.names, unticked) !== true);
		else toggleKind(row.name);
	};

	/** Left folds the lit group, or the group of the lit snippet and lights it.
	 *  Right unfolds the lit group, or steps into it once open. */
	const fold = (row: Row, key: "ArrowLeft" | "ArrowRight"): boolean => {
		if (row.kind === "group") {
			const shut = folded(row.heading);
			if (key === "ArrowLeft" && !shut) setFold(row.heading, true);
			else if (key === "ArrowRight" && shut) setFold(row.heading, false);
			else if (key === "ArrowRight" && row.names[0]) setLit(snippetRow(row.names[0]));
			return true;
		}
		if (row.kind === "snippet" && row.group !== null && key === "ArrowLeft") {
			setFold(row.group, true);
			setLit(groupRow(row.group));
			return true;
		}
		return false;
	};

	const submit = () => {
		if (!ready) return;
		closeSearch();
		setQuery("");
		notify("search.run", { query: query.trim(), snippets, titles });
		replacePane(SEARCH_PLANE);
	};

	const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.nativeEvent.isComposing) return;
		const row = rows.get(lit);
		// Enter searches. Taken before the palette's own Enter, which would
		// tick the lit row instead.
		if (e.key === "Enter") {
			e.preventDefault();
			submit();
		} else if (e.key === "Tab" && !e.metaKey && !e.ctrlKey && !e.altKey) {
			e.preventDefault();
			if (row) toggle(row);
		} else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && !e.shiftKey && row) {
			// Only a group or a snippet in one takes the arrows: anywhere else
			// they move the caret.
			if (fold(row, e.key)) e.preventDefault();
		}
	};

	const snippet = (s: Searchable, indent: boolean) => (
		<CommandItem
			key={s.name}
			value={snippetRow(s.name)}
			onSelect={() => toggleKind(s.name)}
			className={indent ? searchChildItem : searchItem}
		>
			<Box tick={ticked(s.name)} />
			<PlaneIcon icon={parseIcon(s.icon) ?? SNIPPET_ICON} />
			<span className={searchLabel}>{s.label}</span>
			{s.description ? <span className={searchDescription}>{s.description}</span> : null}
		</CommandItem>
	);

	return (
		<CommandPalette
			open={open}
			onOpenChange={(next) => {
				if (!next) closeSearch();
			}}
			label="Search"
			shouldFilter={false}
			value={lit}
			onValueChange={setLit}
		>
			<CommandInput
				placeholder="Search"
				value={query}
				onValueChange={setQuery}
				onKeyDown={onKeyDown}
			/>
			<CommandList className="max-h-[26rem]">
				<CommandGroup heading="Look in">
					<CommandItem
						value={ALL_ROW}
						onSelect={() => toggle({ kind: "all" })}
						className={searchItem}
					>
						<Box tick={tickOf(every, unticked)} />
						<span className={searchLabel}>Everywhere</span>
						<span className={searchCount}>
							{on} of {every.length}
						</span>
					</CommandItem>
					<CommandItem
						value={TITLES_ROW}
						onSelect={() => toggleKind(TITLES)}
						className={searchItem}
					>
						<Box tick={titles} />
						<span className={searchLabel}>Plane titles</span>
					</CommandItem>
				</CommandGroup>
				{searchable.length > 0 ? <CommandSeparator /> : null}
				{grouped ? (
					<CommandGroup heading="Snippets">
						{groups.map((g) => {
							const heading = g.heading ?? "";
							const names = g.items.map((s) => s.name);
							const shut = folded(heading);
							const count = names.filter(ticked).length;
							return [
								<CommandItem
									key={groupRow(heading)}
									value={groupRow(heading)}
									onSelect={() => setKinds(names, tickOf(names, unticked) !== true)}
									className={searchGroupItem}
									aria-expanded={!shut}
								>
									{/* The chevron folds; the rest of the row ticks. */}
									<span
										className={searchChevron}
										data-open={!shut}
										onClick={(e) => {
											e.stopPropagation();
											setFold(heading, !shut);
										}}
										aria-hidden="true"
									>
										<ChevronRight />
									</span>
									<Box tick={tickOf(names, unticked)} />
									<span className={searchLabel}>{heading}</span>
									<span className={searchCount}>
										{count}/{names.length}
									</span>
								</CommandItem>,
								...(shut ? [] : g.items.map((s) => snippet(s, true))),
							];
						})}
					</CommandGroup>
				) : searchable.length > 0 ? (
					<CommandGroup heading="Snippets">{searchable.map((s) => snippet(s, false))}</CommandGroup>
				) : null}
			</CommandList>
			<div className={searchFooter}>
				<span className={searchKeys}>
					<span className={searchHint}>
						<Shortcut keys={["up"]} size="sm" />
						<Shortcut keys={["down"]} size="sm" />
						Move
					</span>
					<span className={searchHint}>
						<Shortcut keys={["tab"]} size="sm" />
						Tick
					</span>
					{grouped ? (
						<span className={searchHint}>
							<Shortcut keys={["left"]} size="sm" />
							<Shortcut keys={["right"]} size="sm" />
							Fold
						</span>
					) : null}
					<span className={searchHint}>
						<Shortcut keys={["enter"]} size="sm" />
						Search
					</span>
				</span>
				<Button size="sm" disabled={!ready} onClick={submit}>
					Search
				</Button>
			</div>
		</CommandPalette>
	);
}

/** A row's box. The row is the control: the box only shows its state. */
function Box({ tick }: { tick: Tick }) {
	return <Checkbox checked={tick} tabIndex={-1} aria-hidden="true" />;
}
