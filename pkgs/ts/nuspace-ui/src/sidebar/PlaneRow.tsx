// One row of the rail: a Plane, on the row shell in ./RailRow.tsx.
//
// Every affordance is a kit primitive. The label is a `NavLink` (a real
// anchor, so cmd-click opens a Plane in a tab and `aria-current="page"` marks
// the open one for a screen reader); the twisty and the actions are
// `IconButton`s beside it rather than inside it, because a button inside an
// anchor is not a thing; per-Plane actions live in a kit `DropdownMenu` off the
// `...` and in a kit `ContextMenu` off a right-click on the row.
//
// The hover `+` adds a Plane under this one, through the one Add plane popup.

import {
	ContextMenuItem,
	ContextMenuSeparator,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
} from "@nustackdev/ui-kit";
import type { LucideIcon } from "lucide-react";
import { ChevronRight, Columns2, Ellipsis, FileText, PenLine, Plus, Trash2 } from "lucide-react";
import type * as React from "react";
import { useCallback } from "react";
import { closePanes, hrefFor, onNavClick, openPane, replacePane } from "../core/router";
import { railAction, railLeafIcon, railTwisty } from "../design";
import { openAddPlane } from "./add";
import type { Notify } from "./ops";
import { RailRow, RailRowLink } from "./RailRow";
import { RailRowInput } from "./RailRowInput";
import { folds, subtreeOf, type VisibleRow } from "./tree";
import type { PlaneTree } from "./types";

export function PlaneRow({
	row,
	index,
	icon: Icon,
	selected,
	open: isOpen,
	tabbable,
	renaming,
	drag,
	className,
	onToggle,
	reveal,
	onFocus,
	onKeyDown,
	onRename,
	onCommit,
	onCancel,
	notify,
	tree,
}: {
	row: VisibleRow;
	index: number;
	/** The leaf icon: the one its registered Plane names. */
	icon: LucideIcon;
	/** The focused pane's Plane. */
	selected: boolean;
	/** Showing in some pane. */
	open: boolean;
	tabbable: boolean;
	renaming: boolean;
	drag: React.ComponentProps<typeof RailRow>["drag"];
	className?: string;
	onToggle: (key: string) => void;
	reveal: (key: string) => void;
	onFocus: (key: string) => void;
	onKeyDown: (e: React.KeyboardEvent, row: VisibleRow, index: number) => void;
	onRename: (row: VisibleRow) => void;
	onCommit: (title: string) => void;
	onCancel: () => void;
	notify: Notify;
	tree: PlaneTree;
}) {
	const { key, id, depth, title, hasKids, open, pos, size } = row;
	const foldable = folds(row);
	const navClick = onNavClick(id);

	const remove = useCallback(() => {
		if (!window.confirm(`Delete "${title}" and everything under it?`)) return;
		notify("plane.delete", { plane_id: id });
		// Its panes go too, and so do its children's. Replace, not push: the
		// back button should not bring back a Plane that no longer exists.
		closePanes(subtreeOf(tree, id), true);
	}, [id, notify, title, tree]);

	const split = useCallback(() => {
		if (hasKids) reveal(key);
		openPane(id);
	}, [hasKids, id, key, reveal]);

	const add = useCallback(() => openAddPlane({ parent: id }), [id]);

	return (
		<RailRow
			rowKey={key}
			selected={selected}
			open={isOpen && !selected}
			tabbable={tabbable}
			indent={depth}
			level={depth + 1}
			posinset={pos}
			setsize={size}
			expanded={foldable ? open : undefined}
			drag={renaming ? undefined : drag}
			className={className}
			onFocus={() => onFocus(key)}
			onKeyDown={(e) => onKeyDown(e, row, index)}
			lane={
				foldable ? (
					<IconButton
						variant="ghost"
						size="sm"
						tabIndex={-1}
						aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
						aria-expanded={open}
						onClick={() => onToggle(key)}
						className={railTwisty}
					>
						<ChevronRight
							className={`transition-transform duration-fast ease-out ${open ? "rotate-90" : ""}`}
						/>
					</IconButton>
				) : (
					<Icon className={railLeafIcon} aria-hidden="true" />
				)
			}
			label={
				renaming ? (
					<RailRowInput
						initial={title}
						label={`Rename ${title}`}
						onCommit={onCommit}
						onCancel={onCancel}
					/>
				) : (
					<RailRowLink
						href={hrefFor(id)}
						label={title}
						selected={selected}
						onClick={(e) => {
							// Opening a Plane reveals what is inside it. It never folds
							// it: a click that toggles is a click you cannot predict.
							if (hasKids) reveal(key);
							navClick(e);
						}}
						onDoubleClick={() => onRename(row)}
					/>
				)
			}
			actions={
				<>
					<IconButton
						variant="ghost"
						size="sm"
						tabIndex={-1}
						aria-label={`Add plane in ${title}`}
						title="Add plane"
						onClick={add}
						className={railAction}
					>
						<Plus />
					</IconButton>
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<IconButton
								variant="ghost"
								size="sm"
								tabIndex={tabbable ? 0 : -1}
								aria-label={`Actions for ${title}`}
								className={railAction}
							>
								<Ellipsis />
							</IconButton>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="start" className="min-w-40">
							<DropdownMenuItem onSelect={split}>
								<Columns2 />
								Open in split
							</DropdownMenuItem>
							<DropdownMenuItem onSelect={add}>
								<Plus />
								Add plane
							</DropdownMenuItem>
							<DropdownMenuItem onSelect={() => onRename(row)}>
								<PenLine />
								Rename
							</DropdownMenuItem>
							<DropdownMenuSeparator />
							<DropdownMenuItem variant="danger" onSelect={remove}>
								<Trash2 />
								Delete
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				</>
			}
			menu={
				<>
					<ContextMenuItem onSelect={() => replacePane(id)}>
						<FileText />
						Open
					</ContextMenuItem>
					<ContextMenuItem onSelect={split}>
						<Columns2 />
						Open in split
					</ContextMenuItem>
					<ContextMenuSeparator />
					<ContextMenuItem onSelect={add}>
						<Plus />
						Add plane
					</ContextMenuItem>
					<ContextMenuItem onSelect={() => onRename(row)}>
						<PenLine />
						Rename
					</ContextMenuItem>
					<ContextMenuSeparator />
					<ContextMenuItem variant="danger" onSelect={remove}>
						<Trash2 />
						Delete
					</ContextMenuItem>
				</>
			}
		/>
	);
}
