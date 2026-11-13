// A plane's menu: the one item list behind the menus that act on a Plane,
// the Planes tree row's (`...` and right-click, ../sidebar/PlanesTree.tsx) and
// the pane bar's `...` (../pane/PaneMenu.tsx). Each passes the actions it has;
// the list keeps the same groups, in the same order, with the same icons and
// labels, so the two read as one menu that shows more or less of itself.
//
//   open      Open, Open to the side, Open in a new desk, Open in new tab
//   close     Close
//   plane     Add plane inside, Rename, Change icon,
//             Copy plane ID, Copy plane key, Restart plane
//   settings  the caller's rows, eg the pane's switches
//   delete    Delete plane, last and on its own
//
// "Open to the side" is with Open, on the Planes tree row's menu only: a pane
// is beside itself already. A group with nothing in it takes no separator. "Open in new tab" and "Copy
// plane ID" need only the id, so they are on every menu with a plane. "Copy
// plane key" needs the key, which only a landed plane's pane knows, so it is
// on the pane's menu alone, disabled while the plane has no key. The
// close group shows when `desk` is set and the tab is on a desk item showing
// the plane: Close takes the plane item out of its desk, or the pane out of
// its strip. A solo plane has nothing to close.

import {
	AtSign,
	Check,
	Columns3,
	ExternalLink,
	FileText,
	Hash,
	PanelRight,
	Pen,
	Plus,
	RotateCcw,
	SmilePlus,
	Trash2,
	X,
} from "lucide-react";
import type * as React from "react";
import { Fragment } from "react";
import { useCopyRow } from "../core/clipboard";
import { closeItem, closePane, openInNewTab, type Route, useRoute } from "../core/router";
import { openToTheSide } from "../desk/open";
import { NEW_INSIDE_KEYS, openAddPlane } from "../sidebar/add";
import { OPEN_KEYS, SIDE_KEYS } from "../sidebar/keys";
import { newDeskWith } from "../sidebar/newDesk";
import type { MenuParts } from "./parts";

export type PlaneActions = {
	planeId: string;
	/** Open the plane solo: a Planes tree row's. */
	open?: () => void;
	/** Add plane inside. A child of the plane, opened as usual, when left out. */
	add?: () => void;
	/** Left off where the menu cannot rename in place. */
	rename?: () => void;
	/** Left off where there is no picker to anchor. */
	changeIcon?: () => void;
	/** The plane's key, "" for none. Left out where it is not known: no row then. */
	planeKey?: string;
	restart?: () => void;
	/** The close group, while the plane is a desk item or a pane of one. */
	desk?: boolean;
	/** Rows of their own group, after the desk's. */
	settings?: React.ReactNode;
	/** Null or left out for a Plane that cannot be deleted. */
	remove?: (() => void) | null;
};

export function PlaneMenuItems({ parts, ...a }: PlaneActions & { parts: MenuParts }) {
	const { Item, Separator, Shortcut } = parts;
	const copy = useCopyRow(a.planeId);
	const copyKey = useCopyRow(a.planeKey ?? "");
	const route = useRoute();
	const id = a.planeId;
	const add = a.add ?? (() => openAddPlane({ parent: id }));

	const open = [
		a.open ? (
			<Item key="open" onSelect={a.open}>
				<FileText />
				Open
				<Shortcut keys={OPEN_KEYS} />
			</Item>
		) : null,
		a.open ? (
			<Item key="side" onSelect={() => openToTheSide({ plane: id, params: {} })}>
				<PanelRight />
				Open to the side
				<Shortcut keys={SIDE_KEYS} />
			</Item>
		) : null,
		<Item key="new-desk" onSelect={() => newDeskWith(id)}>
			<Columns3 />
			Open in a new desk
		</Item>,
		<Item key="tab" onSelect={() => openInNewTab(id)}>
			<ExternalLink />
			Open in new tab
		</Item>,
	];

	const plane = [
		<Item key="add" onSelect={add}>
			<Plus />
			Add plane inside
			<Shortcut keys={NEW_INSIDE_KEYS} />
		</Item>,
		a.rename ? (
			<Item key="rename" onSelect={a.rename}>
				<Pen />
				Rename
			</Item>
		) : null,
		a.changeIcon ? (
			<Item key="icon" onSelect={a.changeIcon}>
				<SmilePlus />
				Change icon
			</Item>
		) : null,
		<Item key="copy" onSelect={copy.onSelect}>
			{copy.copied ? <Check /> : <Hash />}
			{copy.copied ? "Copied" : "Copy plane ID"}
		</Item>,
		a.planeKey !== undefined ? (
			<Item key="copy-key" disabled={!a.planeKey} onSelect={copyKey.onSelect}>
				{copyKey.copied ? <Check /> : <AtSign />}
				{copyKey.copied ? "Copied" : "Copy plane key"}
			</Item>
		) : null,
		a.restart ? (
			<Item key="restart" onSelect={a.restart}>
				<RotateCcw />
				Restart plane
			</Item>
		) : null,
	];

	const desk = a.desk ? deskItems(parts, id, route) : [];

	const remove = a.remove
		? [
				<Item key="delete" variant="danger" onSelect={a.remove}>
					<Trash2 />
					Delete plane
				</Item>,
			]
		: [];

	const groups = [open, desk, plane, a.settings ? [a.settings] : [], remove]
		.map((g) => g.filter(Boolean))
		.filter((g) => g.length > 0);

	return (
		<>
			{groups.map((g, i) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: the groups are fixed, in a fixed order.
				<Fragment key={i}>
					{i > 0 ? <Separator /> : null}
					{g}
				</Fragment>
			))}
		</>
	);
}

/** What closing `id` does where the tab is, or null: off a desk item, or a plane it does not show. */
function closerOf(id: string, route: Route): (() => void) | null {
	if (route.kind !== "item") return null;
	const { desk, item } = route;
	if (item.kind === "plane") {
		const plane = (item.recent ?? item.original).plane;
		return plane === id ? () => closeItem(desk, item.id) : null;
	}
	const shows = item.columns.some((c) =>
		c.panes.some((p) => (p.recent ?? p.original).plane === id),
	);
	return shows ? () => closePane(desk, item.id, id) : null;
}

/** Close: the plane item out of its desk, or the pane out of its strip. None anywhere else. */
function deskItems(parts: MenuParts, id: string, route: Route): React.ReactNode[] {
	const { Item } = parts;
	const close = closerOf(id, route);
	if (!close) return [];
	return [
		<Item key="close" onSelect={close}>
			<X />
			Close
		</Item>,
	];
}
