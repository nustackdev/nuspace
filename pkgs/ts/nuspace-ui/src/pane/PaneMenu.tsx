// The `...` off a pane's bar or its tab: a small popover of page settings.
//
// A list of rows, one per entry in ./settings.ts, each a label and a control.
// The whole row is the hit target for a switch, so it can be flipped from the
// label as well as the track.
//
// The tab bar opens the same menu with two extras: a Rename row on top (only
// when `onRename` is given), and `open` / `onOpenChange` so a key on the tab
// can open it.

import { IconButton, Popover, PopoverContent, PopoverTrigger, Switch } from "@nustackdev/ui-kit";
import { Ellipsis } from "lucide-react";
import { useId, useRef } from "react";
import {
	paneBarButton,
	paneMenu,
	paneMenuAction,
	paneMenuHint,
	paneMenuLabel,
	paneMenuRow,
	paneMenuSeparator,
	paneMenuText,
} from "../design";
import type { PageMeta } from "../page/types";
import { PAGE_SETTINGS, type PageSetting } from "./settings";

export function PaneMenu({
	meta,
	onChange,
	onRename,
	open,
	onOpenChange,
	className = paneBarButton,
	tabIndex,
}: {
	/** Null until the page lands; the menu stays shut until then. */
	meta: PageMeta | null;
	onChange: (patch: Record<string, unknown>) => void;
	/** Adds a Rename row on top. The caller owns the inline editor. */
	onRename?: () => void;
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
	return (
		<Popover open={open} onOpenChange={onOpenChange}>
			<PopoverTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label="Page settings"
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
				{meta && onRename ? (
					<>
						<button
							type="button"
							className={paneMenuAction}
							onClick={() => {
								renaming.current = true;
								onOpenChange?.(false);
								onRename();
							}}
						>
							Rename
						</button>
						<div className={paneMenuSeparator} aria-hidden="true" />
					</>
				) : null}
				{meta
					? PAGE_SETTINGS.map((s) => (
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
	setting: PageSetting;
	meta: PageMeta;
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
