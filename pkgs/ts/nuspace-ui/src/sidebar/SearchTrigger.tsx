// The rail's search entry, under the top bar: a row that opens the search
// popup (./SearchPalette.tsx), with the shortcut that opens it from anywhere.
//
// It is nuspace's own, not a kit control dressed as an input: it is laid out
// like a flat plane row (design/rail.ts, `railSearchTrigger`), so the top bar
// and the search entry read as one quiet group over the divider.

import { Kbd } from "@nustackdev/ui-kit";
import { Search as SearchIcon } from "lucide-react";
import {
	railSearch,
	railSearchHint,
	railSearchIcon,
	railSearchText,
	railSearchTrigger,
} from "../design";
import { openSearch, SEARCH_SHORTCUT } from "./search";

export function SearchTrigger() {
	return (
		<div className={railSearch}>
			<button
				type="button"
				className={railSearchTrigger}
				aria-keyshortcuts="Meta+K Control+K"
				onClick={openSearch}
			>
				<span className={railSearchIcon} aria-hidden="true">
					<SearchIcon />
				</span>
				<span className={railSearchText}>Search</span>
				<Kbd className={railSearchHint} aria-hidden="true">
					{SEARCH_SHORTCUT}
				</Kbd>
			</button>
		</div>
	);
}
