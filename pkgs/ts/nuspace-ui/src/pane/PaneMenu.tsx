// A pane's menu off the `...` on its header, a kit dropdown: "Copy plane
// link" (the plane url with this pane's params, confirmed in a toast);
// then Close where the pane has one (out of its strip, or the plane item out
// of its desk; a solo plane has none); then a plane's menu
// (../menu/PlaneMenuItems.tsx), the same groups as the sidebar row's, with
// what a pane adds. A group with nothing in it takes no separator. "Restart
// plane" runs it again, a fresh run for this pane; "Add plane inside" opens
// the child in this pane; "Delete plane" shows when `onDelete` is given,
// which it is not for a system Plane. A plane that has not landed (or is
// absent) gets the link and Close only.
//
// Its settings group is one row per entry in ./settings.ts. A switch is a
// label and a switch, the whole row the item, so the arrows reach it and
// Enter, Space or a click anywhere on it flips the switch, and the menu stays
// open for the next one. The switch only shows the state; the row carries it
// for a screen reader. A choice is its label over a row of tiles, one item
// per value, each a small picture of what it does over its name.

import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Switch,
} from "@nustackdev/ui-kit";
import { Ellipsis, Link, X } from "lucide-react";
import { useState } from "react";
import { hrefFor, paramsOf } from "../core/router";
import {
	type PlaneWidth,
	paneMenuChoice,
	paneMenuChoiceItem,
	paneMenuChoices,
	paneMenuHint,
	paneMenuLabel,
	paneMenuRow,
	paneMenuSwitch,
	paneMenuText,
	paneMenuWidthPicture,
	planeMenu,
} from "../design";
import { PlaneMenuItems } from "../menu/PlaneMenuItems";
import { dropdownParts, type MenuParts } from "../menu/parts";
import { copyWithToast } from "../plane/key";
import type { PlaneMeta } from "../plane/types";
import { openAddPlane } from "../sidebar/add";
import { PLANE_SETTINGS, type PlaneSetting } from "./settings";

export type PaneMenuProps = {
	/** The pane's Plane, the parent "Add plane inside" makes a child of. */
	planeId: string;
	/** Null until the plane lands: the pane's own rows only. */
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
	onClose,
	...props
}: PaneMenuProps & {
	/** Adds a Close row. Left out on a solo plane. */
	onClose?: () => void;
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
				<DropdownMenuItem onSelect={() => void copyWithToast(planeLink(props.planeId))}>
					<Link />
					{COPY_LINK}
				</DropdownMenuItem>
				{onClose ? (
					<>
						<DropdownMenuSeparator />
						<DropdownMenuItem onSelect={onClose}>
							<X />
							Close
						</DropdownMenuItem>
					</>
				) : null}
				{props.meta ? (
					<>
						<DropdownMenuSeparator />
						<PaneMenuItems parts={dropdownParts} {...props} />
					</>
				) : null}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

/** The pane menu's link row. */
export const COPY_LINK = "Copy plane link";

/** A plane link: the plane url with the pane's params, absolute. */
export function planeLink(planeId: string): string {
	return `${window.location.origin}${hrefFor(planeId, paramsOf(planeId))}`;
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
	if (!meta) return null;
	return (
		<PlaneMenuItems
			parts={parts}
			planeId={planeId}
			planeKey={meta.key}
			add={() => openAddPlane({ parent: planeId, pane: planeId })}
			restart={onRestart}
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
	if (setting.kind === "choice") {
		return (
			<div className={paneMenuChoice}>
				<span className={paneMenuLabel}>{setting.label}</span>
				<div className={paneMenuChoices}>
					{setting.options.map((o) => {
						const on = meta[setting.key] === o.value;
						return (
							<Item
								key={o.value}
								role="menuitemradio"
								aria-checked={on}
								className={paneMenuChoiceItem(on)}
								onSelect={(e) => {
									e.preventDefault();
									if (!on) onChange({ [setting.key]: o.value });
								}}
							>
								<WidthPicture width={o.value} />
								<span title={o.hint}>{o.label}</span>
							</Item>
						);
					})}
				</div>
			</div>
		);
	}
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

/** Where the content's lines start and how long they run, in a 32 wide pane. */
const WIDTH_LINES: Record<PlaneWidth, [number, number]> = {
	page: [11, 10],
	board: [7, 18],
	full: [3, 26],
};

/**
 * A width as a picture: a pane's outline and three lines of content as wide
 * as the setting lets them run. Sized inline, so the menu item's own icon
 * size never squares it.
 */
function WidthPicture({ width }: { width: PlaneWidth }) {
	const [x, w] = WIDTH_LINES[width];
	return (
		<svg
			viewBox="0 0 32 20"
			aria-hidden
			className={paneMenuWidthPicture}
			style={{ width: 32, height: 20 }}
		>
			<rect
				x={0.5}
				y={0.5}
				width={31}
				height={19}
				rx={2.5}
				fill="none"
				stroke="currentColor"
				strokeOpacity={0.45}
			/>
			<rect x={x} y={5} width={w} height={2} rx={1} fill="currentColor" />
			<rect x={x} y={9} width={w} height={2} rx={1} fill="currentColor" />
			<rect x={x} y={13} width={w * 0.6} height={2} rx={1} fill="currentColor" />
		</svg>
	);
}
