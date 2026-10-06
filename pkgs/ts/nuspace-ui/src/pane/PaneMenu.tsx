// A pane's menu: the same items off the `...` on its bar (a kit dropdown) and
// off a right-click on its dock chip (a kit context menu, ../main/Dock.tsx).
// The items are written once against the menu parts (../shell/menu.ts).
//
// On top, the desk: "Close" takes this pane off it, "Close others" leaves
// only this one, "Close to the right" takes off every pane after it, and
// stays in the menu, disabled, on the last pane, so the menu keeps its shape
// from pane to pane. A lone pane has nothing to close it to: no desk items.
//
// Under the separator, the plane: "Open in new tab" opens the Plane's URL in a
// browser tab, "Add plane inside" opens the Add plane popup for a child of
// this pane's Plane, opened in this pane, and "Pin" / "Unpin" puts the Plane
// in the sidebar's pinned row or takes it out (a Plane the sidebar draws
// only). "Delete plane" shows when `onDelete` is given, which it is not for a
// system Plane. A plane that has not landed (or is absent) gets the desk only.
//
// Under the next, one row per entry in ./settings.ts, each a label and a
// switch. The whole row is the item, so the arrows reach it and Enter, Space
// or a click anywhere on it flips the switch, and the menu stays open for the
// next one. The switch only shows the state; the row carries it for a screen
// reader.

import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuTrigger,
	IconButton,
	Switch,
} from "@nustackdev/ui-kit";
import { Ellipsis } from "lucide-react";
import { useState } from "react";
import { closePane, closePanes, openInNewTab, useRoutes } from "../core/router";
import {
	paneMenu,
	paneMenuHint,
	paneMenuLabel,
	paneMenuRow,
	paneMenuSwitch,
	paneMenuText,
} from "../design";
import type { PlaneMeta } from "../plane/types";
import { dropdownParts, type MenuParts } from "../shell/menu";
import { NEW_INSIDE_KEYS, openAddPlane } from "../sidebar/add";
import { usePlanePin } from "../sidebar/pin";
import { PLANE_SETTINGS, type PlaneSetting } from "./settings";

export type PaneMenuProps = {
	/** The pane's Plane, the parent "Add plane inside" makes a child of. */
	planeId: string;
	/** Null until the plane lands: the desk items only. */
	meta: PlaneMeta | null;
	onChange: (patch: Record<string, unknown>) => void;
	/** Adds a Delete plane row. Left out for a Plane that cannot be deleted. */
	onDelete?: () => void;
};

/** The `...` on a pane's bar. */
export function PaneMenu({
	open,
	onOpenChange,
	...props
}: PaneMenuProps & {
	/** Controlled open state; uncontrolled when left out. */
	open?: boolean;
	onOpenChange?: (open: boolean) => void;
}) {
	// Uncontrolled unless the caller says, so "Add plane inside" can shut it either way.
	const [own, setOwn] = useState(false);
	return (
		<DropdownMenu open={open ?? own} onOpenChange={onOpenChange ?? setOwn}>
			<DropdownMenuTrigger asChild>
				<IconButton variant="ghost" size="sm" aria-label="Plane settings">
					<Ellipsis />
				</IconButton>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end" className={paneMenu}>
				<PaneMenuItems parts={dropdownParts} {...props} />
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

/** The menu's items, rendered with whichever parts the trigger needs. */
export function PaneMenuItems({
	parts,
	planeId,
	meta,
	onChange,
	onDelete,
}: PaneMenuProps & { parts: MenuParts }) {
	const { Item, Separator, Shortcut } = parts;
	const routes = useRoutes();
	const pin = usePlanePin(planeId);
	const at = routes.indexOf(planeId);
	const others = routes.filter((id) => id !== planeId);
	const right = at < 0 ? [] : routes.slice(at + 1);
	return (
		<>
			{others.length > 0 ? (
				<>
					<Item onSelect={() => closePane(planeId)}>Close</Item>
					<Item onSelect={() => closePanes(others)}>Close others</Item>
					<Item disabled={right.length === 0} onSelect={() => closePanes(right)}>
						Close to the right
					</Item>
				</>
			) : null}
			{meta ? (
				<>
					{others.length > 0 ? <Separator /> : null}
					<Item onSelect={() => openInNewTab(planeId)}>Open in new tab</Item>
					<Item onSelect={() => openAddPlane({ parent: planeId, pane: planeId })}>
						Add plane inside
						<Shortcut keys={NEW_INSIDE_KEYS} />
					</Item>
					{pin ? <Item onSelect={pin.toggle}>{pin.pinned ? "Unpin" : "Pin"}</Item> : null}
					{onDelete ? (
						<Item variant="danger" onSelect={onDelete}>
							Delete plane
						</Item>
					) : null}
					<Separator />
					{PLANE_SETTINGS.map((s) => (
						<SettingRow key={s.key} parts={parts} setting={s} meta={meta} onChange={onChange} />
					))}
				</>
			) : null}
		</>
	);
}

function SettingRow({
	parts,
	setting,
	meta,
	onChange,
}: {
	parts: MenuParts;
	setting: PlaneSetting;
	meta: PlaneMeta;
	onChange: (patch: Record<string, unknown>) => void;
}) {
	const { Item } = parts;
	const on = meta[setting.key] === true;
	return (
		<Item
			role="menuitemcheckbox"
			aria-checked={on}
			className={paneMenuRow}
			onSelect={(e) => {
				e.preventDefault();
				onChange({ [setting.key]: !on });
			}}
		>
			<span className={paneMenuText}>
				<span className={paneMenuLabel}>{setting.label}</span>
				<span className={paneMenuHint}>{setting.hint}</span>
			</span>
			<Switch size="sm" checked={on} tabIndex={-1} aria-hidden className={paneMenuSwitch} />
		</Item>
	);
}
