// The `...` off a pane's bar: a small popover of page settings.
//
// A list of rows, one per entry in ./settings.ts, each a label and a control.
// The whole row is the hit target for a switch, so it can be flipped from the
// label as well as the track.

import { IconButton, Popover, PopoverContent, PopoverTrigger, Switch } from "@nustackdev/ui-kit";
import { Ellipsis } from "lucide-react";
import { useId } from "react";
import {
	paneBarButton,
	paneMenu,
	paneMenuHint,
	paneMenuLabel,
	paneMenuRow,
	paneMenuText,
} from "../design";
import type { PageMeta } from "../page/types";
import { PAGE_SETTINGS, type PageSetting } from "./settings";

export function PaneMenu({
	meta,
	onChange,
}: {
	/** Null until the page lands; the menu stays shut until then. */
	meta: PageMeta | null;
	onChange: (patch: Record<string, unknown>) => void;
}) {
	return (
		<Popover>
			<PopoverTrigger asChild>
				<IconButton
					variant="ghost"
					size="sm"
					aria-label="Page settings"
					disabled={meta === null}
					className={paneBarButton}
				>
					<Ellipsis />
				</IconButton>
			</PopoverTrigger>
			<PopoverContent align="end" className={paneMenu}>
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
