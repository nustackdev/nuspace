// What a cell is called by code and agents: its id and its key, in one small
// block the cell's identity toggle opens, the way the code toggle opens its
// source (./cell/Gutter.tsx).
//
// The id never changes: shown and copied, nothing else. The key is optional
// and changes here: Enter or Save sets it, an empty one removes it. Only its
// spelling is checked here (./key.ts); a key already taken is the server's to
// refuse, and that refusal toasts. Escape in the field closes the block.
//
// Without `onSave` (a read-only plane) the key shows and copies, and nothing
// saves. Kind-blind on purpose, so a plane can show the same block.

import {
	Button,
	IconButton,
	Input,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Copy, Info } from "lucide-react";
import { useEffect, useState } from "react";
import {
	docIdentity,
	docIdentityCopy,
	docIdentityError,
	docIdentityInput,
	docIdentityLabel,
	docIdentityLine,
	docIdentityNote,
	docIdentityValue,
} from "../design";
import { copyWithToast, keyProblem } from "./key";

/** One copy glyph, the same on both lines. */
function CopyButton({ text, label }: { text: string; label: string }) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				{/* A span, so the tooltip still hears a disabled button. */}
				<span className={docIdentityCopy}>
					<IconButton
						variant="ghost"
						size="xs"
						aria-label={label}
						disabled={text === ""}
						onClick={() => void copyWithToast(text)}
					>
						<Copy />
					</IconButton>
				</span>
			</TooltipTrigger>
			<TooltipContent side="top">{text === "" ? "No key to copy" : label}</TooltipContent>
		</Tooltip>
	);
}

export function Identity({
	kind,
	id,
	value,
	onSave,
	onClose,
}: {
	kind: "cell" | "plane";
	id: string;
	/** The key, "" for none. */
	value: string;
	/** Set the key, or "" to remove it. Left out where it cannot change. */
	onSave?: (key: string) => void;
	/** Escape in the key field. */
	onClose?: () => void;
}) {
	const [draft, setDraft] = useState(value);

	// A key that landed (this save, or one from elsewhere) is the field's again,
	// so Save goes quiet until the next edit.
	useEffect(() => setDraft(value), [value]);

	// Read off the field on every keystroke: empty is fine (it removes the key).
	const problem = draft === "" ? null : keyProblem(draft);
	const changed = draft !== value;
	const savable = onSave !== undefined && changed && problem === null;

	const save = () => {
		if (savable) onSave(draft);
	};

	return (
		<div className={docIdentity} data-identity={kind}>
			<div className={docIdentityLine}>
				<span className={docIdentityLabel}>ID</span>
				<span className={docIdentityValue} data-identity-id="">
					{id}
				</span>
				<CopyButton text={id} label={`Copy ${kind} id`} />
			</div>
			<div className={docIdentityLine}>
				<span className={docIdentityLabel}>Key</span>
				<Input
					size="sm"
					ring="inset"
					className={docIdentityInput}
					aria-label={`${kind} key`}
					placeholder={onSave ? "Add a key" : undefined}
					spellCheck={false}
					autoComplete="off"
					readOnly={!onSave}
					value={draft}
					invalid={problem !== null}
					onChange={(e) => setDraft(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							e.preventDefault();
							save();
						} else if (e.key === "Escape" && onClose) {
							e.preventDefault();
							onClose();
						}
					}}
				/>
				{onSave ? (
					<Button size="xs" disabled={!savable} onClick={save}>
						Save
					</Button>
				) : null}
				<CopyButton text={value} label={`Copy ${kind} key`} />
			</div>
			{problem ? (
				<p className={docIdentityError} role="alert">
					{problem}
				</p>
			) : null}
			{onSave ? (
				<p className={docIdentityNote}>
					<Info aria-hidden="true" />
					Renaming can break code or links that use the old key.
				</p>
			) : null}
		</div>
	);
}
