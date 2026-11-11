// One pane: a plane on the canvas. Its header on top (icon, title,
// actions), the plane under it in its body, a native scroller.
//
// Where it sits (`at`) is solo, a plane item, or a pane in a strip. In a
// strip a click focuses it (per tab, never stored), and the focused pane's
// title is the bright one (`data-focused` on the pane), the others dimmed.
// Solo and a plane item are always focused: there is nothing else to focus.
//
// `data-pane` is the plane the pane shows (its recent, else its original):
// the router finds the pane a link was clicked in by it, and navigates that
// pane in place.
//
// Close takes the pane out of its strip, or the plane item out of its desk.
// A solo plane has nothing to close.
//
// A pane whose Plane is absent (none by that id, or one that runs without a
// view) says so in place of the cells, with a way to close it where there is
// one, and offers no title or icon to edit. Its header carries the plane id.
//
// A pane whose Plane has not landed yet draws the viewer skeleton, the same
// one the boot draws, so a switch and a first load look alike.
//
// Under the title, the plane's `@key` when it has one, and the identity block
// its title row's `#` opens (./TitleIdentity.tsx). Like the title, the key is
// the plane's own, not one of its cells, but unlike the title it changes only
// on an editable plane.

import type { Path } from "@nustackdev/ui-core";
import { Button } from "@nustackdev/ui-kit";
import { useCallback, useRef, useState } from "react";
import { closeItem, closePane, focusPane } from "../core/router";
import {
	docRow,
	docTitleHead,
	docTitleIdentity,
	docTitleRow,
	paneBody,
	paneBodyScroll,
	shellPane,
} from "../design";
import type { PaneAt } from "../desk/drag";
import type { PlaneHandle } from "../plane/api";
import { Identity } from "../plane/Identity";
import type { Notify } from "../plane/ops";
import { Plane } from "../plane/Plane";
import type { AbsentReason, ActivePlane, CellSpec } from "../plane/types";
import type { Crumb } from "../sidebar/api";
import { GoHome, NOT_FOUND_TEXT, NotFoundBody } from "./NotFound";
import { PaneHeader } from "./PaneHeader";
import { focusTitle, Title } from "./Title";
import { TitleIcon } from "./TitleIcon";
import { IdentityToggle, KeyHandle } from "./TitleIdentity";
import { ViewerSkeleton } from "./ViewerSkeleton";

// The Plane the server inits with no name shows this instead. A placeholder,
// muted, so it cannot be mistaken for a title that is really there.
export const TITLE_FALLBACK = "Untitled";

/** What an absent pane says, per reason. */
export const ABSENT_TEXT: Record<AbsentReason, string> = {
	missing: NOT_FOUND_TEXT.plane,
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

/** What closes the pane showing `planeId` at `at`: undefined on a solo plane. */
export function closeOf(at: PaneAt, planeId: string): (() => void) | undefined {
	if (at.kind === "strip") return () => closePane(at.desk, at.item, planeId);
	if (at.kind === "plane") return () => closeItem(at.desk, at.item);
	return undefined;
}

const SOLO: PaneAt = { kind: "solo" };

export function Pane({
	viewerPath,
	at = SOLO,
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
	first = true,
	focused,
}: {
	viewerPath: Path;
	/** Where the pane sits: what its header drags as, what a click and close do. */
	at?: PaneAt;
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
	/** The planes above this one, top first, for the header's trail. */
	trail?: readonly Crumb[];
	/** The canvas's first pane, the one the sidebar's reopen button sits over. */
	first?: boolean;
	focused: boolean;
}) {
	// Capture, so a click that a cell handles and stops still moves focus.
	const [deskId, itemId] = at.kind === "strip" ? [at.desk, at.item] : ["", ""];
	const claim = useCallback(() => {
		if (deskId) focusPane(deskId, itemId, planeId);
	}, [deskId, itemId, planeId]);
	const close = closeOf(at, planeId);
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
			className={shellPane}
			aria-label={title}
			data-pane={planeId}
			data-focused={focused ? "" : undefined}
			onPointerDownCapture={claim}
		>
			<PaneHeader
				at={at}
				planeId={planeId}
				title={title}
				trail={absent ? [] : trail.map((c) => ({ ...c, title: c.title || TITLE_FALLBACK }))}
				meta={plane?.meta ?? null}
				onMeta={(patch) => onMeta(planeId, patch)}
				onDelete={onDelete}
				onRestart={absent ? undefined : () => notify("plane.restart", { plane_id: planeId })}
				onClose={close}
				first={first}
				focused={focused}
			/>
			<div className={paneBodyScroll}>
				{/* A press off the cells starts a box selection over them. */}
				<div className={paneBody} onPointerDown={(e) => planeHandle.current?.press(e)}>
					{absent ? (
						<NotFoundBody
							text={ABSENT_TEXT[absent]}
							action={
								close ? (
									<Button variant="ghost" size="sm" onClick={close}>
										Close
									</Button>
								) : (
									<GoHome />
								)
							}
						/>
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
			</div>
		</section>
	);
}
