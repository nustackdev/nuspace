// The SidebarRef node: what the wire writes, and the fold state the browser
// keeps.
//
// The wire half is the list of Planes that draw, replaced wholesale by
// `set_tree`, and the registered Planes the Add plane popup offers, seeded as
// the `registered` prop at boot. Both land in props.
//
// The browser half is which branches are open. The server never sees it, none
// of it survives a reload, and none of it should. It lives in the node's
// `local` prop (see core/local.ts).
//
// ## Why this type keeps a write handler
//
// One op rides a payload told apart by an `op` key, and the store's default
// write has nothing to dispatch on. It also sets `loaded`, which is what tells
// an empty Space from a tree that has not landed.

import { getNode, type Path, type Props } from "@nustackdev/ui-core";
import { useProps, useTree } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { patchLocal, useLocalSlot } from "../core/local";
import {
	coerceRegistered,
	coerceTree,
	EMPTY_TREE,
	type PlaneTree,
	type SidebarValue,
} from "./types";

// -- Browser-owned state ------------------------------------------------------

export type SidebarState = {
	/** Rows whose children are showing. A Plane id per entry. */
	expanded: string[];
};

export const EMPTY_LOCAL: SidebarState = { expanded: [] };

// -- The write handler's body -------------------------------------------------

/** Apply one inbound payload to this node's props. Pure, so it is testable. */
export function applySidebarWrite(props: Props, payload: unknown): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	if (String(p.op ?? "") !== "set_tree") return;
	props.tree = coerceTree(p.planes);
	props.loaded = true;
}

// -- Reads --------------------------------------------------------------------

export function useSidebarValue(path: Path): SidebarValue {
	const props = useProps(path);
	const tree = (props.tree as SidebarValue["tree"] | undefined) ?? EMPTY_TREE;
	const loaded = props.loaded === true;
	const raw = props.registered;
	const registered = useMemo(() => coerceRegistered(raw), [raw]);
	return useMemo(() => ({ tree, loaded, registered }), [tree, loaded, registered]);
}

/**
 * The icon a plane falls back to: its registered Plane's, "" for none. Read
 * off the sidebar's node, the one place a plane's `made_by` and the
 * registered list both reach the browser. `sidebar` is that node's path.
 */
export function useRegisteredIcon(sidebar: Path | null, planeId: string): string {
	return useTree((s) => {
		const props = sidebar ? getNode(s.root, sidebar)?.props : undefined;
		const made = (props?.tree as PlaneTree | undefined)?.[planeId]?.made_by;
		if (!made || !Array.isArray(props?.registered)) return "";
		const hit = (props.registered as unknown[]).find(
			(r) => !!r && typeof r === "object" && (r as Record<string, unknown>).name === made,
		) as Record<string, unknown> | undefined;
		return typeof hit?.icon === "string" ? hit.icon : "";
	});
}

export function useExpanded(path: Path): string[] {
	return useLocalSlot(path, EMPTY_LOCAL, (s) => s.expanded);
}

// -- Writes -------------------------------------------------------------------

/**
 * Patch the browser-owned fold state. Module-level rather than a hook so event
 * handlers deep in the tree can call it without prop-drilling, and so it never
 * participates in a render.
 */
export function patchSidebar(
	path: Path,
	patch: Partial<SidebarState> | ((s: SidebarState) => Partial<SidebarState>),
): void {
	patchLocal(path, EMPTY_LOCAL, patch);
}
