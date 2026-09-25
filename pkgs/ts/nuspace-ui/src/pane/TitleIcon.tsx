// The plane's icon, beside its title, and the way to change it.
//
// Always there: the plane's own `meta.icon`, else its registered Plane's, else
// the page icon, the same line the rail follows. A click, or Enter on it,
// opens the picker anchored on it; that is its only job. Every plane has
// this, editable or not: like the title, the icon is not one of its cells.

import {
	Popover,
	PopoverTrigger,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { useState } from "react";
import { docPlaneIcon } from "../design";
import { IconPickerContent } from "../icon/IconPicker";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";

export function TitleIcon({
	value,
	registered = "",
	onChange,
}: {
	/** The plane's `meta.icon`. */
	value: unknown;
	/** Its registered Plane's icon, the fallback. "" for none. */
	registered?: string;
	/** A stored spelling, "" for none. */
	onChange: (icon: string) => void;
}) {
	const [open, setOpen] = useState(false);
	const set = (next: string) => {
		setOpen(false);
		onChange(next);
	};

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<Tooltip>
				<TooltipTrigger asChild>
					<PopoverTrigger asChild>
						<button type="button" aria-label="Change icon" className={docPlaneIcon}>
							<PlaneIcon icon={planeIcon(value, registered)} size="lg" />
						</button>
					</PopoverTrigger>
				</TooltipTrigger>
				<TooltipContent side="bottom">Change icon</TooltipContent>
			</Tooltip>
			<IconPickerContent
				value={typeof value === "string" ? value : ""}
				onPick={set}
				onRemove={() => set("")}
				side="bottom"
				align="start"
			/>
		</Popover>
	);
}
