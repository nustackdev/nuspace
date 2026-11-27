// A plane's rename, as a sheet step: one input, Save. The sidebar row's sheet
// (./sidebar/PlaneSheet.tsx) and the plane's own ⋯ sheet
// (./plane/PlaneInfoSheet.tsx) both show it; what a save sends is theirs.
//
// The title as it is now, selected, so typing replaces it. 16px text, so
// the phone does not zoom into it. An empty title is the plane's "Untitled".

import { BottomSheetFooter, Button, Input } from "@nustackdev/ui-kit";
import { useState } from "react";
import { mobileSheetForm, mobileSheetInput } from "../design";

export function RenameForm({ title, onSave }: { title: string; onSave: (title: string) => void }) {
	const [draft, setDraft] = useState(title);
	return (
		<form
			className={mobileSheetForm}
			data-rename-form=""
			onSubmit={(e) => {
				e.preventDefault();
				onSave(draft.trim());
			}}
		>
			<Input
				aria-label="Plane title"
				placeholder="Untitled"
				value={draft}
				onChange={(e) => setDraft(e.target.value)}
				autoFocus
				onFocus={(e) => e.currentTarget.select()}
				enterKeyHint="done"
				className={mobileSheetInput}
			/>
			<BottomSheetFooter>
				<Button type="submit" size="lg">
					Save
				</Button>
			</BottomSheetFooter>
		</form>
	);
}
