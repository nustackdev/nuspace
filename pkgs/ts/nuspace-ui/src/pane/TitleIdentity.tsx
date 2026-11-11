// What a plane is called by code and agents, next to its title: the `#` toggle
// in the title row's right gutter, where a cell's sits on its row, opens the
// identity block (../plane/Identity.tsx) under the title; and the plane's key,
// when it has one, as a small `@key` line under the title that copies on a
// click. No key, no line: nothing invites adding one but the block.

import { Button, Toggle, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { Hash } from "lucide-react";
import { useCopyRow } from "../core/clipboard";
import { docGutterToggle, docTitleGutter, docTitleKey, docTitleKeyLine } from "../design";

/** The title row's right gutter: the identity toggle. */
export function IdentityToggle({
	open,
	onOpenChange,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const label = open ? "Hide id and key" : "Show id and key";
	return (
		<div className={docTitleGutter} data-pinned={open ? "" : undefined}>
			<Tooltip>
				<TooltipTrigger asChild>
					<Toggle
						size="sm"
						pressed={open}
						onPressedChange={onOpenChange}
						aria-label={label}
						data-plane-identity=""
						className={docGutterToggle}
					>
						<Hash />
					</Toggle>
				</TooltipTrigger>
				<TooltipContent side="top">{label}</TooltipContent>
			</Tooltip>
		</div>
	);
}

/** The plane's `@key` under its title. Not an editor: a click copies it. */
export function KeyHandle({ value }: { value: string }) {
	const { copied, copy } = useCopyRow(value);
	return (
		<div className={docTitleKeyLine}>
			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						variant="ghost"
						size="xs"
						aria-label="Copy key"
						data-plane-key=""
						className={docTitleKey}
						onClick={copy}
					>
						{copied ? "Copied" : `@${value}`}
					</Button>
				</TooltipTrigger>
				<TooltipContent side="bottom">Copy key</TooltipContent>
			</Tooltip>
		</div>
	);
}
