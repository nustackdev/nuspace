// The Add plane popup: the empty plane on top, every registered Plane
// under it, grouped and searchable like the / menu (../menu/), and picking
// one makes it. Over the groups, the packages (../menu/rank.ts): nuverse's
// Planes on top with the empty one, every other package a title, open while
// the lit row is in it. cmdk's arrows step every row, folded or not, so a
// folded package's rows stay mounted, hidden; a click on a title lights its
// first row.
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
import { useEffect, useRef, useState } from "react";
import { navigate, openPlane } from "../core/router";
import { menuItem, menuPackage } from "../design";
import { DEFAULT_ICON } from "../icon/parse";
import { MenuEntry, MenuKeys, PackageEntry } from "../menu/Entry";
import { type MenuPackage, menuPackages, menuPinned, menuScore } from "../menu/rank";
import { closeAddPlane, createPlane, useAddRequest } from "./add";
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

/** The popup's packages for `query`: the empty plane pinned first when it matches. `lit` opens its package. */
export function addPackages(
	query: string,
	registered: Registered[],
	lit?: string,
): MenuPackage<Registered>[] {
	const rest = menuPackages(query, registered, lit);
	return menuScore(query, EMPTY) === null
		? rest
		: [menuPinned([{ heading: null, items: [EMPTY] }]), ...rest];
}

/** cmdk's value for a row. cmdk keys its rows by value, and "" would fall back to the text. */
const rowValue = (entry: Registered) => entry.name || "_empty";

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
	// cmdk's lit row, held here: its package is the open one.
	const [lit, setLit] = useState("");
	const list = useRef<HTMLDivElement | null>(null);
	// A pick sends the caret on to the new Plane (an empty one takes it, see
	// ../plane/Plane.tsx), so the popup does not hand it back as it closes.
	const picked = useRef(false);
	const packages = addPackages(query, registered, lit === "_empty" ? "" : lit);

	// cmdk scrolls to a row before its package unfolds: scroll again once it has.
	// biome-ignore lint/correctness/useExhaustiveDependencies: a new lit row is a new scroll
	useEffect(() => {
		list.current
			?.querySelector<HTMLElement>('[cmdk-item][data-selected="true"]')
			?.scrollIntoView({ block: "nearest" });
	}, [lit]);

	const pick = (entry: Registered) => {
		const req = request;
		picked.current = true;
		closeAddPlane();
		setQuery("");
		setLit("");
		if (!req) return;
		const planeId = createPlane(notify, entry, req.parent, entry === EMPTY);
		if (req.parent && req.parent !== ROOT_ID) reveal(req.parent);
		// From a pane: a link followed there (in place on a desk item). Else solo.
		if (req.pane) navigate({ plane: planeId, params: {} }, req.pane);
		else openPlane(planeId);
	};

	return (
		<CommandPalette
			open={request !== null}
			onOpenChange={(open) => {
				if (open) return;
				closeAddPlane();
				setQuery("");
				setLit("");
			}}
			label="Add plane"
			onCloseAutoFocus={(e) => {
				if (picked.current) e.preventDefault();
				picked.current = false;
			}}
			// Ranked and grouped here (../menu/rank.ts), like the / menu.
			shouldFilter={false}
			value={lit}
			onValueChange={setLit}
			// The arrows wrap past either end, as the / menu's do.
			loop
		>
			<CommandInput placeholder="Add plane" value={query} onValueChange={setQuery} />
			<CommandList ref={list} className="max-h-[26rem]">
				<CommandEmpty>Nothing matches “{query.trim()}”</CommandEmpty>
				{packages.map((pkg) => (
					<div key={pkg.key ?? `_${pkg.sections[0]?.items[0]?.name}`}>
						{pkg.key === null ? null : (
							// A title, not a stop: a click lights its first row, which opens it.
							// biome-ignore lint/a11y/useKeyWithClickEvents lint/a11y/noStaticElementInteractions: the arrows reach the same rows
							<div
								data-open={pkg.open}
								onClick={() => {
									const first = pkg.sections[0]?.items[0];
									if (first) setLit(rowValue(first));
								}}
								className={menuPackage}
							>
								<PackageEntry {...pkg} />
							</div>
						)}
						{/* Folded rows stay mounted, hidden: cmdk's arrows step them too. */}
						<div hidden={!pkg.open}>
							{pkg.sections.map((section) => (
								// The empty plane and nuverse's ungrouped rows are headless.
								<CommandGroup
									key={section.heading ?? `_${section.items[0]?.name}`}
									heading={section.heading ?? undefined}
								>
									{section.items.map((entry) => (
										<CommandItem
											key={entry.name}
											value={rowValue(entry)}
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
						</div>
					</div>
				))}
			</CommandList>
			{packages.length === 0 ? null : <MenuKeys action="Create" />}
		</CommandPalette>
	);
}
