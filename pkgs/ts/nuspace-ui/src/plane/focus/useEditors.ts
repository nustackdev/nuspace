// The cells' markdown editors, as the kit hands them over.
//
// A cell whose program draws a kit markdown editor (a MarkdownRef) registers
// it at its own tree path while it is mounted. That path is under the cell's
// address (../cell/address.ts), so the plane finds a cell's editor by asking
// the kit what is at that address (`markdownAt`), and hears it arrive, change
// or leave by subscribing there (`subscribeMarkdown`). No DOM query, no
// selector: what drew the editor around it is none of the plane's business.
//
// For each editor of one of this plane's cells that takes commands, two
// things: its intents are heard (and routed, ../intents.ts), and its handle's
// arrival is told, so a focus request parked for the cell is consumed
// (./useFocusRouting.ts).
//
// An editor is there before it takes commands: a program opens one in steps,
// the text first and editing a frame later, and the kit hands out a handle
// only while it is editable. So the plane can tell "an editor is here, not
// yet open for editing" (a parked request keeps waiting) from "nothing here"
// (it is let go). Which of the two it is decides only that, never whether
// the cell shows: that is the request's business (../Plane.tsx).
//
// Registration happens in the editor's own mount, which runs before this
// plane's effects on the first render. So the subscription is followed by a
// sweep over the cells for editors already there, and the sweep runs again
// whenever the cells change.

import type { Path } from "@nustackdev/ui-core";
import {
	type MarkdownHandle,
	type MarkdownIntent,
	markdownAt,
	pathKey,
	subscribeMarkdown,
} from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { CELLS, cellUiPath } from "../cell/address";
import type { Cell } from "../types";

export function useEditors(
	viewerPath: Path,
	cells: Cell[],
	on: {
		/** An intent from a cell's editor. True when acted on. */
		intent: (cell: string, i: MarkdownIntent) => boolean;
		/** A cell's editor handed its handle: it takes commands now. */
		registered: (cell: string) => void;
		/** A cell's editor left, and none is there now. */
		vanished: (cell: string) => void;
	},
): void {
	const cb = useRef(on);
	cb.current = on;
	const at = useRef({ viewerPath, live: new Set<string>() });
	at.current = { viewerPath, live: new Set(cells.map((c) => c.id)) };
	/** The handle each cell's intents are heard on, and how to stop. */
	const heard = useRef(new Map<string, { doc: MarkdownHandle; off: () => void }>());
	const viewerKey = pathKey(viewerPath);
	/** Whether cell `id` has a markdown editor mounted now, open for editing or not. */
	const sense = useRef(
		(id: string) => markdownAt(cellUiPath(at.current.viewerPath, id)) !== null,
	).current;

	/** Hear cell `id`'s handle as the kit has it now, or none. */
	const sync = useRef((id: string) => {
		const { viewerPath, live } = at.current;
		const doc = live.has(id) ? (markdownAt(cellUiPath(viewerPath, id))?.handle ?? null) : null;
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
		const off = subscribeMarkdown(base, (path, entry) => {
			const id = path[base.length];
			if (!id) return;
			sync(id);
			const here = sense(id);
			if (entry === null && !here && at.current.live.has(id)) cb.current.vanished(id);
		});
		for (const id of at.current.live) sync(id);
		return () => {
			off();
			for (const h of map.values()) h.off();
			map.clear();
		};
	}, [viewerKey, sync, sense]);

	// Cells come and go: hear the new ones' editors, stop hearing the gone.
	useEffect(() => {
		for (const id of [...heard.current.keys(), ...cells.map((c) => c.id)]) sync(id);
	}, [cells, sync]);
}
