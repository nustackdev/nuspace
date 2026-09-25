// Pins: the Planes pinned to the row under the rail's top bar, in order.
//
// The server's `Space.pinned` is the one source, shipped by `set_tree`. A pin
// is a shortcut: the Plane stays in the tree. Pin, unpin and reorder go out as
// one op each and land here at once, optimistically: the row changes now and
// the next `set_tree` replaces it with what the server stored.
//
// An index is a position among the pins with the Plane taken out, the end
// when out of range, which is how the server reads it too.

import type { Path } from "@nustackdev/ui-core";
import { nodeAt, pathKey, tree as store } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { useTypePath } from "../core/surfaces";
import { notifyOp } from "../core/wire";
import type { Ops } from "./ops";
import { usePinned, usePlaneTree } from "./state";
import { KIND_PLANE } from "./types";

/** `list` with `id` taken out and put at `index`, the end when out of range. */
export function placePin(list: string[], id: string, index: number): string[] {
	const out = list.filter((k) => k !== id);
	out.splice(index >= 0 && index < out.length ? index : out.length, 0, id);
	return out;
}

/**
 * The index a drop of `id` at `slot` asks for. `slot` counts the gaps of
 * `list` as drawn, 0 before the first. Null when `id` would stay where it is.
 */
export function pinDropIndex(list: string[], id: string, slot: number): number | null {
	const from = list.indexOf(id);
	if (from < 0) return slot;
	const index = slot > from ? slot - 1 : slot;
	return index === from ? null : index;
}

/** The pins and the three ops on them, bound to the sidebar's node. */
export type Pins = {
	ids: string[];
	/** Pin at `index`, the end when left out. Moves a pinned Plane. */
	pin: (id: string, index?: number) => void;
	unpin: (id: string) => void;
	move: (id: string, index: number) => void;
};

function patch(path: Path, next: (pins: string[]) => string[]): void {
	const raw = nodeAt(path)?.props.pinned;
	store.getState().setProps(path, { pinned: next(Array.isArray(raw) ? (raw as string[]) : []) });
}

/** Pin ops on the sidebar at `path`: applied locally, then sent. */
function bind(path: Path, ids: string[]): Pins {
	const send = <K extends "plane.pin" | "plane.unpin" | "plane.pin_move">(op: K, args: Ops[K]) =>
		notifyOp<Ops, K>(path, op, args);
	return {
		ids,
		pin: (id, index = -1) => {
			patch(path, (pins) => placePin(pins, id, index));
			send("plane.pin", { plane_id: id, index });
		},
		unpin: (id) => {
			patch(path, (pins) => pins.filter((k) => k !== id));
			send("plane.unpin", { plane_id: id });
		},
		move: (id, index) => {
			patch(path, (pins) => (pins.includes(id) ? placePin(pins, id, index) : pins));
			send("plane.pin_move", { plane_id: id, index });
		},
	};
}

/** The pins of the sidebar at `sidebar`, null while there is none. */
function usePinsAt(sidebar: Path | null): Pins | null {
	const ids = usePinned(sidebar);
	const key = sidebar ? pathKey(sidebar) : "";
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	return useMemo(() => (sidebar ? bind(sidebar, ids) : null), [key, ids]);
}

/** The sidebar's own pins, from inside it. `path` is its node. */
export function usePins(path: Path): Pins {
	return usePinsAt(path) as Pins;
}

/**
 * Pin or unpin one Plane, from outside the sidebar (a pane's `...`). Null
 * for a Plane the sidebar does not draw, which is one that cannot be pinned.
 */
export function usePlanePin(planeId: string): { pinned: boolean; toggle: () => void } | null {
	const sidebar = useTypePath("SidebarRef");
	const tree = usePlaneTree(sidebar);
	const pins = usePinsAt(sidebar);
	if (!pins || tree[planeId]?.kind !== KIND_PLANE) return null;
	const pinned = pins.ids.includes(planeId);
	return { pinned, toggle: () => (pinned ? pins.unpin(planeId) : pins.pin(planeId)) };
}
