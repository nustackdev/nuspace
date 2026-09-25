// The `...` off a pane's bar or its tab: a kit dropdown of plane actions and
// settings.
//
// Above the separator, "Open in new tab" opens the Plane's URL in a browser
// tab, "Add plane" opens the Add plane popup for a child of this pane's Plane,
// opened in this pane, and "Pin" / "Unpin" puts the Plane in the sidebar's
// pinned row or takes it out (a Plane the sidebar draws only). The tab bar
// adds a Rename row (only when `onRename` is given), and `open` /
// `onOpenChange` so a key on the tab can open it. "Delete plane" shows when
// `onDelete` is given, which it is not for a system Plane.
//
// Under it, one row per entry in ./settings.ts, each a label and a switch.
// The whole row is the item, so the arrows reach it and Enter, Space or a
// click anywhere on it flips the switch, and the menu stays open for the
// next one. The switch only shows the state; the row carries it for a screen
// reader.

import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Switch,
} from "@nustackdev/ui-kit";
import { Ellipsis } from "lucide-react";
import { useRef, useState } from "react";
import { openInNewTab } from "../core/router";
import {
	paneMenu,
	paneMenuHint,
	paneMenuLabel,
	paneMenuRow,
	paneMenuSwitch,
	paneMenuText,
} from "../design";
import type { PlaneMeta } from "../plane/types";
import { openAddPlane } from "../sidebar/add";
import { usePlanePin } from "../sidebar/pin";
import { PLANE_SETTINGS, type PlaneSetting } from "./settings";

export function PaneMenu({
	planeId,
	meta,
	onChange,
	onRename,
	onDelete,
	open,
	onOpenChange,
	tabIndex,
}: {
	/** The pane's Plane, the parent "Add plane" makes a child of. */
	planeId: string;
	/** Null until the plane lands; the menu stays shut until then. */
	meta: PlaneMeta | null;
	onChange: (patch: Record<string, unknown>) => void;
	/** Adds a Rename row on top. The caller owns the inline editor. */
	onRename?: () => void;
	/** Adds a Delete plane row. Left out for a Plane that cannot be deleted. */
	onDelete?: () => void;
	/** Controlled open state; uncontrolled when left out. */
	open?: boolean;
	onOpenChange?: (open: boolean) => void;
	/** The trigger's tab stop. */
	tabIndex?: number;
}) {
	// Rename closes the menu and puts a caret in an input. Radix would hand
	// focus back to the trigger on close, which blurs, and so commits, that
	// input the moment it opens.
	const renaming = useRef(false);
	// Uncontrolled unless the caller says, so "Add plane" can shut it either way.
	const [own, setOwn] = useState(false);
	const isOpen = open ?? own;
	const setOpen = onOpenChange ?? setOwn;
	const pin = usePlanePin(planeId);
	return (
		<DropdownMenu open={isOpen} onOpenChange={setOpen}>
			<DropdownMenuTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label="Plane settings"
					disabled={meta === null}
					tabIndex={tabIndex}
				>
					<Ellipsis />
				</IconButton>
			</DropdownMenuTrigger>
			<DropdownMenuContent
				align="end"
				className={paneMenu}
				onCloseAutoFocus={(e) => {
					if (!renaming.current) return;
					renaming.current = false;
					e.preventDefault();
				}}
			>
				{meta ? (
					<>
						<DropdownMenuItem onSelect={() => openInNewTab(planeId)}>
							Open in new tab
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={() => openAddPlane({ parent: planeId, pane: planeId })}>
							Add plane
						</DropdownMenuItem>
						{pin ? (
							<DropdownMenuItem onSelect={pin.toggle}>
								{pin.pinned ? "Unpin" : "Pin"}
							</DropdownMenuItem>
						) : null}
						{onRename ? (
							<DropdownMenuItem
								onSelect={() => {
									renaming.current = true;
									onRename();
								}}
							>
								Rename
							</DropdownMenuItem>
						) : null}
						{onDelete ? (
							<DropdownMenuItem variant="danger" onSelect={onDelete}>
								Delete plane
							</DropdownMenuItem>
						) : null}
						<DropdownMenuSeparator />
						{PLANE_SETTINGS.map((s) => (
							<SettingRow key={s.key} setting={s} meta={meta} onChange={onChange} />
						))}
					</>
				) : null}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

function SettingRow({
	setting,
	meta,
	onChange,
}: {
	setting: PlaneSetting;
	meta: PlaneMeta;
	onChange: (patch: Record<string, unknown>) => void;
}) {
	const on = meta[setting.key] === true;
	return (
		<DropdownMenuItem
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
		</DropdownMenuItem>
	);
}
