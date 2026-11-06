// The cells' documents, as the kit registry hands them over.
//
// A cell whose program draws a kit document (a MarkdownRef) registers it at
// its own tree path while its editor is mounted. That path is under the
// cell's address (../cell/address.ts), so the plane finds a cell's document
// by asking the registry what is under that address, and hears it arrive or
// leave by subscribing there. No DOM query, no selector: what drew the
// document around it is none of the plane's business.
//
// For each document of one of this plane's cells, two things: its intents
// are heard (and routed, ../intents.ts), and its arrival is told, so a focus
// request parked for the cell is consumed (./useFocusRouting.ts).
//
// A document is present before it is registered: a program opens one in
// steps, the text first and editing a frame later, and the kit registers a
// handle only while it takes commands. Presence is heard too (the kit's
// `subscribePresence`), so the plane can tell "a document is here, not yet
// open for editing" (a parked request keeps waiting) from "nothing here"
// (it is let go), and `present` is what the plane draws by.
//
// Registration happens in the editor's own mount, which runs before this
// plane's effects on the first render. So the subscription is followed by a
// sweep over the cells for documents already there, and the sweep runs again
// whenever the cells change.

import type { Path } from "@nustackdev/ui-core";
import {
	type DocIntent,
	type DocumentHandle,
	documentPresent,
	documentUnder,
	pathKey,
	subscribeDocuments,
	subscribePresence,
} from "@nustackdev/ui-kit";
import { useEffect, useRef, useState } from "react";
import { CELLS, cellUiPath } from "../cell/address";
import type { Cell } from "../types";

export function useDocuments(
	viewerPath: Path,
	cells: Cell[],
	on: {
		/** An intent from a cell's document. True when acted on. */
		intent: (cell: string, i: DocIntent) => boolean;
		/** A cell's document registered. */
		registered: (cell: string) => void;
		/** A cell's document left without ever taking commands, and none is there now. */
		vanished: (cell: string) => void;
	},
): { present: ReadonlySet<string> } {
	const cb = useRef(on);
	cb.current = on;
	const at = useRef({ viewerPath, live: new Set<string>() });
	at.current = { viewerPath, live: new Set(cells.map((c) => c.id)) };
	/** The handle each cell's intents are heard on, and how to stop. */
	const heard = useRef(new Map<string, { doc: DocumentHandle; off: () => void }>());
	const viewerKey = pathKey(viewerPath);
	/** Cells with a document mounted, open for editing or not. */
	const [present, setPresent] = useState<ReadonlySet<string>>(() => new Set());

	/** Whether cell `id` has a document mounted now, as a set the render reads. */
	const sense = useRef((id: string) => {
		const here = documentPresent(cellUiPath(at.current.viewerPath, id));
		setPresent((was) => {
			if (was.has(id) === here) return was;
			const next = new Set(was);
			if (here) next.add(id);
			else next.delete(id);
			return next;
		});
		return here;
	}).current;

	/** Hear cell `id`'s document as the registry has it now, or none. */
	const sync = useRef((id: string) => {
		const { viewerPath, live } = at.current;
		const doc = live.has(id) ? documentUnder(cellUiPath(viewerPath, id)) : null;
		const map = heard.current;
		const was = map.get(id);
		if (was?.doc === doc) return;
		was?.off();
		map.delete(id);
		if (!doc) return;
		map.set(id, { doc, off: doc.onIntent((i) => cb.current.intent(id, i)) });
		cb.current.registered(id);
	}).current;

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	useEffect(() => {
		const base = [...viewerPath, CELLS];
		const map = heard.current;
		const off = subscribeDocuments(base, (path) => {
			const id = path[base.length];
			if (id) sync(id);
		});
		const offPresence = subscribePresence(base, (path) => {
			const id = path[base.length];
			if (!id) return;
			const here = sense(id);
			if (!here && at.current.live.has(id) && !documentUnder(cellUiPath(viewerPath, id))) {
				cb.current.vanished(id);
			}
		});
		for (const id of at.current.live) {
			sync(id);
			sense(id);
		}
		return () => {
			off();
			offPresence();
			for (const h of map.values()) h.off();
			map.clear();
		};
	}, [viewerKey, sync, sense]);

	// Cells come and go: hear the new ones' documents, stop hearing the gone.
	useEffect(() => {
		for (const id of [...heard.current.keys(), ...cells.map((c) => c.id)]) sync(id);
		for (const c of cells) sense(c.id);
	}, [cells, sync, sense]);

	return { present };
}
