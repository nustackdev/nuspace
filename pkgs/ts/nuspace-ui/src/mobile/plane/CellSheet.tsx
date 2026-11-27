// A cell's options, what a tap on it opens while its plane's cells are
// edited (./editing.ts): one bottom sheet, two steps, and the source screen.
//
//   actions   the cell's facts and its last run, desktop's cell menu head
//             (../../plane/cell/InfoBlock.tsx), read-only, then Restart,
//             Copy id, View source, Delete (no delete where the plane
//             cannot be written). Key editing stays on desktop
//   delete    the confirm: Delete or Cancel, then desktop's Undo toast
//
// View source closes the sheet and opens the source full screen, read-only:
// a kit side sheet, which takes the whole screen on a phone. Copy id closes
// the sheet and says so in a toast. The ops are desktop's, on the pane's own
// node (../../plane/ops.ts); the facts are asked for by the tap that opens
// it (./MobilePlane.tsx), as desktop's menu asks as it opens.

import type { Path } from "@nustackdev/ui-core";
import {
	BottomSheet,
	BottomSheetContent,
	BottomSheetDescription,
	BottomSheetFooter,
	BottomSheetItem,
	Button,
	Code,
	DropdownMenuSeparator,
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
	toast,
} from "@nustackdev/ui-kit";
import { Code as CodeIcon, Copy, RotateCw, Trash2 } from "lucide-react";
import type * as React from "react";
import { useEffect, useState } from "react";
import { mobileSourceBody, mobileSourceTitle } from "../../design";
import { CellInfoBlock } from "../../plane/cell/InfoBlock";
import type { Cell } from "../../plane/types";
import { type CellAction, cellActions, copyToClipboard } from "./model";

/** The cell pressed, and the step its sheet is on. */
export type CellPressed = { id: string; step: "actions" | "delete" } | null;

export function CellSheet({
	panePath,
	cell,
	pressed,
	editable,
	onPressed,
	onRestart,
	onSource,
	onDelete,
}: {
	/** The pane node the cell's facts land on. */
	panePath: Path;
	/** The cell pressed, as it is now; undefined once it is gone. */
	cell: Cell | undefined;
	pressed: CellPressed;
	/** The plane can be written: Delete is offered. */
	editable: boolean;
	onPressed: (next: CellPressed) => void;
	onRestart: (id: string) => void;
	onSource: (id: string) => void;
	onDelete: (id: string) => void;
}) {
	// Held through the close, so the body does not empty while it slides away.
	const [shown, setShown] = useState<Exclude<CellPressed, null> | null>(pressed);
	useEffect(() => {
		if (pressed) setShown(pressed);
	}, [pressed]);
	const close = () => onPressed(null);
	const id = shown?.id ?? "";
	const label = cell?.key ? `@${cell.key}` : "Cell";

	const act = (action: CellAction) => {
		if (action === "delete") {
			onPressed({ id, step: "delete" });
			return;
		}
		close();
		if (action === "restart") onRestart(id);
		else if (action === "source") onSource(id);
		else
			void copyToClipboard(id).then((ok) =>
				toast(ok ? { title: "Cell id copied" } : { title: "Could not copy", description: id }),
			);
	};

	return (
		<BottomSheet open={pressed !== null && !!cell} onOpenChange={(open) => (open ? null : close())}>
			<BottomSheetContent
				title={shown?.step === "delete" ? "Delete this cell?" : label}
				label={label}
				data-cell-sheet={shown?.step ?? ""}
			>
				{!shown ? null : shown.step === "actions" ? (
					<>
						{cell ? (
							<>
								<CellInfoBlock
									panePath={panePath}
									cellId={cell.id}
									state={cell.status.state}
									error={cell.status.error ?? null}
								/>
								<DropdownMenuSeparator />
							</>
						) : null}
						<div role="menu">
							{cellActions(editable).map((action) => (
								<ActionRow key={action} action={action} onClick={() => act(action)} />
							))}
						</div>
					</>
				) : (
					<>
						<BottomSheetDescription>
							Its program and what it drew go with it.
						</BottomSheetDescription>
						<BottomSheetFooter>
							<Button
								variant="destructive"
								size="lg"
								onClick={() => {
									close();
									onDelete(id);
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

const ACTION_ROWS: Record<CellAction, { label: string; icon: React.ReactNode }> = {
	restart: { label: "Restart", icon: <RotateCw aria-hidden="true" /> },
	copy: { label: "Copy id", icon: <Copy aria-hidden="true" /> },
	source: { label: "View source", icon: <CodeIcon aria-hidden="true" /> },
	delete: { label: "Delete", icon: <Trash2 aria-hidden="true" /> },
};

function ActionRow({ action, onClick }: { action: CellAction; onClick: () => void }) {
	const { label, icon } = ACTION_ROWS[action];
	return (
		<BottomSheetItem
			role="menuitem"
			variant={action === "delete" ? "danger" : "default"}
			data-action={action}
			onClick={onClick}
		>
			{icon}
			{label}
		</BottomSheetItem>
	);
}

/** A cell's source, full screen and read-only. Closed by its X, back or Escape. */
export function SourceScreen({
	cell,
	open,
	onClose,
}: {
	cell: Cell | undefined;
	open: boolean;
	onClose: () => void;
}) {
	// Held through the close, like the sheet's body.
	const [shown, setShown] = useState(cell);
	useEffect(() => {
		if (cell) setShown(cell);
	}, [cell]);
	return (
		<Sheet open={open && !!cell} onOpenChange={(next) => (next ? null : onClose())}>
			<SheetContent side="right" data-source-screen="">
				<SheetHeader>
					<SheetTitle className={mobileSourceTitle}>
						{shown?.key ? `@${shown.key}` : shown?.id}
					</SheetTitle>
					<SheetDescription>Source, read-only</SheetDescription>
				</SheetHeader>
				<div className={mobileSourceBody}>
					<Code
						block
						value={shown?.source ?? ""}
						language="python"
						lineNumbers
						copyable
						maxHeight={0}
					/>
				</div>
			</SheetContent>
		</Sheet>
	);
}
