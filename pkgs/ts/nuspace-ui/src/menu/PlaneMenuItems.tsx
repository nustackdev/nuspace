// A plane's menu: the one item list behind the menus that act on a Plane,
// the rail row's (`...` and right-click, ../sidebar/PlaneRow.tsx) and the pane
// bar's `...` (../pane/PaneMenu.tsx). Each passes the actions it has; the list
// keeps the same groups, in the same order, with the same icons and labels, so
// the two read as one menu that shows more or less of itself. The dock chip's
// right-click (../main/Dock.tsx) is the close group alone.
//
//   open      Open, Open on desk, Open in new tab
//   close     Close, Close others, Close to the right
//   plane     Add plane inside, Rename, Change icon, Pin / Unpin,
//             Copy plane id, Restart plane
//   settings  the caller's rows, eg the pane's switches
//   delete    Delete plane, last and on its own
//
// A group with nothing in it takes no separator. "Open in new tab" and "Copy
// plane id" need only the id, so they are on every menu with a plane. The
// close group shows when `desk` is set, the plane is on the desk, and there is
// another pane to close it to, with "Close to the right" kept, disabled, on
// the last pane so the menu keeps its shape from pane to pane.

import {
	ArrowRightToLine,
	Check,
	Columns2,
	Copy,
	CopyX,
	ExternalLink,
	FileText,
	PenLine,
	Pin,
	PinOff,
	Plus,
	RotateCcw,
	SmilePlus,
	Trash2,
	X,
} from "lucide-react";
import type * as React from "react";
import { Fragment } from "react";
import { useCopyRow } from "../core/clipboard";
import { closePane, closePanes, openInNewTab, useRoutes } from "../core/router";
import { NEW_INSIDE_KEYS, openAddPlane } from "../sidebar/add";
import { DESK_KEYS, OPEN_KEYS } from "../sidebar/keys";
import type { MenuParts } from "./parts";

export type PlaneActions = {
	planeId: string;
	/** Open in the focused pane: a rail row, whose plane may not be on the desk. */
	open?: () => void;
	/** Open in a new pane beside the others. */
	openOnDesk?: () => void;
	/** Add plane inside. A child of the plane, opened as usual, when left out. */
	add?: () => void;
	/** Left off where the menu cannot rename in place. */
	rename?: () => void;
	/** Left off where there is no picker to anchor. */
	changeIcon?: () => void;
	/** Pin / Unpin. Null or left out for a plane the rail does not draw. */
	pin?: { pinned: boolean; toggle: () => void } | null;
	restart?: () => void;
	/** The close group, while the plane is in a pane. */
	desk?: boolean;
	/** Rows of their own group, after the desk's. */
	settings?: React.ReactNode;
	/** Null or left out for a Plane that cannot be deleted. */
	remove?: (() => void) | null;
};

export function PlaneMenuItems({ parts, ...a }: PlaneActions & { parts: MenuParts }) {
	const { Item, Separator, Shortcut } = parts;
	const copy = useCopyRow(a.planeId);
	const routes = useRoutes();
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
		a.openOnDesk ? (
			<Item key="desk" onSelect={a.openOnDesk}>
				<Columns2 />
				Open on desk
				<Shortcut keys={DESK_KEYS} />
			</Item>
		) : null,
		<Item key="tab" onSelect={() => openInNewTab(id)}>
			<ExternalLink />
			Open in new tab
		</Item>,
	];

	const PinIcon = a.pin?.pinned ? PinOff : Pin;
	const plane = [
		<Item key="add" onSelect={add}>
			<Plus />
			Add plane inside
			<Shortcut keys={NEW_INSIDE_KEYS} />
		</Item>,
		a.rename ? (
			<Item key="rename" onSelect={a.rename}>
				<PenLine />
				Rename
			</Item>
		) : null,
		a.changeIcon ? (
			<Item key="icon" onSelect={a.changeIcon}>
				<SmilePlus />
				Change icon
			</Item>
		) : null,
		a.pin ? (
			<Item key="pin" onSelect={a.pin.toggle}>
				<PinIcon />
				{a.pin.pinned ? "Unpin" : "Pin"}
			</Item>
		) : null,
		<Item key="copy" onSelect={copy.onSelect}>
			{copy.copied ? <Check /> : <Copy />}
			{copy.copied ? "Copied" : "Copy plane id"}
		</Item>,
		a.restart ? (
			<Item key="restart" onSelect={a.restart}>
				<RotateCcw />
				Restart plane
			</Item>
		) : null,
	];

	const desk = a.desk ? deskItems(parts, id, routes) : [];

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

/** The close group alone: the dock chip's, and a pane whose plane has not landed, or is absent. */
export function DeskMenuItems({ parts, planeId }: { parts: MenuParts; planeId: string }) {
	return <>{deskItems(parts, planeId, useRoutes())}</>;
}

/** Close, Close others, Close to the right. None off the desk, or on a lone pane. */
function deskItems(parts: MenuParts, id: string, routes: string[]): React.ReactNode[] {
	const { Item } = parts;
	const others = routes.filter((r) => r !== id);
	if (!routes.includes(id) || others.length === 0) return [];
	const at = routes.indexOf(id);
	const right = at < 0 ? [] : routes.slice(at + 1);
	return [
		<Item key="close" onSelect={() => closePane(id)}>
			<X />
			Close
		</Item>,
		<Item key="others" onSelect={() => closePanes(others)}>
			<CopyX />
			Close others
		</Item>,
		<Item key="right" disabled={right.length === 0} onSelect={() => closePanes(right)}>
			<ArrowRightToLine />
			Close to the right
		</Item>,
	];
}
