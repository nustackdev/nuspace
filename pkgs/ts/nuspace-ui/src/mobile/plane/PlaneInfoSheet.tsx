// What the ⋯ on a plane's header opens (and on a desk's, for the pane on
// screen): one bottom sheet with the plane's facts, desktop's pane menu head
// (../../pane/PlaneInfoBlock.tsx), read-only, then the plane actions of the
// pane menu the phone has, in its order: Add plane inside, Rename, Change
// icon, Restart, and Delete with a confirm, not on a system plane. Key
// editing stays on desktop.
//
//   info     the facts and the run, the id and the key, then the actions
//   rename   one input, Save (../RenameForm.tsx)
//   icon     the kit's icon picker, filling the sheet: a pick sets it, Remove
//            puts the default back, as desktop's title icon does
//   delete   the confirm: what goes with it, Delete or Cancel
//
// One sheet whose body changes, so a step never closes one sheet to open the
// next. The facts are asked for as it opens, on the pane's own node, the way
// the pane menu asks (../../plane/info.ts); each open asks again. Every
// action is the pane's own op, as on desktop's pane. Rename and icon land on
// the pane at once and the next head confirms them. A restart closes the
// sheet and the cells run again in place; a delete leaves the screen for
// home, as it does for any plane that goes. Add plane inside closes it and
// opens the add sheet for a child (../sidebar/AddPlaneSheet.tsx).

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
	formatIcon,
	IconPicker,
	pathKey,
} from "@nustackdev/ui-kit";
import { FilePlus, Pencil, RotateCcw, SmilePlus, Trash2 } from "lucide-react";
import type * as React from "react";
import { useEffect, useMemo, useState } from "react";
import { notifyOp } from "../../core/wire";
import { DEFAULT_ICON, RECENT_ICONS } from "../../icon/parse";
import { PlaneInfoBlock } from "../../pane/PlaneInfoBlock";
import {
	clearPanePlaneInfo,
	panePath,
	patchPaneMeta,
	patchPaneTitle,
	usePaneHead,
} from "../../pane/state";
import { TITLE_FALLBACK } from "../../pane/titles";
import type { Ops } from "../../plane/ops";
import { deletedPlane } from "../../refs/toast";
import { openAddPlane } from "../../sidebar/add";
import { RenameForm } from "../RenameForm";
import { type PlaneInfoAction, planeInfoActions } from "./model";

type Step = "info" | "rename" | "icon" | "delete";

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
	const icon = head?.meta.icon;

	const act = (action: PlaneInfoAction) => {
		if (action === "rename" || action === "icon" || action === "delete") {
			setStep(action);
			return;
		}
		onClose();
		if (action === "inside") openAddPlane({ parent: planeId, pane: planeId });
		else notifyOp<Ops, "plane.restart">(path, "plane.restart", {});
	};
	const rename = (next: string) => {
		onClose();
		if (next === (head?.title ?? "")) return;
		patchPaneTitle(path, next);
		notifyOp<Ops, "plane.rename">(path, "plane.rename", { title: next });
	};
	const setIcon = (next: string) => {
		onClose();
		patchPaneMeta(path, { icon: next });
		notifyOp<Ops, "plane.icon">(path, "plane.icon", { icon: next });
	};

	return (
		<BottomSheet open={open && !!head} onOpenChange={(next) => (next ? null : onClose())}>
			<BottomSheetContent
				title={STEP_TITLE[step]?.(title) ?? title}
				label={title}
				data-plane-info-sheet={step}
			>
				{!head ? null : step === "info" ? (
					<>
						<PlaneInfoBlock panePath={path} icon={String(icon ?? "")} />
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
						<DropdownMenuSeparator />
						<div role="menu">
							{planeInfoActions(head.system).map((action) => (
								<ActionRow key={action} action={action} onClick={() => act(action)} />
							))}
						</div>
					</>
				) : step === "rename" ? (
					<RenameForm title={head.title} onSave={rename} />
				) : step === "icon" ? (
					<IconPicker
						value={typeof icon === "string" ? icon : ""}
						onPick={setIcon}
						onRemove={() => setIcon(formatIcon(DEFAULT_ICON))}
						recentKey={RECENT_ICONS}
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

/** The sheet's title on a step other than the facts, from the plane's title. */
const STEP_TITLE: Partial<Record<Step, (title: string) => string>> = {
	rename: () => "Rename plane",
	icon: () => "Change icon",
	delete: (title) => `Delete “${title}”?`,
};

const ACTION_ROWS: Record<PlaneInfoAction, { label: string; icon: React.ReactNode }> = {
	inside: { label: "Add plane inside", icon: <FilePlus aria-hidden="true" /> },
	rename: { label: "Rename", icon: <Pencil aria-hidden="true" /> },
	icon: { label: "Change icon", icon: <SmilePlus aria-hidden="true" /> },
	restart: { label: "Restart plane", icon: <RotateCcw aria-hidden="true" /> },
	delete: { label: "Delete plane", icon: <Trash2 aria-hidden="true" /> },
};

function ActionRow({ action, onClick }: { action: PlaneInfoAction; onClick: () => void }) {
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
