// One pane: a plane on the canvas. Its header on top (icon, title,
// actions), the plane under it in its body, a native scroller.
//
// It reads its own PaneRef node (./state.ts) and nothing else: head, cells,
// trail and why it is absent all ride that node, and every op it sends
// rides that node's path (rename, icon, delete, key, flags, restart and the
// plane's cell ops). Its `...` offers delete off its own head's `system`.
// A delete sends the op and nothing more: when the plane goes, every pane on
// it (or under it) turns absent `missing`, and a pane that had a plane and
// turns missing leaves (`leavePlanes`: a solo plane goes home, a desk item is
// pruned by the server).
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
// A pane whose head or cells have not landed yet draws the viewer skeleton,
// the same one the boot draws, so a switch and a first load look alike.
//
// The body's scroll is the node's too: `set_follow` keeps it at its end as
// it grows, `scroll` moves it once (./scroll.ts). The server or a cell on the
// pane sends them.
//
// Under the title, the plane's `@key` when it has one, and the identity block
// its title row's `#` opens (./TitleIdentity.tsx). Like the title, the key is
// the plane's own, not one of its cells, but unlike the title it changes only
// on an editable plane.

import type { Path } from "@nustackdev/ui-core";
import { Button, pathKey, ScrollArea } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { confirm } from "../core/confirm";
import { closeItem, closePane, focusPane, leavePlanes } from "../core/router";
import { notifyOp } from "../core/wire";
import {
	docRow,
	docTitleHead,
	docTitleIdentity,
	docTitleLine,
	docTitleRow,
	paneBody,
	paneBodyScroll,
	paneBodyViewport,
	shellPane,
} from "../design";
import type { PaneAt } from "../desk/drag";
import type { PlaneHandle } from "../plane/api";
import { Identity } from "../plane/Identity";
import type { Notify, Ops } from "../plane/ops";
import { Plane } from "../plane/Plane";
import type { AbsentReason, ActivePlane, CellSpec, PaneHead } from "../plane/types";
import { GoHome, NOT_FOUND_TEXT, NotFoundBody } from "./NotFound";
import { PaneHeader } from "./PaneHeader";
import { useScroller } from "./scroll";
import {
	markScrolled,
	panePath,
	patchPaneMeta,
	patchPaneTitle,
	usePaneAbsent,
	usePaneCells,
	usePaneFollow,
	usePaneHead,
	usePaneScroll,
	usePaneScrolled,
	usePaneTrail,
} from "./state";
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
	head: { title: string } | null,
	absent: AbsentReason | null,
): string {
	return absent ? planeId : head?.title || TITLE_FALLBACK;
}

/**
 * Ask, then delete the pane's plane and everything under it. Nothing else:
 * the panes on what went leave as they turn missing.
 */
export async function deleteFromPane(notify: Notify, title: string): Promise<void> {
	const yes = await confirm({
		title: "Delete plane",
		description: `Delete "${title}" and everything under it?`,
		action: "Delete",
	});
	if (yes) notify("plane.delete", {});
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
	cellSpecs,
	focused,
}: {
	/** The ViewerRef node: the panes and every cell's ui hang under it. */
	viewerPath: Path;
	/** Where the pane sits: what its header drags as, what a click and close do. */
	at?: PaneAt;
	planeId: string;
	cellSpecs: CellSpec[];
	focused: boolean;
}) {
	const viewerKey = pathKey(viewerPath);
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const path = useMemo(() => panePath(viewerPath, planeId), [viewerKey, planeId]);
	const head = usePaneHead(path);
	const cells = usePaneCells(path);
	const trail = usePaneTrail(path);
	const absent = usePaneAbsent(path);
	const plane = usePlane(planeId, head, cells);

	// The body's scroll, as the node says.
	const viewport = useRef<HTMLDivElement | null>(null);
	const content = useRef<HTMLDivElement | null>(null);
	const onScrolled = useCallback((seq: string) => markScrolled(path, seq), [path]);
	useScroller({
		viewport,
		content,
		follow: usePaneFollow(path),
		scroll: usePaneScroll(path),
		applied: usePaneScrolled(path),
		ready: plane != null,
		onApplied: onScrolled,
	});

	// One ref per op, on this pane's own node: the path says the plane.
	const notify = useCallback<Notify>(
		(op, args) => notifyOp<Ops, typeof op>(path, op, args),
		[path],
	);

	// Optimistic: the switch moves now, the next `set_head` confirms it.
	const onMeta = (patch: Record<string, unknown>) => {
		patchPaneMeta(path, patch);
		const flags = Object.fromEntries(
			Object.entries(patch).filter(([, v]) => typeof v === "boolean" || typeof v === "string"),
		) as Record<string, boolean | string>;
		notify("plane.web", { flags });
	};
	const onRename = (title: string) => {
		patchPaneTitle(path, title);
		notify("plane.rename", { title });
	};
	const onIcon = (icon: string) => {
		patchPaneMeta(path, { icon });
		notify("plane.icon", { icon });
	};

	// A pane that had its plane and turns missing leaves: the plane went.
	const had = useRef(false);
	useEffect(() => {
		if (head) had.current = true;
	}, [head]);
	useEffect(() => {
		if (absent === "missing" && had.current) leavePlanes([planeId], true);
	}, [absent, planeId]);

	// Capture, so a click that a cell handles and stops still moves focus.
	const [deskId, itemId] = at.kind === "strip" ? [at.desk, at.item] : ["", ""];
	const claim = useCallback(() => {
		if (deskId) focusPane(deskId, itemId, planeId);
	}, [deskId, itemId, planeId]);
	const close = closeOf(at, planeId);
	const title = paneTitle(planeId, head, absent);
	const onDelete =
		head && !head.system ? () => void deleteFromPane(notify, head.title || planeId) : undefined;
	const width = plane?.meta.width ?? "page";
	// The plane fills this in: the title reports its intents to it, and a
	// press anywhere in the pane can start a box selection over its cells.
	// The way back up is the title's own heading, which the plane puts the
	// caret in.
	const planeHandle = useRef<PlaneHandle | null>(null);
	const headRef = useRef<HTMLHeadingElement | null>(null);
	const toTitle = useCallback((at: "start" | "end") => {
		if (headRef.current) focusTitle(headRef.current, at);
	}, []);
	// The identity block is this pane's own business, like a cell's is the cell's.
	const [identity, setIdentity] = useState(false);
	const key = plane?.meta.key ?? "";
	const setKey = (next: string) =>
		next === "" ? notify("plane.remove_key", {}) : notify("plane.key", { key: next });

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
				meta={head?.meta ?? null}
				onMeta={onMeta}
				onDelete={onDelete}
				onRestart={absent ? undefined : () => notify("plane.restart", {})}
				onClose={close}
				focused={focused}
			/>
			<ScrollArea
				className={paneBodyScroll}
				viewportClassName={paneBodyViewport}
				viewportRef={viewport}
			>
				{/* A press off the cells starts a box selection over them. */}
				<div
					ref={content}
					className={paneBody}
					onPointerDown={(e) => planeHandle.current?.press(e)}
				>
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
							<header className={docTitleHead(width)}>
								<div className={docTitleRow}>
									<div className={docTitleLine}>
										<TitleIcon value={plane.meta.icon} onChange={onIcon} />
										<Title
											value={plane.title}
											placeholder={TITLE_FALLBACK}
											onCommit={onRename}
											onIntent={(i) => planeHandle.current?.title(i) ?? false}
											headRef={headRef}
										/>
									</div>
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
								panePath={path}
								plane={plane}
								cellSpecs={cellSpecs}
								editable={plane.meta.editable}
								width={width}
								notify={notify}
								handleRef={planeHandle}
								onTitle={toTitle}
								focused={focused}
							/>
						</>
					)}
				</div>
			</ScrollArea>
		</section>
	);
}

const NO_PLANE = null;

/** The pane's plane as its body draws it: head and cells, once both landed. */
function usePlane(planeId: string, head: PaneHead | null, cells: ActivePlane["cells"] | null) {
	return useMemo<ActivePlane | null>(
		() =>
			head && cells ? { plane_id: planeId, title: head.title, meta: head.meta, cells } : NO_PLANE,
		[planeId, head, cells],
	);
}
