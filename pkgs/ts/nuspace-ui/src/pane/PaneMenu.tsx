// A pane's menu off the `...` on its bar, a kit dropdown: a plane's menu
// (../menu/PlaneMenuItems.tsx), the same groups as the rail row's, with what a
// pane adds. Its close group closes this pane, the others,
// or the ones to its right; "Restart plane" runs it again, a fresh run for this
// pane; "Add plane inside" opens the child in this pane; "Delete plane" shows
// when `onDelete` is given, which it is not for a system Plane. A plane that
// has not landed (or is absent) gets the close group only.
//
// Its settings group is one row per entry in ./settings.ts, each a label and a
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
import {
	paneMenuHint,
	paneMenuLabel,
	paneMenuRow,
	paneMenuSwitch,
	paneMenuText,
	planeMenu,
} from "../design";
import { DeskMenuItems, PlaneMenuItems } from "../menu/PlaneMenuItems";
import { dropdownParts, type MenuParts } from "../menu/parts";
import type { PlaneMeta } from "../plane/types";
import { openAddPlane } from "../sidebar/add";
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
	/** Adds a Restart plane row. */
	onRestart?: () => void;
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
			<DropdownMenuContent align="end" className={planeMenu}>
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
	onRestart,
}: PaneMenuProps & { parts: MenuParts }) {
	const pin = usePlanePin(planeId);
	if (!meta) return <DeskMenuItems parts={parts} planeId={planeId} />;
	return (
		<PlaneMenuItems
			parts={parts}
			planeId={planeId}
			add={() => openAddPlane({ parent: planeId, pane: planeId })}
			pin={pin}
			restart={onRestart}
			desk
			settings={PLANE_SETTINGS.map((s) => (
				<SettingRow key={s.key} parts={parts} setting={s} meta={meta} onChange={onChange} />
			))}
			remove={onDelete}
		/>
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
