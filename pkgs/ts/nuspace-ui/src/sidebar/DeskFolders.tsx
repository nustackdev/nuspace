// The desk folders: one section per desk (./DeskFolder.tsx), above the
// Planes tree, in the desks feed's order (creation order, Favorites first,
// then as dragged). A new desk comes from the header's `+` menu, a plane's
// menu or the nav section's New desk row, a click or a drop (./newDesk.ts).
//
// This is the list: the folders and the state they share while a drag is on.
//
//   drops    one aim at a time across every folder (`Aimed`), and the drop
//            itself through `dropOn` (../desk/dnd.ts), offered only where the
//            drag table writes something (`canDrop`). The aim says what the
//            drop does (`dropDoes`), or why the table refuses it (`whyNot`),
//            ringed on its row and not offered
//   lifted   the row being dragged, dimmed while it travels
//   reorder  a desk dragged by its title, and where it would land
//   rename   which folder's title is a rename field
//
// The looks of every plane the folders link to are resolved once, here
// (../core/looks.ts).

import type * as React from "react";
import { useEffect, useMemo, useState } from "react";
import { moveDesk, useDeskOrder, useDesks } from "../core/desks";
import { usePlaneLooks } from "../core/looks";
import { canDrop, dragging, dragKind, dropOn, endDrag, readDrag, whyNot } from "../desk/dnd";
import { setDragChip } from "../desk/drag";
import type { Desk, Links } from "../desk/model";
import { type Aimed, type AimHit, DeskFolder } from "./DeskFolder";
import type { DragProps, DropProps } from "./DeskRows";
import { doesHint, refusedHint, useSettle } from "./drag";
import { type FolderRow, folderKey, folderRows, useFolds } from "./folders";
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

const sameAim = (a: Aimed, b: Aimed) => JSON.stringify(a) === JSON.stringify(b);

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
	// A desk dragged by its title, and where it would land: over a folder's
	// title, above or under it.
	const [movingDesk, setMovingDesk] = useState<string | null>(null);
	const [deskAim, setDeskAim] = useState<{ desk: string; edge: "before" | "after" } | null>(null);

	// How long the pointer has rested on a row, across every folder.
	const settle = useSettle();

	// A drag that ends anywhere (Esc, a drop elsewhere, a drag from the tree)
	// clears the aim, as the canvas's does.
	const { reset } = settle;
	useEffect(() => {
		const clear = () => {
			setAim(null);
			reset();
		};
		document.addEventListener("dragend", clear);
		document.addEventListener("drop", clear);
		return () => {
			document.removeEventListener("dragend", clear);
			document.removeEventListener("drop", clear);
		};
	}, [reset]);

	const onAim = (next: Aimed) => {
		if (!sameAim(aim, next)) setAim(next);
	};

	/**
	 * Drag handlers for a drop site whose aim is `aimAt`'s: null where nothing
	 * lands, `{ keep }` over no row of desk `keep`, where its aim holds.
	 */
	const dropHandlers = (aimAt: (e: React.DragEvent<HTMLElement>) => AimHit): DropProps => {
		const judge = (e: React.DragEvent<HTMLElement>): Aimed | "keep" => {
			const hit = aimAt(e);
			if (!hit) return null;
			if ("keep" in hit) return aim?.desk === hit.keep ? "keep" : null;
			const payload = dragging();
			const { target, mark } = hit.aim;
			if (canDrop(payload, target)) {
				return {
					desk: hit.desk,
					key: hit.key,
					mark,
					target,
					ok: true,
					hint: doesHint(payload, target),
				};
			}
			const why = whyNot(payload, target);
			return why
				? {
						desk: hit.desk,
						key: hit.key,
						mark: { ring: true },
						target,
						ok: false,
						hint: refusedHint(why),
					}
				: null;
		};
		return {
			onDragOver: (e) => {
				if (!dragKind(e.dataTransfer)) return;
				const next = judge(e);
				if (next !== "keep") onAim(next);
				const now = next === "keep" ? aim : next;
				if (!now?.ok) return;
				e.preventDefault();
				e.stopPropagation();
				e.dataTransfer.dropEffect = "move";
			},
			onDragLeave: (e) => {
				// Within its folder (the title to the rows and back) the aim
				// holds, so a line on the gap between them stays; the next
				// dragover sets it. Leaving the folders clears it (below).
				const to = e.relatedTarget as Node | null;
				if (e.currentTarget.closest("section")?.contains(to)) return;
				setAim(null);
				settle.reset();
			},
			onDrop: (e) => {
				const payload = readDrag(e.dataTransfer);
				const next = payload ? judge(e) : null;
				const now = next === "keep" ? aim : next;
				setAim(null);
				settle.reset();
				if (!payload || !now?.ok || !canDrop(payload, now.target)) return;
				e.preventDefault();
				e.stopPropagation();
				endDrag();
				setLifted(null);
				dropOn(payload, now.target);
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
			settle.reset();
		},
	});

	// Leaving every folder, for the tree or the canvas, drops the aim.
	const leave = (e: React.DragEvent<HTMLElement>) => {
		if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
		setAim(null);
		settle.reset();
	};

	return (
		// `contents`: a box for leaving the folders only.
		<div role="none" className="contents" onDragLeave={leave}>
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
					settled={settle.settled}
				/>
			))}
		</div>
	);
}
