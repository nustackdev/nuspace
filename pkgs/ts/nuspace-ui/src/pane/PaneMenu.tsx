// The `...` off a pane's bar or its tab: a small popover of plane settings.
//
// A list of rows, one per entry in ./settings.ts, each a label and a control.
// The whole row is the hit target for a switch, so it can be flipped from the
// label as well as the track.
//
// Above the settings, "Add plane" opens the Add plane popup for a child of
// this pane's Plane, opened in this pane. The tab bar adds a Rename row (only
// when `onRename` is given), and `open` / `onOpenChange` so a key on the tab
// can open it. "Delete plane" shows when `onDelete` is given, which it is not
// for a system Plane.

import { IconButton, Popover, PopoverContent, PopoverTrigger, Switch } from "@nustackdev/ui-kit";
import { Ellipsis } from "lucide-react";
import { useId, useRef, useState } from "react";
import {
	paneBarButton,
	paneMenu,
	paneMenuAction,
	paneMenuDanger,
	paneMenuHint,
	paneMenuLabel,
	paneMenuRow,
	paneMenuSeparator,
	paneMenuText,
} from "../design";
import type { PlaneMeta } from "../plane/types";
import { openAddPlane } from "../sidebar/add";
import { PLANE_SETTINGS, type PlaneSetting } from "./settings";

export function PaneMenu({
	planeId,
	meta,
	onChange,
	onRename,
	onDelete,
	open,
	onOpenChange,
	className = paneBarButton,
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
	/** The trigger's class. */
	className?: string;
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
	return (
		<Popover open={isOpen} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label="Plane settings"
					disabled={meta === null}
					className={className}
					tabIndex={tabIndex}
				>
					<Ellipsis />
				</IconButton>
			</PopoverTrigger>
			<PopoverContent
				align="end"
				className={paneMenu}
				onCloseAutoFocus={(e) => {
					if (!renaming.current) return;
					renaming.current = false;
					e.preventDefault();
				}}
			>
				{meta ? (
					<button
						type="button"
						className={paneMenuAction}
						onClick={() => {
							setOpen(false);
							openAddPlane({ parent: planeId, pane: planeId });
						}}
					>
						Add plane
					</button>
				) : null}
				{meta && onRename ? (
					<button
						type="button"
						className={paneMenuAction}
						onClick={() => {
							renaming.current = true;
							setOpen(false);
							onRename();
						}}
					>
						Rename
					</button>
				) : null}
				{meta && onDelete ? (
					<button
						type="button"
						className={paneMenuDanger}
						onClick={() => {
							setOpen(false);
							onDelete();
						}}
					>
						Delete plane
					</button>
				) : null}
				{meta ? <div className={paneMenuSeparator} aria-hidden="true" /> : null}
				{meta
					? PLANE_SETTINGS.map((s) => (
							<SettingRow key={s.key} setting={s} meta={meta} onChange={onChange} />
						))
					: null}
			</PopoverContent>
		</Popover>
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
	const id = useId();
	return (
		<label htmlFor={id} className={paneMenuRow}>
			<span className={paneMenuText}>
				<span className={paneMenuLabel}>{setting.label}</span>
				<span className={paneMenuHint}>{setting.hint}</span>
			</span>
			<Switch
				id={id}
				size="sm"
				checked={meta[setting.key] === true}
				onCheckedChange={(on) => onChange({ [setting.key]: on })}
			/>
		</label>
	);
}
