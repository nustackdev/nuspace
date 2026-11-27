// The phone's Add plane: a bottom sheet with the empty plane on top and every
// registered plane under it, by package. Desktop's popup is a searchable
// palette; the phone's list is short enough to scroll, and a pick is a tap.
//
// The request is desktop's (../../sidebar/add.ts): the sidebar's +, the
// Planes title's + and a row's "Add plane inside" all open it. The new plane
// is made where the request says, its parent opened so its row shows, and the
// sidebar closes onto it.

import { BottomSheet, BottomSheetContent, BottomSheetItem } from "@nustackdev/ui-kit";
import { Fragment } from "react";
import { openPlane } from "../../core/router";
import { mobileSheetGroup, mobileSheetLabel, mobileSheetNote } from "../../design";
import { PlaneIcon } from "../../icon/PlaneIcon";
import { DEFAULT_ICON, planeIcon } from "../../icon/parse";
import { closeAddPlane, createPlane, useAddRequest } from "../../sidebar/add";
import type { Notify } from "../../sidebar/ops";
import { type Registered, ROOT_ID } from "../../sidebar/types";
import { leaveThen } from "./open";

/** The empty plane (nuspace.ext.EMPTY): no registry entry, so it is here. Its planes start untitled. */
export const EMPTY_PLANE: Registered = {
	name: "",
	label: "Empty",
	group: "",
	icon: "",
	description: "An empty plane to add cells to.",
};

/** The registered planes by package, packages in the order they first show. */
export function addGroups(registered: Registered[]): { pkg: string; entries: Registered[] }[] {
	const by = new Map<string, Registered[]>();
	for (const entry of registered) {
		const dot = entry.name.indexOf(".");
		const pkg = dot > 0 ? entry.name.slice(0, dot) : "";
		const list = by.get(pkg) ?? [];
		list.push(entry);
		by.set(pkg, list);
	}
	return [...by.entries()].map(([pkg, entries]) => ({ pkg, entries }));
}

export function AddPlaneSheet({
	registered,
	notify,
	expand,
}: {
	registered: Registered[];
	notify: Notify;
	/** Open a plane's row, so the new one under it shows. */
	expand: (id: string) => void;
}) {
	const request = useAddRequest();
	const inside = request && request.parent !== ROOT_ID ? request.parent : "";

	const pick = (entry: Registered) => {
		const req = request;
		closeAddPlane();
		if (!req) return;
		const planeId = createPlane(notify, entry, req.parent, entry === EMPTY_PLANE);
		if (inside) expand(inside);
		leaveThen(() => openPlane(planeId));
	};

	const row = (entry: Registered) => (
		<BottomSheetItem
			key={entry.name || "_empty"}
			onClick={() => pick(entry)}
			data-spec={entry.name}
		>
			<PlaneIcon icon={entry.icon ? planeIcon(entry.icon) : DEFAULT_ICON} />
			<span className={mobileSheetLabel}>{entry.label}</span>
		</BottomSheetItem>
	);

	return (
		<BottomSheet open={request !== null} onOpenChange={(open) => (open ? null : closeAddPlane())}>
			<BottomSheetContent title={inside ? "Add plane inside" : "Add plane"}>
				{row(EMPTY_PLANE)}
				{addGroups(registered).map(({ pkg, entries }) => (
					<Fragment key={pkg || "_"}>
						{pkg ? <div className={mobileSheetGroup}>{pkg}</div> : null}
						{entries.map(row)}
					</Fragment>
				))}
				{registered.length ? null : (
					<p className={mobileSheetNote}>No packages offer planes in this space.</p>
				)}
			</BottomSheetContent>
		</BottomSheet>
	);
}
