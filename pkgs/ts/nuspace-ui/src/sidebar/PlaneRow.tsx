// One row of the rail: a section or a Plane, on the row shell in ./RailRow.tsx.
//
// Every affordance is a kit primitive. A Plane row's label is a `NavLink` (a
// real anchor, so cmd-click opens a Plane in a tab and `aria-current="page"`
// marks the open one for a screen reader); the twisty and the actions are
// `IconButton`s beside it rather than inside it, because a button inside an
// anchor is not a thing; per-Plane actions live in a kit `DropdownMenu` off the
// `...` and in a kit `ContextMenu` off a right-click on the row.

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
import { ChevronRight, Columns2, Ellipsis, FileText, PenLine, Plus, Trash2 } from "lucide-react";
import type * as React from "react";
import { useCallback } from "react";
import { closePanes, hrefFor, onNavClick, openPane, replacePane } from "../app/router";
import { railAction, railLeafIcon, railTwisty } from "../design";
import type { Notify } from "./ops";
import { RailRow, RailRowLink, RailSectionLabel } from "./RailRow";
import { RailRowInput } from "./RailRowInput";
import { folds, subtreeOf, type VisibleRow } from "./tree";
import { KIND_GROUP, type PageTree } from "./types";

export function PlaneRow({
	row,
	index,
	selected,
	open: isOpen,
	tabbable,
	renaming,
	onToggle,
	reveal,
	onFocus,
	onKeyDown,
	onRename,
	onCreate,
	onCommit,
	onCancel,
	notify,
	tree,
}: {
	row: VisibleRow;
	index: number;
	/** The focused pane's Plane. */
	selected: boolean;
	/** Showing in some pane. */
	open: boolean;
	tabbable: boolean;
	renaming: boolean;
	onToggle: (key: string) => void;
	reveal: (key: string) => void;
	onFocus: (key: string) => void;
	onKeyDown: (e: React.KeyboardEvent, row: VisibleRow, index: number) => void;
	onRename: (row: VisibleRow) => void;
	onCreate: (row: VisibleRow) => void;
	onCommit: (title: string) => void;
	onCancel: () => void;
	notify: Notify;
	tree: PageTree;
}) {
	const { key, id, kind, depth, title, hasKids, open, pos, size } = row;
	const section = kind === KIND_GROUP;
	const foldable = folds(row);
	const navClick = onNavClick(id);

	const remove = useCallback(() => {
		if (!window.confirm(`Delete "${title}" and everything under it?`)) return;
		notify("page.delete", { page_id: id });
		// Its panes go too, and so do its children's. Replace, not push: the
		// back button should not bring back a Plane that no longer exists.
		closePanes(subtreeOf(tree, id), true);
	}, [id, notify, title, tree]);

	const split = useCallback(() => {
		if (hasKids) reveal(key);
		openPane(id);
	}, [hasKids, id, key, reveal]);

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
					<FileText className={railLeafIcon} aria-hidden="true" />
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
				) : section ? (
					<RailSectionLabel label={title} />
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
				section ? (
					<IconButton
						variant="ghost"
						size="sm"
						tabIndex={tabbable ? 0 : -1}
						aria-label={`New in ${title}`}
						onClick={() => onCreate(row)}
						className={railAction}
					>
						<Plus />
					</IconButton>
				) : (
					<>
						<IconButton
							variant="ghost"
							size="sm"
							tabIndex={-1}
							aria-label={`Open ${title} in split`}
							title="Open in split"
							onClick={split}
							className={railAction}
						>
							<Columns2 />
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
				)
			}
			menu={
				section ? (
					<ContextMenuItem onSelect={() => onCreate(row)}>
						<Plus />
						New in {title}
					</ContextMenuItem>
				) : (
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
				)
			}
		/>
	);
}
