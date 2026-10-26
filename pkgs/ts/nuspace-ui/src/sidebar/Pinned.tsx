// The pinned planes, the first section of the rail's body after the nav
// rows: one flat row per pinned Plane, in order. A pin is a shortcut: the
// Plane is in the tree as well. Hidden when nothing is pinned, its header
// with it.
//
// A row opens its Plane the way a tree row does: a plain click in the focused
// pane, Option-click beside the others, cmd/ctrl-click in a browser tab. Its
// hover controls and menus are a tree row's (./PlaneRow.tsx), less rename
// and change icon, which happen on the tree row. The home, search and
// settings planes are never pinned: they have their nav rows (./nav.ts).
//
// Drag and drop is native, like the tree's (./useRailDrag.ts):
//
//   a tree row dropped here      pinned where it lands, and left in the tree
//   a pin dropped here           moved where it lands
//   a pin dropped on the panes   opened there as a split (../main/useCanvasDrop.ts)
//   a pin dropped anywhere else  nothing: the tree only takes its own rows
//
// Where a drop lands is read off the pointer against the row under it: its
// top half is before it, its bottom half after it.

import type * as React from "react";
import { useCallback, useMemo, useState } from "react";
import { hrefFor, openBeside, openHere, openInNewTab } from "../core/router";
import {
	railDragging,
	railDropLine,
	railDropLineStyle,
	railIcon,
	railRowWrap,
	railTreeList,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { contextParts } from "../shell/menu";
import { openAddPlane } from "./add";
import { NAV_PLANES } from "./nav";
import type { Notify } from "./ops";
import { PlaneMenuItems, type PlaneMenuProps, PlaneRowActions } from "./PlaneRow";
import { type Pins, pinDropIndex } from "./pin";
import { RailRow, RailRowLink } from "./RailRow";
import { RailSection } from "./RailSection";
import { canDelete, deletePlane } from "./remove";
import type { PlaneTree } from "./types";
import { PLANE_MIME } from "./useRailDrag";
import { pinKey, useRailNav } from "./useRailFocus";

/** What a pin's drag carries, apart from a tree row's so the tree ignores it. */
export const PIN_MIME = "application/x-nuspace-pin";

/** Where a drop would land: beside the pin at `index`. */
type PinTarget = { index: number; edge: "before" | "after" };

/** The gap a target names, 0 before the first pin. */
export function pinSlot(target: PinTarget): number {
	return target.edge === "before" ? target.index : target.index + 1;
}

/** The pins the rail draws: in the tree, and not a nav plane. */
export function shownPins(tree: PlaneTree, ids: string[]): string[] {
	return ids.filter((id) => tree[id] && !NAV_PLANES.has(id));
}

export function Pinned(props: {
	tree: PlaneTree;
	pins: Pins;
	routes: string[];
	/** The focused pane's Plane. */
	selKey: string;
	reveal: (key: string) => void;
	notify: Notify;
}) {
	const shown = useMemo(() => shownPins(props.tree, props.pins.ids), [props.tree, props.pins.ids]);
	return shown.length ? (
		<>
			<RailSection label="Pinned" />
			<PinList {...props} shown={shown} />
		</>
	) : null;
}

function PinList({
	tree,
	pins,
	routes,
	selKey,
	reveal,
	notify,
	shown,
}: {
	tree: PlaneTree;
	pins: Pins;
	routes: string[];
	selKey: string;
	reveal: (key: string) => void;
	notify: Notify;
	/** The pins the tree holds, in order. */
	shown: string[];
}) {
	const { tabKey, setActiveKey, arrows } = useRailNav();
	const [dragId, setDragId] = useState<string | null>(null);
	const [target, setTarget] = useState<PinTarget | null>(null);

	const end = useCallback(() => {
		setDragId(null);
		setTarget(null);
	}, []);

	/** Whether this drag is one the list takes: a pin, or a tree row. */
	const takes = (e: React.DragEvent) =>
		dragId !== null || Array.from(e.dataTransfer.types).includes(PLANE_MIME);

	const drop = (e: React.DragEvent, to: PinTarget) => {
		e.preventDefault();
		e.stopPropagation();
		const moving = dragId;
		const id = moving ?? e.dataTransfer.getData(PLANE_MIME);
		end();
		if (!id || !tree[id] || NAV_PLANES.has(id)) return;
		const index = pinDropIndex(shown, id, pinSlot(to));
		if (index === null) return;
		if (moving) pins.move(id, index);
		else pins.pin(id, index);
	};

	const aim = (e: React.DragEvent, index: number): PinTarget => {
		const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
		return { index, edge: e.clientY < r.top + r.height / 2 ? "before" : "after" };
	};

	return (
		<div
			role="tree"
			aria-label="Pinned"
			className={railTreeList}
			onDragLeave={(e) => {
				if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setTarget(null);
			}}
		>
			{shown.map((id, index) => {
				const row = tree[id];
				const title = row.title || "Untitled";
				const selected = id === selKey;
				const aimed = target?.index === index ? target.edge : null;
				const open = () => {
					if (row.children.length) reveal(id);
					openHere(id);
				};
				const menu: PlaneMenuProps = {
					open,
					openOnDesk: () => {
						if (row.children.length) reveal(id);
						openBeside(id);
					},
					newTab: () => openInNewTab(id),
					add: () => openAddPlane({ parent: id }),
					pinned: true,
					togglePin: () => pins.unpin(id),
					remove: canDelete(tree, id) ? () => void deletePlane(notify, tree, id, title) : null,
				};
				return (
					<div key={id} role="none" className={railRowWrap}>
						<RailRow
							rowKey={pinKey(id)}
							planeId={id}
							selected={selected}
							open={!selected && routes.includes(id)}
							tabbable={pinKey(id) === tabKey}
							level={1}
							posinset={index + 1}
							setsize={shown.length}
							className={dragId === id ? railDragging : undefined}
							onFocus={() => setActiveKey(pinKey(id))}
							onKeyDown={(e) => {
								if (arrows(e, pinKey(id))) return;
								if (e.key === "Enter" || e.key === " ") {
									e.preventDefault();
									if (e.altKey && e.key === "Enter") openBeside(id);
									else open();
								}
							}}
							drag={{
								draggable: true,
								onDragStart: (e) => {
									e.dataTransfer.effectAllowed = "move";
									e.dataTransfer.setData(PIN_MIME, id);
									setDragId(id);
								},
								onDragEnd: end,
								onDragOver: (e) => {
									if (!takes(e)) return;
									e.preventDefault();
									e.stopPropagation();
									e.dataTransfer.dropEffect = "move";
									const next = aim(e, index);
									if (target?.index !== next.index || target.edge !== next.edge) setTarget(next);
								},
								onDrop: (e) => {
									if (takes(e)) drop(e, aim(e, index));
								},
							}}
							lane={<PlaneIcon icon={planeIcon(row.icon)} className={railIcon(false)} />}
							label={
								<RailRowLink
									href={hrefFor(id)}
									label={title}
									selected={selected}
									// The tree row's click, through the shell's anchor catcher.
									// Here it only reveals what is inside it.
									onClick={() => {
										if (row.children.length) reveal(id);
									}}
								/>
							}
							actions={
								<PlaneRowActions
									title={title}
									tabbable={pinKey(id) === tabKey}
									dragging={dragId !== null}
									menu={menu}
								/>
							}
							menu={<PlaneMenuItems parts={contextParts} {...menu} />}
						/>
						{aimed ? (
							<span
								className={railDropLine(aimed)}
								style={railDropLineStyle(0)}
								aria-hidden="true"
							/>
						) : null}
					</div>
				);
			})}
		</div>
	);
}
