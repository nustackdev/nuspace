// One pane: a plane's frame on the desk. Its bar on top (title, settings,
// remove), the plane under it in its own scroll host.
//
// The pane last clicked (or tabbed into) is the focused one: that is the pane
// a plain sidebar click replaces. With more than one pane on the desk the
// others sit on a dimmed surface and the focused one keeps the canvas.
//
// A pane whose Plane is absent (none by that id, or one that runs without a
// view) says so in place of the cells, with a way to close it, and offers no
// title or icon to edit. Its bar and its dock chip carry the plane id.
//
// A pane whose Plane has not landed yet draws the viewer skeleton, the same
// one the boot draws, so a switch and a first load look alike.
//
// Under the title, the plane's `@key` when it has one, and the identity block
// its title row's `#` opens (./TitleIdentity.tsx). Like the title, the key is
// the plane's own, not one of its cells, but unlike the title it changes only
// on an editable plane.

import type { Path } from "@nustackdev/ui-core";
import { Button, EmptyState } from "@nustackdev/ui-kit";
import { useCallback, useRef, useState } from "react";
import { closePane, focusPane } from "../core/router";
import {
	docContentTrack,
	docPlaneAbsent,
	docRow,
	docTitleHead,
	docTitleIdentity,
	docTitleRow,
	shellPane,
	shellPaneDrop,
	shellPanePlane,
} from "../design";
import type { PlaneHandle } from "../plane/api";
import { Identity } from "../plane/Identity";
import type { Notify } from "../plane/ops";
import { Plane } from "../plane/Plane";
import type { AbsentReason, ActivePlane, CellSpec } from "../plane/types";
import type { Crumb } from "../sidebar/api";
import { PaneBar } from "./PaneBar";
import { focusTitle, Title } from "./Title";
import { TitleIcon } from "./TitleIcon";
import { IdentityToggle, KeyHandle } from "./TitleIdentity";
import { ViewerSkeleton } from "./ViewerSkeleton";

// The Plane the server inits with no name shows this instead. A placeholder,
// muted, so it cannot be mistaken for a title that is really there.
export const TITLE_FALLBACK = "Untitled";

/** What an absent pane says, per reason. */
export const ABSENT_TEXT: Record<AbsentReason, string> = {
	missing: "This plane doesn't exist",
	headless: "This plane runs without a view",
};

/** A pane's title: the plane's, the id for an absent one, else the fallback. */
export function paneTitle(
	planeId: string,
	plane: ActivePlane | null,
	absent: AbsentReason | null,
): string {
	return absent ? planeId : plane?.title || TITLE_FALLBACK;
}

export function Pane({
	viewerPath,
	planeId,
	plane,
	absent = null,
	cellSpecs,
	notify,
	onMeta,
	onRename,
	onIcon,
	onDelete,
	trail = [],
	many,
	divided,
	focused,
	drop = null,
}: {
	viewerPath: Path;
	planeId: string;
	/** Null until this Plane's `set_plane` lands. */
	plane: ActivePlane | null;
	/** Why there is no Plane to draw, once the server says so. */
	absent?: AbsentReason | null;
	cellSpecs: CellSpec[];
	notify: Notify;
	/** Change this plane's settings. */
	onMeta: (planeId: string, patch: Record<string, unknown>) => void;
	/** Rename this plane. */
	onRename: (planeId: string, title: string) => void;
	/** Set this plane's icon: a stored spelling, "" for none. */
	onIcon: (planeId: string, icon: string) => void;
	/** Delete this plane. Left out for one that cannot be deleted. */
	onDelete?: () => void;
	/** The planes above this one, top first, for the bar's trail. */
	trail?: readonly Crumb[];
	/** More than one pane on the desk: dim the unfocused, drag by the bar. */
	many: boolean;
	/** Not the desk's first pane, so the rail's reopen button is not over its bar. */
	divided: boolean;
	focused: boolean;
	/** A plane dragged off the rail would open on this side of it. */
	drop?: "before" | "after" | null;
}) {
	// Capture, so a click that a cell handles and stops still moves focus,
	// and a caret tabbed into the pane counts the same as a click.
	const claim = useCallback(() => focusPane(planeId), [planeId]);
	const title = paneTitle(planeId, plane, absent);
	const wide = plane?.meta.full_width === true;
	const compact = plane?.meta.compact === true;
	// The plane fills this in: the title reports its intents to it, and a
	// press anywhere in the pane can start a box selection over its cells.
	// The way back up is the title's own heading, which the plane puts the
	// caret in.
	const planeHandle = useRef<PlaneHandle | null>(null);
	const head = useRef<HTMLHeadingElement | null>(null);
	const toTitle = useCallback((at: "start" | "end") => {
		if (head.current) focusTitle(head.current, at);
	}, []);
	// The identity block is this pane's own business, like a cell's is the cell's.
	const [identity, setIdentity] = useState(false);
	const key = plane?.meta.key ?? "";
	const setKey = (next: string) =>
		next === ""
			? notify("plane.remove_key", { plane_id: planeId })
			: notify("plane.key", { plane_id: planeId, key: next });

	return (
		<section
			className={shellPane(many && !focused)}
			aria-label={title}
			onPointerDownCapture={claim}
			onFocusCapture={claim}
		>
			<PaneBar
				planeId={planeId}
				title={title}
				trail={absent ? [] : trail.map((c) => ({ ...c, title: c.title || TITLE_FALLBACK }))}
				meta={plane?.meta ?? null}
				onMeta={(patch) => onMeta(planeId, patch)}
				onDelete={onDelete}
				onRestart={absent ? undefined : () => notify("plane.restart", { plane_id: planeId })}
				onClose={() => closePane(planeId)}
				first={!divided}
				movable={many}
				closable={many}
				lit={many && focused}
			/>
			{/* A press off the cells starts a box selection over them. */}
			<div className={shellPanePlane} onPointerDown={(e) => planeHandle.current?.press(e)}>
				{absent ? (
					<div className={docPlaneAbsent}>
						<EmptyState
							className={docContentTrack}
							action={
								<Button variant="ghost" size="sm" onClick={() => closePane(planeId)}>
									Close
								</Button>
							}
						>
							{ABSENT_TEXT[absent]}
						</EmptyState>
					</div>
				) : plane == null ? (
					<ViewerSkeleton />
				) : (
					<>
						<header className={docTitleHead(wide, compact)}>
							<div className={docTitleRow}>
								<TitleIcon value={plane.meta.icon} onChange={(icon) => onIcon(planeId, icon)} />
								<Title
									value={plane.title}
									placeholder={TITLE_FALLBACK}
									onCommit={(next) => onRename(planeId, next)}
									onIntent={(i) => planeHandle.current?.title(i) ?? false}
									headRef={head}
								/>
								<IdentityToggle open={identity} onOpenChange={setIdentity} />
							</div>
							{key ? (
								<div className={docRow}>
									<KeyHandle value={key} />
								</div>
							) : null}
							{identity ? (
								<div className={docRow}>
									<div className={docTitleIdentity}>
										<Identity
											kind="plane"
											id={planeId}
											value={key}
											onSave={plane.meta.editable ? setKey : undefined}
											onClose={() => {
												setIdentity(false);
												toTitle("end");
											}}
										/>
									</div>
								</div>
							) : null}
						</header>
						<Plane
							viewerPath={viewerPath}
							plane={plane}
							cellSpecs={cellSpecs}
							editable={plane.meta.editable}
							wide={wide}
							compact={compact}
							notify={notify}
							handleRef={planeHandle}
							onTitle={toTitle}
							focused={focused}
						/>
					</>
				)}
			</div>
			{drop ? <div className={shellPaneDrop(drop)} aria-hidden="true" /> : null}
		</section>
	);
}
