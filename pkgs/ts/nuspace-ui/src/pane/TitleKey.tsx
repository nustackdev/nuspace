// The plane's key, when it has one, as a small `@key` line under its title
// that copies on a click. No key, no line: a key is added, changed and
// removed from the pane's `...` menu (./PaneMenu.tsx).

import { Button, Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { useCopyRow } from "../core/clipboard";
import { docTitleKey, docTitleKeyLine } from "../design";

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
