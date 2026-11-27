// What the ⋯ on a plane's header opens (and on a desk's, for the pane on
// screen): one bottom sheet with the plane's facts, desktop's pane menu head
// (../../pane/PlaneInfoBlock.tsx), read-only, then the one plane action the
// pane menu has that the phone does: Delete, with a confirm, not on a system
// plane. Key editing stays on desktop.
//
//   info     the facts and the run, the id and the key, then Delete
//   delete   the confirm: what goes with it, Delete or Cancel
//
// The facts are asked for as it opens, on the pane's own node, the way the
// pane menu asks (../../plane/info.ts); each open asks again. Delete is the
// pane's own op, and the screen then leaves for home as it does for any
// plane that goes.

import type { Path } from "@nustackdev/ui-core";
import {
	BottomSheet,
	BottomSheetContent,
	BottomSheetDescription,
	BottomSheetFooter,
	BottomSheetItem,
	Button,
	DropdownMenuDetail,
	DropdownMenuDetails,
	DropdownMenuSeparator,
	pathKey,
} from "@nustackdev/ui-kit";
import { Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { notifyOp } from "../../core/wire";
import { PlaneInfoBlock } from "../../pane/PlaneInfoBlock";
import { clearPanePlaneInfo, panePath, usePaneHead } from "../../pane/state";
import { TITLE_FALLBACK } from "../../pane/titles";
import type { Ops } from "../../plane/ops";
import { deletedPlane } from "../../refs/toast";

type Step = "info" | "delete";

export function PlaneInfoSheet({
	viewerPath,
	planeId,
	open,
	onClose,
}: {
	viewerPath: Path;
	planeId: string;
	open: boolean;
	onClose: () => void;
}) {
	const viewerKey = pathKey(viewerPath);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const path = useMemo(() => panePath(viewerPath, planeId), [viewerKey, planeId]);
	const head = usePaneHead(path);
	const [step, setStep] = useState<Step>("info");

	// Asked for as it opens, from the info step.
	useEffect(() => {
		if (!open) return;
		setStep("info");
		clearPanePlaneInfo(path);
		notifyOp<Ops, "plane.info">(path, "plane.info", {});
	}, [open, path]);

	const title = head?.title || TITLE_FALLBACK;
	const key = head?.meta.key ?? "";
	return (
		<BottomSheet open={open && !!head} onOpenChange={(next) => (next ? null : onClose())}>
			<BottomSheetContent
				title={step === "delete" ? `Delete “${title}”?` : title}
				label={title}
				data-plane-info-sheet={step}
			>
				{!head ? null : step === "info" ? (
					<>
						<PlaneInfoBlock panePath={path} icon={String(head.meta.icon ?? "")} />
						<DropdownMenuDetails>
							<DropdownMenuDetail label="ID" mono>
								{planeId}
							</DropdownMenuDetail>
							{key ? (
								<DropdownMenuDetail label="Key" mono>
									@{key}
								</DropdownMenuDetail>
							) : null}
						</DropdownMenuDetails>
						{head.system ? null : (
							<>
								<DropdownMenuSeparator />
								<div role="menu">
									<BottomSheetItem
										role="menuitem"
										variant="danger"
										data-action="delete"
										onClick={() => setStep("delete")}
									>
										<Trash2 aria-hidden="true" />
										Delete plane
									</BottomSheetItem>
								</div>
							</>
						)}
					</>
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
									onClose();
									notifyOp<Ops, "plane.delete">(path, "plane.delete", {});
									deletedPlane(planeId, title);
								}}
							>
								Delete
							</Button>
							<Button variant="ghost" size="lg" onClick={onClose}>
								Cancel
							</Button>
						</BottomSheetFooter>
					</>
				)}
			</BottomSheetContent>
		</BottomSheet>
	);
}
