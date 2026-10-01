// Search: the popup the rail's search entry (./SearchTrigger.tsx) opens.
//
// The popup is the Add plane popup's pattern (./AddPlane.tsx): a kit
// `CommandPalette`, opened through a module level store (./search.ts), sending
// one sidebar op. Here the input is the query and the rows are what to search:
// plane titles, then every snippet the space registered with a search, as the
// server seeded them (`searchable`). A row click ticks or unticks it; Enter or
// the button sends `search.run` and opens the search Plane, which shows the
// newest search.
//
// Nothing is filtered: the rows are the whole list, whatever is typed.

import {
	Button,
	Checkbox,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
	CommandPalette,
	Shortcut,
	useCommandPaletteHotkey,
} from "@nustackdev/ui-kit";
import { useState } from "react";
import { replacePane } from "../core/router";
import { searchFooter, searchHint, searchItem } from "../design";
import type { Notify } from "./ops";
import {
	closeSearch,
	SEARCH_PLANE,
	TITLES,
	toggleKind,
	useSearchOpen,
	useSearchSetter,
	useUnticked,
} from "./search";
import type { Searchable } from "./types";

export function SearchPopup({ searchable, notify }: { searchable: Searchable[]; notify: Notify }) {
	const open = useSearchOpen();
	const unticked = useUnticked();
	const [query, setQuery] = useState("");
	useCommandPaletteHotkey(useSearchSetter());

	const kinds: Searchable[] = [{ name: TITLES, label: "Titles" }, ...searchable];
	const ticked = (name: string) => !unticked.has(name);
	const snippets = searchable.filter((s) => ticked(s.name)).map((s) => s.name);
	const titles = ticked(TITLES);
	const ready = query.trim() !== "" && (titles || snippets.length > 0);

	const submit = () => {
		if (!ready) return;
		closeSearch();
		setQuery("");
		notify("search.run", { query: query.trim(), snippets, titles });
		replacePane(SEARCH_PLANE);
	};

	return (
		<CommandPalette
			open={open}
			onOpenChange={(next) => {
				if (!next) closeSearch();
			}}
			label="Search"
			shouldFilter={false}
		>
			<CommandInput
				placeholder="Search"
				value={query}
				onValueChange={setQuery}
				onKeyDown={(e) => {
					// Enter searches. Taken before the palette's own Enter, which
					// would tick the highlighted row instead.
					if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
					e.preventDefault();
					submit();
				}}
			/>
			<CommandList>
				<CommandGroup heading="Look in">
					{kinds.map((kind) => (
						<CommandItem
							key={kind.name || "titles"}
							value={kind.name || "titles"}
							onSelect={() => toggleKind(kind.name)}
							className={searchItem}
						>
							{/* The row is the control: the box only shows its state. */}
							<Checkbox checked={ticked(kind.name)} tabIndex={-1} aria-hidden="true" />
							<span>{kind.label}</span>
						</CommandItem>
					))}
				</CommandGroup>
			</CommandList>
			<div className={searchFooter}>
				<span className={searchHint}>
					<Shortcut keys={["enter"]} size="sm" /> to search
				</span>
				<Button size="sm" disabled={!ready} onClick={submit}>
					Search
				</Button>
			</div>
		</CommandPalette>
	);
}
