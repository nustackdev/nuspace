// One row of the rail: a Plane, on the row shell in ./RailRow.tsx.
//
// Every affordance is a kit primitive. The label is a `NavLink` (a real
// anchor, so cmd-click opens a Plane in a tab and `aria-current="page"` marks
// the open one for a screen reader); the twisty and the actions are
// `IconButton`s beside it rather than inside it, because a button inside an
// anchor is not a thing; per-Plane actions live in a kit `DropdownMenu` off the
// `...` and in a kit `ContextMenu` off a right-click on the row.
//
// The lane is Notion's: every row shows its plane's icon at rest, and while
// the row is hovered or keyboard focused the icon swaps, in place, for the
// fold chevron. Leaves too: unfolding a leaf shows "No planes inside". The
// swap is pure CSS (`railIcon` / `railTwisty` in design/rail.ts). The chevron
// only folds: it never opens the plane and never starts a drag.
//
// The icon is the plane's own (`meta.icon`), else its registered Plane's, else
// the default. It is not a control, since the chevron takes its place under
// the pointer: "Change icon" in both menus opens the picker, anchored on it.
// "Pin" / "Unpin" in both menus puts it in the pinned row or takes it out.
//
// The hover split opens the plane in a new pane beside the others, the same as
// the menus' "Open in split" and a drag of the row onto the panes. "Open in new
// tab" in both menus is the browser's tab, the same as a cmd-click. The hover `+` adds a Plane under this one,
// through the one Add plane popup. All three actions carry a kit tooltip; the
// title carries one only when it is cut off (see ../shell/OverflowTooltip.tsx).

import {
	ContextMenuItem,
	ContextMenuSeparator,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Popover,
	PopoverAnchor,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import {
	ChevronRight,
	Columns2,
	Ellipsis,
	ExternalLink,
	FileText,
	PenLine,
	Pin,
	PinOff,
	Plus,
	SmilePlus,
	Trash2,
} from "lucide-react";
import type * as React from "react";
import { useCallback, useRef, useState } from "react";
import { hrefFor, onNavClick, openInNewTab, openPane, replacePane } from "../core/router";
import { railAction, railChevron, railIcon, railTwisty } from "../design";
import { IconPickerContent } from "../icon/IconPicker";
import { PlaneIcon } from "../icon/PlaneIcon";
import type { Icon as PlaneIconValue } from "../icon/parse";
import { openAddPlane } from "./add";
import type { Notify } from "./ops";
import type { Pins } from "./pin";
import { RailRow, RailRowLink } from "./RailRow";
import { RailRowInput } from "./RailRowInput";
import { canDelete, deletePlane } from "./remove";
import type { VisibleRow } from "./tree";
import type { PlaneTree } from "./types";

export function PlaneRow({
	row,
	index,
	icon,
	selected,
	open: isOpen,
	tabbable,
	renaming,
	drag,
	dragging,
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
	pins,
}: {
	row: VisibleRow;
	index: number;
	/** The row's icon, resolved: its own, its registered Plane's, or the default. */
	icon: PlaneIconValue;
	/** The focused pane's Plane. */
	selected: boolean;
	/** Showing in some pane. */
	open: boolean;
	tabbable: boolean;
	renaming: boolean;
	drag: React.ComponentProps<typeof RailRow>["drag"];
	/** Some row is being dragged, so no row takes its hover look. */
	dragging: boolean;
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
	pins: Pins;
}) {
	const { key, id, depth, title, hasKids, open, pos, size } = row;
	const navClick = onNavClick(id);

	const remove = useCallback(() => deletePlane(notify, tree, id, title), [id, notify, title, tree]);
	const removable = canDelete(tree, id);

	const split = useCallback(() => {
		if (hasKids) reveal(key);
		openPane(id);
	}, [hasKids, id, key, reveal]);

	const newTab = useCallback(() => openInNewTab(id), [id]);

	const add = useCallback(() => openAddPlane({ parent: id }), [id]);

	const pinned = pins.ids.includes(id);
	const togglePin = useCallback(() => (pinned ? pins.unpin(id) : pins.pin(id)), [id, pinned, pins]);
	const PinIcon = pinned ? PinOff : Pin;
	const pinLabel = pinned ? "Unpin" : "Pin";

	// "Change icon" opens the picker once its menu has closed, in place of the
	// menu handing focus back; opened any sooner, that focus would shut it.
	const [picking, setPicking] = useState(false);
	const pickNext = useRef(false);
	const changeIcon = useCallback(() => {
		pickNext.current = true;
	}, []);
	const afterMenu = useCallback((e: Event) => {
		if (!pickNext.current) return;
		pickNext.current = false;
		e.preventDefault();
		setPicking(true);
	}, []);
	const setIcon = useCallback(
		(next: string) => {
			setPicking(false);
			notify("plane.icon", { plane_id: id, icon: next });
		},
		[id, notify],
	);

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
			expanded={open}
			drag={renaming ? undefined : drag}
			className={className}
			onFocus={() => onFocus(key)}
			onKeyDown={(e) => onKeyDown(e, row, index)}
			onMenuCloseAutoFocus={afterMenu}
			lane={
				<>
					<Popover open={picking} onOpenChange={setPicking}>
						<PopoverAnchor asChild>
							<PlaneIcon icon={icon} className={railIcon(!dragging)} />
						</PopoverAnchor>
						<IconPickerContent
							value={row.icon}
							onPick={setIcon}
							onRemove={() => setIcon("")}
							side="bottom"
							align="start"
							// Back to the row, so the keyboard carries on from where it was.
							onCloseAutoFocus={(e) => {
								e.preventDefault();
								document
									.querySelector<HTMLElement>(
										`[role="treeitem"][data-rail-key="${CSS.escape(key)}"]`,
									)
									?.focus();
							}}
						/>
					</Popover>
					<IconButton
						variant="ghost"
						size="sm"
						tabIndex={tabbable ? 0 : -1}
						aria-label={open ? "Collapse" : "Expand"}
						aria-expanded={open}
						// No focus on a click (so nothing lingers once the pointer
						// leaves) and no drag of the row from here.
						onMouseDown={(e) => e.preventDefault()}
						onClick={(e) => {
							e.stopPropagation();
							onToggle(key);
						}}
						// Enter and Space press the button. Kept from the row, whose
						// Enter opens the plane and would cancel the press.
						onKeyDown={(e) => {
							if (e.key === "Enter" || e.key === " ") e.stopPropagation();
						}}
						className={railTwisty(!dragging)}
					>
						<ChevronRight className={railChevron(open)} />
					</IconButton>
				</>
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
						dragging={dragging}
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
					<Tooltip>
						<TooltipTrigger asChild>
							<IconButton
								variant="ghost"
								size="sm"
								tabIndex={-1}
								aria-label={`Open ${title} in split`}
								onClick={split}
								className={railAction}
							>
								<Columns2 />
							</IconButton>
						</TooltipTrigger>
						<TooltipContent side="bottom">Open in split</TooltipContent>
					</Tooltip>
					<Tooltip>
						<TooltipTrigger asChild>
							<IconButton
								variant="ghost"
								size="sm"
								tabIndex={-1}
								aria-label={`Add plane in ${title}`}
								onClick={add}
								className={railAction}
							>
								<Plus />
							</IconButton>
						</TooltipTrigger>
						<TooltipContent side="bottom">Add plane inside</TooltipContent>
					</Tooltip>
					<MoreMenu
						title={title}
						tabbable={tabbable}
						dragging={dragging}
						onCloseAutoFocus={afterMenu}
					>
						<DropdownMenuItem onSelect={split}>
							<Columns2 />
							Open in split
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={newTab}>
							<ExternalLink />
							Open in new tab
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={add}>
							<Plus />
							Add plane
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={() => onRename(row)}>
							<PenLine />
							Rename
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={changeIcon}>
							<SmilePlus />
							Change icon
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={togglePin}>
							<PinIcon />
							{pinLabel}
						</DropdownMenuItem>
						{removable ? (
							<>
								<DropdownMenuSeparator />
								<DropdownMenuItem variant="danger" onSelect={remove}>
									<Trash2 />
									Delete
								</DropdownMenuItem>
							</>
						) : null}
					</MoreMenu>
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
					<ContextMenuItem onSelect={newTab}>
						<ExternalLink />
						Open in new tab
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
					<ContextMenuItem onSelect={changeIcon}>
						<SmilePlus />
						Change icon
					</ContextMenuItem>
					<ContextMenuItem onSelect={togglePin}>
						<PinIcon />
						{pinLabel}
					</ContextMenuItem>
					{removable ? (
						<>
							<ContextMenuSeparator />
							<ContextMenuItem variant="danger" onSelect={remove}>
								<Trash2 />
								Delete
							</ContextMenuItem>
						</>
					) : null}
				</>
			}
		/>
	);
}

/**
 * The `...` and its dropdown. Its "More" tooltip never shows over the open
 * menu, nor on the focus the menu hands back to it when it closes: that one
 * waits until the pointer comes back or focus moves on.
 */
function MoreMenu({
	title,
	tabbable,
	dragging,
	onCloseAutoFocus,
	children,
}: {
	title: string;
	tabbable: boolean;
	dragging: boolean;
	/** Where focus goes when the menu closes; the default is back to the `...`. */
	onCloseAutoFocus?: (e: Event) => void;
	/** The dropdown's items. */
	children: React.ReactNode;
}) {
	const [menu, setMenu] = useState(false);
	const [tip, setTip] = useState(false);
	const handedBack = useRef(false);

	const onMenu = useCallback((next: boolean) => {
		setMenu(next);
		setTip(false);
		if (!next) handedBack.current = true;
	}, []);

	const onTip = useCallback(
		(next: boolean) => setTip(next && !menu && !dragging && !handedBack.current),
		[menu, dragging],
	);

	return (
		<DropdownMenu open={menu} onOpenChange={onMenu}>
			<Tooltip open={tip && !menu && !dragging} onOpenChange={onTip}>
				{/* The menu's trigger outside the tooltip's, so the row's action
				    lane still sees the menu's data-state and stays up while it is
				    open. */}
				<DropdownMenuTrigger asChild>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							tabIndex={tabbable ? 0 : -1}
							aria-label={`Actions for ${title}`}
							onPointerEnter={() => {
								handedBack.current = false;
							}}
							onBlur={() => {
								handedBack.current = false;
							}}
							className={railAction}
						>
							<Ellipsis />
						</IconButton>
					</TooltipTrigger>
				</DropdownMenuTrigger>
				<TooltipContent side="bottom">More</TooltipContent>
			</Tooltip>
			<DropdownMenuContent align="start" className="min-w-40" onCloseAutoFocus={onCloseAutoFocus}>
				{children}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
