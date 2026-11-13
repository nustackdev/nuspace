// Making a desk: the one way every "New desk" goes, the header's `+` menu,
// a plane's menu ("Open in a new desk") and the New desk drop zone
// shown while dragging. The desk lands named "Untitled", empty or with what
// was dropped or picked as its first item; its folder opens and the tab goes
// to it. Renaming it is up to the user, from its folder's chip.

import { createDesk, knownDesks, openDesk, writeDesks } from "../core/router";
import { type Payload, planNew } from "../desk/dnd";
import { mintDeskId } from "../desk/model";
import { folderKey, setFolded } from "./folders";

/**
 * Make a desk, `first` as its first item when given (written once, with the
 * desk it leaves: ../desk/dnd.ts `planNew`), open its folder and go to it.
 */
export function newDesk(first?: Payload): string {
	const desks = knownDesks();
	const fresh = mintDeskId((x) => !!desks?.[x]);
	const plan = first && desks ? planNew(desks, first, fresh) : null;
	let id = fresh;
	if (plan) writeDesks(plan);
	else id = createDesk();
	setFolded(folderKey(id), false);
	openDesk(id);
	return id;
}

/** "Open in a new desk": a new desk holding plane `plane` as its one item. */
export function newDeskWith(plane: string): string {
	return newDesk({ kind: "plane", link: { plane, params: {} } });
}
