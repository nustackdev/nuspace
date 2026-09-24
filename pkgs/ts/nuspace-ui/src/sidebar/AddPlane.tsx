// The Add plane popup: every registered Plane, Plain first, and picking one
// makes it.
//
// A kit `CommandPalette`, which brings the dialog, the filter, the arrows,
// Enter and Escape. Where the new Plane hangs and which pane it opens in is
// the request (./add.ts); what it is made from is the row picked.
//
// The id is minted here, so the new Plane is routed to at once and the pane
// waits for it (nav holds a route until its Plane exists). Its row is revealed
// under its parent and put in rename mode when the tree brings it.

import {
	CommandEmpty,
	CommandInput,
	CommandItem,
	CommandList,
	CommandPalette,
} from "@nustackdev/ui-kit";
import { mintId } from "../core/ids";
import { focusPane, replacePane } from "../core/router";
import { addPlaneDescription, addPlaneItem, addPlaneLabel, addPlaneText } from "../design";
import { closeAddPlane, renameWhenListed, useAddRequest } from "./add";
import { iconNamed } from "./icons";
import type { Notify } from "./ops";
import { type Registered, ROOT_ID } from "./types";

/** The registered Plane with no cells: its new Planes start as "Untitled". */
const PLAIN = "plain";

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

	const pick = (entry: Registered) => {
		const req = request;
		closeAddPlane();
		if (!req) return;
		const planeId = mintId("p");
		notify("plane.create", {
			plane_id: planeId,
			parent_id: req.parent || ROOT_ID,
			made_by: entry.name,
			title: entry.name === PLAIN ? "Untitled" : entry.label,
		});
		if (req.parent && req.parent !== ROOT_ID) reveal(req.parent);
		if (req.pane) focusPane(req.pane);
		replacePane(planeId);
		renameWhenListed(planeId);
	};

	return (
		<CommandPalette
			open={request !== null}
			onOpenChange={(open) => {
				if (!open) closeAddPlane();
			}}
			label="Add plane"
		>
			<CommandInput placeholder="Add plane" />
			<CommandList>
				<CommandEmpty>Nothing matches</CommandEmpty>
				{registered.map((entry) => {
					const Icon = iconNamed(entry.icon);
					return (
						<CommandItem
							key={entry.name}
							value={`${entry.label} ${entry.name}`}
							onSelect={() => pick(entry)}
							className={addPlaneItem}
						>
							<Icon aria-hidden="true" />
							<span className={addPlaneText}>
								<span className={addPlaneLabel}>{entry.label}</span>
								{entry.description ? (
									<span className={addPlaneDescription}>{entry.description}</span>
								) : null}
							</span>
						</CommandItem>
					);
				})}
			</CommandList>
		</CommandPalette>
	);
}
