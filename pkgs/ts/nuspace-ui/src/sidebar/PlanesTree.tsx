// The Planes tree: every plane that draws, by parent, in sibling order, each
// a `SidebarRow` at its depth. The role planes are the nav section's, so the
// tree leaves them out (./nav.ts) and draws their children in their place.
//
// ## The interaction model
//
// Two affordances, two jobs, no overlap:
//
//   * **the row navigates and reveals.** It is a link (./links.ts: plain
//     opens the plane solo, Cmd to a browser tab). A click never edits a
//     desk. Opening a plane that has children shows them. It never hides
//     them: a click that sometimes opens and sometimes closes is a click you
//     cannot predict.
//   * **the chevron only folds.** It toggles both ways and never navigates.
//     It shows in the icon's place while the row is hovered (the swap is CSS,
//     design/sidebar.ts). Every plane folds, leaf or not; an open leaf shows
//     "No planes inside".
//
// The lazy tree: opening a branch tells the server (`plane.expand`), which
// ships its children; closing one tells it too (./Sidebar.tsx).
//
// A row's trailing hover actions are `+` (add a plane inside) and its `...`,
// the plane's menu (every pane menu shares it, ../menu/PlaneMenuItems.tsx),
// also on a right-click. Rename is in place (double click, or the menu).
// "Change icon" opens the picker, anchored on the row's icon. The selected
// row is the solo plane's; on a desk item no tree row is selected.
// Drag and drop is ./drag.ts; this draws its marks (./DropMarks.tsx): the
// line on a gap between rows, the ring on a row. A row also drags onto a desk folder
// or the canvas, as a plane.
//
// The rows are flat siblings, never nested in each other's DOM, so a row's
// `group/row` hover is its own.

import {
	cn,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuTrigger,
	EmptyState,
	IconButton,
	Popover,
	PopoverAnchor,
	Shortcut,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { ChevronRight, Ellipsis, Plus } from "lucide-react";
import type * as React from "react";
import { useCallback, useRef, useState } from "react";
import { hrefFor, openPlane } from "../core/router";
import {
	planeMenu,
	sidebarChevron,
	sidebarDragging,
	sidebarDropInto,
	sidebarDropQuiet,
	sidebarDropRefused,
	sidebarDropTail,
	sidebarDropZone,
	sidebarIcon,
	sidebarIndent,
	sidebarNoPlanes,
	sidebarRowAction,
	sidebarRowWrap,
	sidebarTooltipHint,
	sidebarTwisty,
} from "../design";
import { IconPickerContent } from "../icon/IconPicker";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { PlaneMenuItems } from "../menu/PlaneMenuItems";
import { contextParts, dropdownParts } from "../menu/parts";
import { NEW_INSIDE_KEYS, openAddPlane } from "./add";
import { DropHint, DropLine } from "./DropMarks";
import { DROP_ROW, DROP_TAIL, useTreeDrag } from "./drag";
import { useSidebarNav } from "./focus";
import type { Notify } from "./ops";
import { canDelete, deletePlane } from "./remove";
import { RowAction, SidebarRow } from "./SidebarRow";
import { showsNoPlanes, type VisibleRow } from "./tree";
import type { PlaneTree } from "./types";
import { useDraft } from "./useDraft";

export function PlanesTree({
	tree,
	rows,
	selKey,
	onToggle,
	reveal,
	notify,
}: {
	tree: PlaneTree;
	rows: VisibleRow[];
	/** The solo plane: the selected row. "" on a desk. */
	selKey: string;
	onToggle: (key: string) => void;
	reveal: (key: string) => void;
	notify: Notify;
}) {
	const { focusKey } = useSidebarNav();
	const { draft, startRename, commitDraft, cancelDraft } = useDraft({ notify, focusKey });
	const { dragKey, aim, rowProps, zoneProps } = useTreeDrag({
		tree,
		rows,
		notify,
		reveal,
	});
	const ringed = aim && "ring" in aim.mark ? aim.mark.ring : null;
	const gap = aim && "gap" in aim.mark ? aim.mark : null;

	const items: React.ReactNode[] = [];
	rows.forEach((row, index) => {
		const ring = ringed === row.key && aim ? aim : null;
		// The line on the gap above this row, or under the last.
		const line =
			gap?.gap === index
				? "before"
				: gap?.gap === rows.length && index === rows.length - 1
					? "after"
					: null;
		const near = gap !== null && (gap.gap === index || gap.gap === index + 1);
		items.push(
			<div
				key={row.key}
				role="none"
				className={cn(sidebarRowWrap, near && sidebarDropQuiet)}
				{...{ [DROP_ROW]: row.key }}
			>
				<PlaneRow
					row={row}
					next={rows[index + 1]}
					selected={row.key === selKey}
					renaming={draft?.key === row.key}
					drag={rowProps(row.key)}
					dragging={dragKey !== null}
					className={
						ring
							? ring.ok
								? sidebarDropInto
								: sidebarDropRefused
							: dragKey === row.key
								? sidebarDragging
								: undefined
					}
					onToggle={onToggle}
					reveal={reveal}
					onRename={startRename}
					onCommit={commitDraft}
					onCancel={cancelDraft}
					notify={notify}
					tree={tree}
				/>
				{ring ? <DropHint hint={ring.hint} at /> : null}
				{line && gap && aim ? <DropLine edge={line} depth={gap.depth} hint={aim.hint} /> : null}
			</div>,
		);
		if (showsNoPlanes(row)) {
			items.push(
				<EmptyState
					key={`${row.key}:none`}
					role="none"
					size="sm"
					className={sidebarNoPlanes}
					style={sidebarIndent(row.depth + 1)}
				>
					No planes inside
				</EmptyState>,
			);
		}
	});

	return (
		// The drop zone: its gaps between rows are its own (`sidebarDropZone`).
		<div role="none" className={sidebarDropZone} {...zoneProps}>
			{items}
			{/* Under the last row: a drop here goes to the top level, last. */}
			<div className={sidebarDropTail} {...{ [DROP_TAIL]: "" }} />
		</div>
	);
}

function PlaneRow({
	row,
	next,
	selected,
	renaming,
	drag,
	dragging,
	className,
	onToggle,
	reveal,
	onRename,
	onCommit,
	onCancel,
	notify,
	tree,
}: {
	row: VisibleRow;
	/** The row under it, where ArrowRight steps into an open row. */
	next: VisibleRow | undefined;
	selected: boolean;
	renaming: boolean;
	drag: React.HTMLAttributes<HTMLDivElement> & { draggable?: boolean };
	/** Some row is being dragged, so no row takes its hover look. */
	dragging: boolean;
	className?: string;
	onToggle: (key: string) => void;
	reveal: (key: string) => void;
	onRename: (row: VisibleRow) => void;
	onCommit: (title: string) => void;
	onCancel: () => void;
	notify: Notify;
	tree: PlaneTree;
}) {
	const { focusKey, tabKey } = useSidebarNav();
	const { key, id, depth, title, hasKids, open, pos, size } = row;

	const remove = useCallback(() => void deletePlane(notify, id, title), [id, notify, title]);
	const openRow = useCallback(() => {
		if (hasKids) reveal(key);
		openPlane(id);
	}, [hasKids, id, key, reveal]);

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
		(icon: string) => {
			setPicking(false);
			notify("plane.icon", { plane_id: id, icon });
		},
		[id, notify],
	);

	const menu = {
		planeId: id,
		open: openRow,
		add: () => openAddPlane({ parent: id }),
		rename: () => onRename(row),
		changeIcon,
		remove: canDelete(tree, id) ? remove : null,
	};

	return (
		<SidebarRow
			rowKey={key}
			planeId={id}
			href={hrefFor(id)}
			label={title}
			selected={selected}
			depth={depth}
			level={depth + 1}
			posinset={pos}
			setsize={size}
			expanded={open}
			drag={renaming ? undefined : drag}
			className={className}
			rename={renaming ? { label: `Rename ${title}`, onCommit, onCancel: onCancel } : null}
			// Opening a plane reveals what is inside it, never folds it.
			onClick={() => {
				if (hasKids) reveal(key);
			}}
			onDoubleClick={() => onRename(row)}
			onKeyDown={(e) => {
				if (e.target !== e.currentTarget) return;
				if (e.key === "ArrowRight") {
					// Unfold a folded row; step into an open one's first child.
					e.preventDefault();
					if (!open) onToggle(key);
					else if (hasKids && next) focusKey(next.key);
				} else if (e.key === "ArrowLeft") {
					// Fold an open row; otherwise climb to the parent.
					e.preventDefault();
					if (open) onToggle(key);
					else if (row.parent !== null) focusKey(row.parent);
				}
			}}
			onMenuCloseAutoFocus={afterMenu}
			menu={<PlaneMenuItems parts={contextParts} {...menu} />}
			icon={
				<>
					<Popover open={picking} onOpenChange={setPicking}>
						<PopoverAnchor asChild>
							<PlaneIcon icon={planeIcon(row.icon)} className={sidebarIcon(!dragging)} />
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
								focusKey(key);
							}}
						/>
					</Popover>
					<IconButton
						variant="ghost"
						size="xs"
						ring="inset"
						tabIndex={tabKey === key ? 0 : -1}
						aria-label={open ? "Collapse" : "Expand"}
						aria-expanded={open}
						// No focus on a click (so nothing lingers once the pointer
						// leaves) and no drag of the row from here.
						onMouseDown={(e) => e.preventDefault()}
						onClick={(e) => {
							e.stopPropagation();
							onToggle(key);
						}}
						// Enter and Space press the button, kept from the row,
						// whose Enter opens the plane.
						onKeyDown={(e) => {
							if (e.key === "Enter" || e.key === " ") e.stopPropagation();
						}}
						className={sidebarTwisty(!dragging)}
					>
						<ChevronRight className={sidebarChevron(open)} />
					</IconButton>
				</>
			}
			trailing={{
				action: (
					<>
						<RowAction
							label={`Add plane in ${title}`}
							tip={
								<>
									Add plane inside
									<Shortcut keys={NEW_INSIDE_KEYS} size="sm" className={sidebarTooltipHint} />
								</>
							}
							onClick={menu.add}
						>
							<Plus />
						</RowAction>
						<MoreMenu
							title={title}
							tabbable={tabKey === key}
							dragging={dragging}
							onCloseAutoFocus={afterMenu}
						>
							<PlaneMenuItems parts={dropdownParts} {...menu} />
						</MoreMenu>
					</>
				),
			}}
		/>
	);
}

/**
 * The `...` and its dropdown. Its "More" tooltip never shows over the open
 * menu, nor on the focus the menu hands back to it when it closes: that one
 * waits until the pointer comes back or focus moves on (the kit Tooltip's
 * `canOpen`).
 */
function MoreMenu({
	title,
	tabbable,
	dragging,
	onCloseAutoFocus,
	children,
}: {
	title: string;
	/** Its row is the body's tab stop, so Tab reaches it from there. */
	tabbable: boolean;
	/** Some row is being dragged, so no tooltip shows. */
	dragging: boolean;
	/** Where focus goes when the menu closes; the default is back to the `...`. */
	onCloseAutoFocus?: (e: Event) => void;
	children: React.ReactNode;
}) {
	const [menu, setMenu] = useState(false);
	const handedBack = useRef(false);

	const onMenu = useCallback((next: boolean) => {
		setMenu(next);
		if (!next) handedBack.current = true;
	}, []);

	const canTip = useCallback(() => !menu && !dragging && !handedBack.current, [menu, dragging]);

	return (
		<DropdownMenu open={menu} onOpenChange={onMenu}>
			<Tooltip canOpen={canTip}>
				{/* The menu's trigger outside the tooltip's, so the row's hover
				    action still sees the menu's data-state and stays up while it
				    is open. */}
				<DropdownMenuTrigger asChild>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							ring="inset"
							tabIndex={tabbable ? 0 : -1}
							aria-label={`Actions for ${title}`}
							onPointerEnter={() => {
								handedBack.current = false;
							}}
							onBlur={() => {
								handedBack.current = false;
							}}
							className={sidebarRowAction}
						>
							<Ellipsis />
						</IconButton>
					</TooltipTrigger>
				</DropdownMenuTrigger>
				<TooltipContent side="bottom">More</TooltipContent>
			</Tooltip>
			<DropdownMenuContent align="start" className={planeMenu} onCloseAutoFocus={onCloseAutoFocus}>
				{children}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
