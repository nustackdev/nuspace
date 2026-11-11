// The desk folders: one section per desk (./DeskFolder.tsx), above the
// Planes tree, in the desks feed's order (creation order, Favorites first,
// then as dragged). A new desk comes from the header's `+` menu, a plane's
// menu or a drop on the New desk zone (./newDesk.ts).
//
// This is the list: the folders and the state they share while a drag is on.
//
//   drops    one aim at a time across every folder (`Aimed`), and the drop
//            itself through `dropOn` (../desk/dnd.ts), offered only where the
//            drag table writes something (`canDrop`)
//   lifted   the row being dragged, dimmed while it travels
//   reorder  a desk dragged by its title, and where it would land
//   rename   which folder's title is a rename field
//   New desk while a plane, item or pane is dragged, a dashed zone under the
//            last folder: a drop there makes a desk of it
//
// The looks of every plane the folders link to are resolved once, here
// (../core/looks.ts).

import { cn } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useEffect, useMemo, useState } from "react";
import { moveDesk, useDeskOrder, useDesks } from "../core/desks";
import { usePlaneLooks } from "../core/looks";
import { sidebarDeskEmpty, sidebarDropInto } from "../design";
import { canDrop, dragging, dragKind, dropOn, endDrag, readDrag } from "../desk/dnd";
import { setDragChip } from "../desk/drag";
import type { Desk, Links } from "../desk/model";
import { type Aimed, DeskFolder } from "./DeskFolder";
import type { DragProps, DropProps } from "./DeskRows";
import { type Aim, type FolderRow, folderKey, folderRows, useFolds } from "./folders";
import { newDesk } from "./newDesk";
import type { PlaneTree } from "./types";

/** One desk's folder, as drawn. */
export type Folder = { id: string; desk: Desk; folded: boolean; rows: FolderRow[] };

/** The folders in order, with their rows: for the body's one tab stop and for drawing. */
export function useFolders(): Folder[] {
	const desks = useDesks();
	const order = useDeskOrder();
	const folds = useFolds();
	return useMemo(
		() =>
			order.flatMap((id) => {
				const desk = desks?.[id];
				if (!desk) return [];
				const folded = folds.has(folderKey(id));
				return [{ id, desk, folded, rows: folded ? [] : folderRows(id, desk, folds) }];
			}),
		[desks, order, folds],
	);
}

/** The row keys the folders draw, in order. */
export function folderKeys(folders: Folder[]): string[] {
	return folders.flatMap((f) => f.rows.map((r) => r.key));
}

/** Every plane the folders link to, original and recent. */
function planesOf(folders: Folder[]): string[] {
	const out = new Set<string>();
	const add = (x: Links) => {
		out.add(x.original.plane);
		if (x.recent) out.add(x.recent.plane);
	};
	for (const { desk } of folders) {
		for (const item of desk.items) {
			if (item.kind === "plane") add(item);
			else for (const col of item.columns) for (const pane of col.panes) add(pane);
		}
	}
	return [...out];
}

const sameAim = (a: Aimed, b: Aimed) =>
	a?.desk === b?.desk && a?.key === b?.key && JSON.stringify(a?.mark) === JSON.stringify(b?.mark);

export function DeskFolders({
	folders,
	tree,
	selected,
}: {
	folders: Folder[];
	tree: PlaneTree;
	/** The selected row's key (./folders.ts `selectedKey`), null for none here. */
	selected: string | null;
}) {
	const planes = useMemo(() => planesOf(folders), [folders]);
	const looks = usePlaneLooks(planes, tree);
	const [aim, setAim] = useState<Aimed>(null);
	// The row being dragged, dimmed while it travels.
	const [lifted, setLifted] = useState<string | null>(null);
	// The desk whose title is a rename field.
	const [renaming, setRenaming] = useState<string | null>(null);
	const dragOn = useDragOn();
	// The New desk zone while a drag aims at it.
	const [aimNew, setAimNew] = useState(false);
	// A desk dragged by its title, and where it would land: over a folder's
	// title, above or under it.
	const [movingDesk, setMovingDesk] = useState<string | null>(null);
	const [deskAim, setDeskAim] = useState<{ desk: string; edge: "before" | "after" } | null>(null);

	const onAim = (next: Aimed) => {
		if (!sameAim(aim, next)) setAim(next);
	};

	/** Drag handlers for a drop site whose aim is `aimAt`'s, null where nothing lands. */
	const dropHandlers = (
		aimAt: (
			e: React.DragEvent<HTMLElement>,
		) => { aim: Aim; key: string | null; desk: string } | null,
	): DropProps => {
		const take = (e: React.DragEvent<HTMLElement>) => {
			const hit = aimAt(e);
			return hit && canDrop(dragging(), hit.aim.target) ? hit : null;
		};
		return {
			onDragOver: (e) => {
				if (!dragKind(e.dataTransfer)) return;
				const hit = take(e);
				if (!hit) {
					if (aim) setAim(null);
					return;
				}
				e.preventDefault();
				e.stopPropagation();
				e.dataTransfer.dropEffect = "move";
				onAim({ desk: hit.desk, key: hit.key, mark: hit.aim.mark });
			},
			onDragLeave: (e) => {
				if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setAim(null);
			},
			onDrop: (e) => {
				const payload = readDrag(e.dataTransfer);
				const hit = payload ? take(e) : null;
				setAim(null);
				if (!payload || !hit || !canDrop(payload, hit.aim.target)) return;
				e.preventDefault();
				e.stopPropagation();
				endDrag();
				setLifted(null);
				dropOn(payload, hit.aim.target);
			},
		};
	};

	const dragOf = (key: string, write: (dt: DataTransfer) => void): DragProps => ({
		draggable: true,
		onDragStart: (e) => {
			setDragChip(e);
			write(e.dataTransfer);
			setLifted(key);
		},
		onDragEnd: () => {
			endDrag();
			setLifted(null);
			setAim(null);
		},
	});

	return (
		<>
			{folders.map((folder, i) => (
				<DeskFolder
					key={folder.id}
					folder={folder}
					reorder={{
						moving: movingDesk,
						aim: deskAim?.desk === folder.id ? deskAim.edge : null,
						onStart: () => setMovingDesk(folder.id),
						onEnd: () => {
							setMovingDesk(null);
							setDeskAim(null);
						},
						onAim: (edge) =>
							setDeskAim((was) =>
								edge === null
									? was?.desk === folder.id
										? null
										: was
									: was?.desk === folder.id && was.edge === edge
										? was
										: { desk: folder.id, edge },
							),
						onDrop: (dragged, edge) => {
							setDeskAim(null);
							setMovingDesk(null);
							const before = edge === "before" ? folder.id : (folders[i + 1]?.id ?? "");
							moveDesk(dragged, before === dragged ? (folders[i + 2]?.id ?? "") : before);
						},
					}}
					looks={looks}
					selected={selected}
					aim={aim?.desk === folder.id ? aim : null}
					lifted={lifted}
					renaming={renaming === folder.id}
					onRename={(on) => setRenaming(on ? folder.id : null)}
					dropHandlers={dropHandlers}
					dragOf={dragOf}
				/>
			))}
			{dragOn ? (
				// biome-ignore lint/a11y/noStaticElementInteractions: a drop zone, for a pointer drag only
				<div
					data-new-desk=""
					className={cn(sidebarDeskEmpty, aimNew && sidebarDropInto)}
					onDragOver={(e) => {
						if (!dragKind(e.dataTransfer)) return;
						e.preventDefault();
						e.dataTransfer.dropEffect = "move";
						setAim(null);
						setAimNew(true);
					}}
					onDragLeave={() => setAimNew(false)}
					onDrop={(e) => {
						const payload = readDrag(e.dataTransfer);
						setAimNew(false);
						if (!payload) return;
						e.preventDefault();
						e.stopPropagation();
						endDrag();
						setLifted(null);
						newDesk(payload);
					}}
				>
					New desk
				</div>
			) : null}
		</>
	);
}

/**
 * Whether a desk or plane drag is on: the New desk zone shows only then.
 * Heard on the window, so a drag from the tree, a folder or a pane header
 * all count; over at its end or its drop, wherever that lands.
 *
 * Both flips wait a task. The zone must still be there when the drop reaches
 * it: hidden at once from a capturing listener, React drops it first and the
 * drop lands on nothing. And a page that changes under a drag as it starts
 * can make Chrome end that drag at once.
 */
function useDragOn(): boolean {
	const [on, setOn] = useState(false);
	useEffect(() => {
		const start = (e: DragEvent) => {
			if (dragKind(e.dataTransfer)) setTimeout(() => setOn(true));
		};
		const stop = () => setTimeout(() => setOn(false));
		window.addEventListener("dragstart", start);
		window.addEventListener("dragend", stop, true);
		window.addEventListener("drop", stop, true);
		return () => {
			window.removeEventListener("dragstart", start);
			window.removeEventListener("dragend", stop, true);
			window.removeEventListener("drop", stop, true);
		};
	}, []);
	return on;
}
