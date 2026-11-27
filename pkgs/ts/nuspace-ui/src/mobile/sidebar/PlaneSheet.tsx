// What a long-press on a plane row opens: one bottom sheet, three steps.
//
//   actions   Rename, Add plane inside, Delete (no delete on a system plane)
//   rename    one input, Save; the title as it is now, selected
//   delete    the confirm: what goes with it, Delete or Cancel
//
// One sheet whose body changes, so a step never closes one sheet to open the
// next. The ops are desktop's (../../sidebar/ops.ts); delete toasts an Undo
// like desktop's row delete does. Deleting what the screen shows closes the
// sidebar first: the screen then leaves for home from a plain entry, and
// back never lands on a sidebar over a plane that is gone.

import {
	BottomSheet,
	BottomSheetContent,
	BottomSheetDescription,
	BottomSheetFooter,
	BottomSheetItem,
	Button,
	Input,
} from "@nustackdev/ui-kit";
import { FilePlus, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { focusedRoute } from "../../core/router";
import { mobileSheetForm, mobileSheetInput } from "../../design";
import { openAddPlane } from "../../sidebar/add";
import type { Notify } from "../../sidebar/ops";
import { deletePlane } from "../../sidebar/remove";
import { subtreeOf } from "../../sidebar/tree";
import type { PlaneTree } from "../../sidebar/types";
import { planeActions } from "./model";
import { leaveThen } from "./open";

/** The row pressed, and the step its sheet is on. */
export type Pressed = { id: string; step: "actions" | "rename" | "delete" } | null;

export function PlaneSheet({
	tree,
	pressed,
	onPressed,
	notify,
}: {
	tree: PlaneTree;
	pressed: Pressed;
	onPressed: (next: Pressed) => void;
	notify: Notify;
}) {
	// Held through the close, so the body does not empty while it slides away.
	const [shown, setShown] = useState<Exclude<Pressed, null> | null>(pressed);
	useEffect(() => {
		if (pressed) setShown(pressed);
	}, [pressed]);
	const row = shown ? tree[shown.id] : undefined;
	const title = row?.title || "Untitled";
	const close = () => onPressed(null);

	return (
		<BottomSheet open={pressed !== null} onOpenChange={(open) => (open ? null : close())}>
			<BottomSheetContent
				title={
					shown?.step === "delete"
						? `Delete “${title}”?`
						: shown?.step === "rename"
							? "Rename plane"
							: title
				}
				label={title}
				data-plane-sheet={shown?.step ?? ""}
			>
				{!shown || !row ? null : shown.step === "actions" ? (
					<Actions
						actions={planeActions(tree, shown.id)}
						onRename={() => onPressed({ id: shown.id, step: "rename" })}
						onInside={() => {
							close();
							openAddPlane({ parent: shown.id });
						}}
						onDelete={() => onPressed({ id: shown.id, step: "delete" })}
					/>
				) : shown.step === "rename" ? (
					<Rename
						title={row.title}
						onSave={(next) => {
							if (next !== row.title) notify("plane.rename", { plane_id: shown.id, title: next });
							close();
						}}
					/>
				) : (
					<>
						<BottomSheetDescription>
							Every cell on it and every plane inside it go too.
						</BottomSheetDescription>
						<BottomSheetFooter>
							<Button
								variant="destructive"
								size="lg"
								onClick={() => {
									const id = shown.id;
									close();
									// On screen (or under it): closed first, so the move home lands on a plain entry.
									if (subtreeOf(tree, id).includes(focusedRoute()))
										leaveThen(() => deletePlane(notify, id, title));
									else deletePlane(notify, id, title);
								}}
							>
								Delete
							</Button>
							<Button variant="ghost" size="lg" onClick={close}>
								Cancel
							</Button>
						</BottomSheetFooter>
					</>
				)}
			</BottomSheetContent>
		</BottomSheet>
	);
}

function Actions({
	actions,
	onRename,
	onInside,
	onDelete,
}: {
	actions: ReturnType<typeof planeActions>;
	onRename: () => void;
	onInside: () => void;
	onDelete: () => void;
}) {
	return (
		<div role="menu">
			{actions.map((action) =>
				action === "rename" ? (
					<BottomSheetItem key={action} role="menuitem" onClick={onRename}>
						<Pencil aria-hidden="true" />
						Rename
					</BottomSheetItem>
				) : action === "inside" ? (
					<BottomSheetItem key={action} role="menuitem" onClick={onInside}>
						<FilePlus aria-hidden="true" />
						Add plane inside
					</BottomSheetItem>
				) : (
					<BottomSheetItem key={action} role="menuitem" variant="danger" onClick={onDelete}>
						<Trash2 aria-hidden="true" />
						Delete
					</BottomSheetItem>
				),
			)}
		</div>
	);
}

/** The rename step: one input, Save. An empty title is the plane's "Untitled". */
function Rename({ title, onSave }: { title: string; onSave: (title: string) => void }) {
	const [draft, setDraft] = useState(title);
	return (
		<form
			className={mobileSheetForm}
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
