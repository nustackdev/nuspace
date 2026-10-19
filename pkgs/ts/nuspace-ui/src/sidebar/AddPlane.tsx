// The Add plane popup: the empty plane pinned on top, every registered Plane
// under it, grouped and searchable like the / menu (../menu/), and picking
// one makes it.
//
// The empty plane is the space's own, like the / menu's empty program: no
// registry entry, so it is here. It still filters with the query like any row.
//
// A kit `CommandPalette`, which brings the dialog, the arrows, Enter and
// Escape; what it lists and in what order is ../menu/rank.ts. Where the new Plane hangs and which pane it opens in is
// the request (./add.ts); what it is made from is the row picked.
//
// The id is minted here, so the new Plane is routed to at once and the pane
// waits for it (nav holds a route until its Plane exists). Its row is revealed
// under its parent; renaming it is the user's call.

import {
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
	CommandPalette,
} from "@nustackdev/ui-kit";
import { useState } from "react";
import { mintId } from "../core/ids";
import { focusPane, replacePane } from "../core/router";
import { menuItem } from "../design";
import { DEFAULT_ICON } from "../icon/parse";
import { MenuEntry, MenuKeys } from "../menu/Entry";
import { type MenuSection, menuScore, menuSections } from "../menu/rank";
import { closeAddPlane, useAddRequest } from "./add";
import type { Notify } from "./ops";
import { type Registered, ROOT_ID } from "./types";

/** The empty plane (nuspace.ext.EMPTY). Its name is no Plane's, so the server makes it; its planes start as "Untitled". */
export const EMPTY: Registered = {
	name: "",
	label: "Empty",
	group: "",
	icon: "",
	description: "An empty plane. Add cells with /, or nest planes under it.",
};

/** The popup's sections for `query`: the empty plane first when it matches. */
function addSections(query: string, registered: Registered[]): MenuSection<Registered>[] {
	const rest = menuSections(query, registered);
	return menuScore(query, EMPTY) === null ? rest : [{ heading: null, items: [EMPTY] }, ...rest];
}

export function AddPlane({
	registered,
	notify,
	reveal,
}: {
	registered: Registered[];
	notify: Notify;
	/** Open a row, so the new child under it shows. */
	reveal: (key: string) => void;
}) {
	const request = useAddRequest();
	const [query, setQuery] = useState("");
	const sections = addSections(query, registered);

	const pick = (entry: Registered) => {
		const req = request;
		closeAddPlane();
		setQuery("");
		if (!req) return;
		const planeId = mintId("p");
		notify("plane.create", {
			plane_id: planeId,
			parent_id: req.parent || ROOT_ID,
			made_by: entry.name,
			title: entry === EMPTY ? "Untitled" : entry.label,
		});
		if (req.parent && req.parent !== ROOT_ID) reveal(req.parent);
		if (req.pane) focusPane(req.pane);
		replacePane(planeId);
	};

	return (
		<CommandPalette
			open={request !== null}
			onOpenChange={(open) => {
				if (open) return;
				closeAddPlane();
				setQuery("");
			}}
			label="Add plane"
			// Ranked and grouped here (../menu/rank.ts), like the / menu.
			shouldFilter={false}
			// The arrows wrap past either end, as the / menu's do.
			loop
		>
			<CommandInput placeholder="Add plane" value={query} onValueChange={setQuery} />
			<CommandList className="max-h-[26rem]">
				<CommandEmpty>Nothing matches “{query.trim()}”</CommandEmpty>
				{sections.map((section) => (
					// The pinned empty plane and an ungrouped list are both headless.
					<CommandGroup
						key={section.heading ?? `_${section.items[0]?.name}`}
						heading={section.heading ?? undefined}
					>
						{section.items.map((entry) => (
							<CommandItem
								key={entry.name}
								// cmdk keys its rows by value, and "" would fall back to the text.
								value={entry.name || "_empty"}
								onSelect={() => pick(entry)}
								className={menuItem}
							>
								<MenuEntry
									icon={entry.icon}
									fallback={DEFAULT_ICON}
									label={entry.label}
									description={entry.description}
									query={query}
								/>
							</CommandItem>
						))}
					</CommandGroup>
				))}
			</CommandList>
			{sections.length === 0 ? null : <MenuKeys action="Create" />}
		</CommandPalette>
	);
}
