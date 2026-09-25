// The plane's icon over its title, and the way to set one.
//
// Notion's: a set icon shows large above the title and opens the picker on a
// click. With none, the lane over the title holds a quiet "Add icon" that
// shows while the title block is hovered or it has focus. Every plane has
// this, editable or not: like the title, the icon is not one of its cells.
//
// Only the plane's own `meta.icon` shows here. The rail also falls back to the
// registered Plane's icon, but a plane view has no `made_by` to look up.

import { Button, Popover, PopoverTrigger } from "@nustackdev/ui-kit";
import { SmilePlus } from "lucide-react";
import { useState } from "react";
import { docAddIcon, docIconLane, docPlaneIcon } from "../design";
import { IconPickerContent } from "../icon/IconPicker";
import { PlaneIcon } from "../icon/PlaneIcon";
import { parseIcon } from "../icon/parse";

export function TitleIcon({
	value,
	onChange,
}: {
	/** The plane's `meta.icon`. */
	value: unknown;
	/** A stored spelling, "" for none. */
	onChange: (icon: string) => void;
}) {
	const [open, setOpen] = useState(false);
	const icon = parseIcon(value);
	const set = (next: string) => {
		setOpen(false);
		onChange(next);
	};

	return (
		<Popover open={open} onOpenChange={setOpen}>
			{icon ? (
				<PopoverTrigger asChild>
					<button type="button" aria-label="Change icon" className={docPlaneIcon}>
						<PlaneIcon icon={icon} size="lg" />
					</button>
				</PopoverTrigger>
			) : (
				<div className={docIconLane}>
					<PopoverTrigger asChild>
						<Button variant="ghost" size="sm" className={docAddIcon}>
							<SmilePlus aria-hidden="true" />
							Add icon
						</Button>
					</PopoverTrigger>
				</div>
			)}
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
