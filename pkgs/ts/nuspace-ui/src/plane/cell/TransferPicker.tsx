// The "Move to plane" picker: the planes a cell can go to (../transfer.ts),
// searchable, and picking one transfers the cell to its end. The list is
// asked for as it opens: a kit spinner stands in until the answer lands.
//
// A kit `CommandPalette`, as the Add plane popup (../../sidebar/AddPlane.tsx):
// the dialog, the arrows, Enter and Escape are its own. The rows are ranked
// here like every registry menu (../../menu/rank.ts), by title, and by id
// past that, so a plane is found by either.

import {
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
	CommandPalette,
	Spinner,
} from "@nustackdev/ui-kit";
import { useMemo, useRef, useState } from "react";
import { menuItem } from "../../design";
import { DEFAULT_ICON } from "../../icon/parse";
import { MenuEntry, MenuKeys } from "../../menu/Entry";
import { menuItems } from "../../menu/rank";
import type { Target } from "../transfer";

export function TransferPicker({
	open,
	targets,
	onPick,
	onClose,
}: {
	open: boolean;
	/** Where the cell can go, in order (../transfer.ts `targetsFrom`). Null while loading. */
	targets: readonly Target[] | null;
	onPick: (planeId: string) => void;
	/** Shut, picked or not. `picked` says which. */
	onClose: (picked: boolean) => void;
}) {
	const [query, setQuery] = useState("");
	const picked = useRef(false);
	const entries = useMemo(
		() => (targets ?? []).map((t) => ({ name: t.id, label: t.title, icon: t.icon })),
		[targets],
	);
	const rows = menuItems(query, entries);

	const shut = () => {
		setQuery("");
		onClose(picked.current);
		picked.current = false;
	};

	return (
		<CommandPalette
			open={open}
			onOpenChange={(next) => {
				if (!next) shut();
			}}
			label="Move to plane"
			// The caret goes where the close sends it, not back to the menu's grip.
			onCloseAutoFocus={(e) => e.preventDefault()}
			shouldFilter={false}
			loop
		>
			<CommandInput placeholder="Move to plane" value={query} onValueChange={setQuery} />
			<CommandList className="max-h-[26rem]">
				<CommandEmpty>
					{targets === null ? (
						<Spinner size="sm" tone="neutral" label="Loading planes" className="mx-auto" />
					) : targets.length ? (
						`Nothing matches “${query.trim()}”`
					) : (
						"No other plane to move to"
					)}
				</CommandEmpty>
				<CommandGroup>
					{rows.map((row) => (
						<CommandItem
							key={row.name}
							value={row.name}
							onSelect={() => {
								picked.current = true;
								onPick(row.name);
								shut();
							}}
							className={menuItem}
						>
							<MenuEntry icon={row.icon} fallback={DEFAULT_ICON} label={row.label} query={query} />
						</CommandItem>
					))}
				</CommandGroup>
			</CommandList>
			{rows.length === 0 ? null : <MenuKeys action="Move" />}
		</CommandPalette>
	);
}
