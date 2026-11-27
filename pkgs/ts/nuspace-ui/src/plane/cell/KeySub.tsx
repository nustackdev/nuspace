// A cell's key: a row of its menu with a submenu (./Gutter.tsx), and the
// popover that edits it.
//
// The row says the key, or that there is none. Its submenu copies it,
// removes it, and offers "Edit key…", which closes the menu and opens
// `KeyEditor` on the cell's grip. The field lives in a popover, not in the
// menu: a menu holds items only, and a field among them is neither a menu
// item to a screen reader nor safe from the pointer moving focus to the
// row under it.
//
// In the editor, Enter or Save sets the key and closes it, an empty one
// removes the key, Escape closes it unchanged. Only the spelling is checked
// here (../key.ts); a key already taken is the server's to refuse, and that
// refusal toasts. On a read-only plane the submenu only copies.

import {
	Button,
	DropdownMenuItem,
	DropdownMenuShortcut,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	Input,
} from "@nustackdev/ui-kit";
import { AtSign, Check, Copy, Info, Pen, Trash2 } from "lucide-react";
import { useId, useState } from "react";
import { useCopyRow } from "../../core/clipboard";
import { keyProblem } from "../key";

/** The menu row and its submenu. */
export function KeySub({
	cellKey,
	onEdit,
	onRemove,
}: {
	/** "" for none. */
	cellKey: string;
	/** Open the editor. Left out on a read-only plane. */
	onEdit?: () => void;
	/** Drop the key. Left out on a read-only plane. */
	onRemove?: () => void;
}) {
	const copy = useCopyRow(cellKey);
	return (
		<DropdownMenuSub>
			<DropdownMenuSubTrigger aria-label={cellKey ? `Cell key ${cellKey}` : "Cell key, none"}>
				<AtSign />
				<span
					className={
						cellKey
							? "min-w-0 truncate font-mono text-xs"
							: "min-w-0 truncate text-xs text-text-muted"
					}
				>
					{cellKey || "no key"}
				</span>
			</DropdownMenuSubTrigger>
			<DropdownMenuSubContent>
				{onEdit ? (
					<DropdownMenuItem onSelect={onEdit}>
						<Pen />
						{cellKey ? "Edit key…" : "Add key…"}
					</DropdownMenuItem>
				) : null}
				<DropdownMenuItem disabled={!cellKey} onSelect={copy.onSelect}>
					{copy.copied ? <Check /> : <Copy />}
					Copy key
					{copy.copied ? <DropdownMenuShortcut>Copied</DropdownMenuShortcut> : null}
				</DropdownMenuItem>
				{onRemove && cellKey ? (
					<DropdownMenuItem variant="danger" onSelect={onRemove}>
						<Trash2 />
						Remove key
					</DropdownMenuItem>
				) : null}
			</DropdownMenuSubContent>
		</DropdownMenuSub>
	);
}

/** The editor, the body of the popover on the grip. */
export function KeyEditor({
	value,
	onSave,
	onClose,
}: {
	/** The key, "" for none. */
	value: string;
	/** Set the key, "" to remove it. */
	onSave: (key: string) => void;
	onClose: () => void;
}) {
	const [draft, setDraft] = useState(value);
	const id = useId();
	const problem = draft === "" ? null : keyProblem(draft);
	const savable = draft !== value && problem === null;
	const save = () => {
		if (!savable) return;
		onSave(draft);
		onClose();
	};

	return (
		<form
			className="flex flex-col gap-2"
			onSubmit={(e) => {
				e.preventDefault();
				save();
			}}
		>
			<label htmlFor={id} className="text-xs font-medium text-text-secondary">
				Cell key
			</label>
			<Input
				id={id}
				size="sm"
				placeholder="Add a key"
				spellCheck={false}
				autoComplete="off"
				autoFocus
				value={draft}
				invalid={problem !== null}
				aria-describedby={problem ? `${id}-problem ${id}-note` : `${id}-note`}
				onChange={(e) => setDraft(e.target.value)}
			/>
			{problem ? (
				<p id={`${id}-problem`} role="alert" className="text-xs text-status-danger">
					{problem}
				</p>
			) : null}
			<p id={`${id}-note`} className="flex items-start gap-1.5 text-xs text-text-muted">
				<Info aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
				Renaming can break code or links that use the old key.
			</p>
			<div className="flex justify-end gap-2">
				<Button type="button" size="sm" variant="ghost" onClick={onClose}>
					Cancel
				</Button>
				<Button type="submit" size="sm" disabled={!savable}>
					{draft === "" && value ? "Remove" : "Save"}
				</Button>
			</div>
		</form>
	);
}
