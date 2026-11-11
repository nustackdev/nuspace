// The rows of a desk folder, by kind:
//
//   plane item   its plane's icon and title. Navigated away (it has a
//                recent), `[icon] / [title]`: the icon is the original
//                plane's, a click on it resets the item; the title is the
//                recent plane's, a click opens the item as it is now. On
//                hover: save and reset (navigated only), close
//   strip        a `Strip` row that opens the strip; its chevron folds it
//   column       a `Column` group, for a column of 2+ panes: opens the
//                strip with its top pane focused; its chevron folds it
//   pane         reads like a plane item row, and opens the strip with that
//                pane focused and on screen
//
// Every row has a close on hover: an item, a pane or a column out of its
// parent. The rows are links (./links.ts), so a Cmd click is the browser's.
// An item row drags its item, a pane row its pane. Selection is the
// Sidebar's (./folders.ts `selectedKey`).

import { IconButton } from "@nustackdev/ui-kit";
import { ChevronRight, Columns3, RotateCcw, Rows3, Save, X } from "lucide-react";
import type * as React from "react";
import { lookOf, type PlaneLook } from "../core/looks";
import {
	closeColumn,
	closeItem,
	closePane,
	hrefFor,
	itemHref,
	resetItem,
	saveItem,
} from "../core/router";
import {
	sidebarChevron,
	sidebarCrumbSlash,
	sidebarIcon,
	sidebarResetIcon,
	sidebarTwisty,
} from "../design";
import { writeItem, writePane } from "../desk/dnd";
import type { Links } from "../desk/model";
import { shown } from "../desk/model";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { useSidebarNav } from "./focus";
import {
	arrowMove,
	COLUMN_TITLE,
	type FolderRow,
	rowDepth,
	STRIP_TITLE,
	setFolded,
} from "./folders";
import { RESET_ATTR, resetAttr } from "./links";
import { RowAction, SidebarRow } from "./SidebarRow";

/** What a drop site spreads on its element. */
export type DropProps = Pick<
	React.HTMLAttributes<HTMLDivElement>,
	"onDragOver" | "onDragLeave" | "onDrop"
>;

export type DragProps = React.HTMLAttributes<HTMLDivElement> & { draggable?: boolean };

/** One row of a folder, by kind. */
export function DeskRow({
	deskId,
	row,
	next,
	looks,
	selected,
	className,
	drop,
	dragOf,
}: {
	deskId: string;
	row: FolderRow;
	/** The row drawn under it, where Right steps into an open strip or column. */
	next: FolderRow | undefined;
	looks: Record<string, PlaneLook>;
	selected: boolean;
	className?: string;
	drop: DropProps;
	dragOf: (key: string, write: (dt: DataTransfer) => void) => DragProps;
}) {
	const depth = rowDepth(row);
	const { focusKey } = useSidebarNav();
	const toggle = () => setFolded(row.key, "open" in row && row.open);
	// Left and Right as on a Planes tree row (./folders.ts `arrowMove`).
	const onKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
		if (e.target !== e.currentTarget) return;
		if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
		const move = arrowMove(deskId, row, e.key, next);
		if (!move) return;
		e.preventDefault();
		if ("fold" in move) toggle();
		else focusKey(move.focus);
	};
	if (row.kind === "plane") {
		return (
			<LinkRow
				rowKey={row.key}
				href={itemHref(deskId, row.item)}
				links={row.links}
				looks={looks}
				depth={depth}
				selected={selected}
				className={className}
				drag={{ ...dragOf(row.key, (dt) => writeItem(dt, deskId, row.item)), ...drop }}
				onKeyDown={onKeyDown}
				reset={resetAttr(deskId, row.item)}
				onSave={() => saveItem(deskId, row.item)}
				onReset={() => resetItem(deskId, row.item)}
				onClose={() => closeItem(deskId, row.item)}
			/>
		);
	}
	if (row.kind === "pane") {
		return (
			<LinkRow
				rowKey={row.key}
				href={itemHref(deskId, row.item)}
				pane={row.plane}
				links={row.links}
				looks={looks}
				depth={depth}
				selected={selected}
				className={className}
				drag={{ ...dragOf(row.key, (dt) => writePane(dt, deskId, row.item, row.plane)), ...drop }}
				onKeyDown={onKeyDown}
				reset={resetAttr(deskId, row.item, row.plane)}
				onSave={() => saveItem(deskId, row.item, row.plane)}
				onReset={() => resetItem(deskId, row.item, row.plane)}
				onClose={() => closePane(deskId, row.item, row.plane)}
			/>
		);
	}
	if (row.kind === "strip") {
		return (
			<SidebarRow
				rowKey={row.key}
				href={itemHref(deskId, row.item)}
				label={STRIP_TITLE}
				depth={depth}
				expanded={row.open}
				selected={selected}
				className={className}
				drag={{ ...dragOf(row.key, (dt) => writeItem(dt, deskId, row.item)), ...drop }}
				onKeyDown={onKeyDown}
				icon={
					<>
						<Columns3 aria-hidden="true" className={sidebarIcon(true)} />
						<IconButton
							variant="ghost"
							size="xs"
							ring="inset"
							tabIndex={-1}
							aria-label={row.open ? "Collapse strip" : "Expand strip"}
							aria-expanded={row.open}
							onMouseDown={(e) => e.preventDefault()}
							onClick={(e) => {
								e.stopPropagation();
								toggle();
							}}
							className={sidebarTwisty(true)}
						>
							<ChevronRight className={sidebarChevron(row.open)} />
						</IconButton>
					</>
				}
				trailing={{
					action: <CloseAction label="Close strip" onClose={() => closeItem(deskId, row.item)} />,
				}}
			/>
		);
	}
	return (
		<SidebarRow
			rowKey={row.key}
			href={itemHref(deskId, row.item)}
			data-sidebar-pane={row.planes[0]}
			label={COLUMN_TITLE}
			depth={depth}
			expanded={row.open}
			selected={selected}
			className={className}
			drag={drop}
			onKeyDown={onKeyDown}
			icon={
				<>
					<Rows3 aria-hidden="true" className={sidebarIcon(true)} />
					<IconButton
						variant="ghost"
						size="xs"
						ring="inset"
						tabIndex={-1}
						aria-label={row.open ? "Collapse column" : "Expand column"}
						aria-expanded={row.open}
						onMouseDown={(e) => e.preventDefault()}
						onClick={(e) => {
							e.stopPropagation();
							toggle();
						}}
						className={sidebarTwisty(true)}
					>
						<ChevronRight className={sidebarChevron(row.open)} />
					</IconButton>
				</>
			}
			trailing={{
				action: (
					<CloseAction
						label="Close column"
						onClose={() => closeColumn(deskId, row.item, row.column)}
					/>
				),
			}}
		/>
	);
}

/**
 * A plane item or pane row: icon and title, or `[icon] / [title]` once
 * navigated, the icon the original's and the title the recent's. Both are
 * links: the title to the item (a pane row says its pane), the icon to the
 * original plane, a plain click on it resetting the item (./links.ts). On
 * hover: save and reset (navigated only: the recent becomes the original,
 * or goes) and close.
 */
function LinkRow({
	rowKey,
	href,
	pane,
	links,
	looks,
	depth,
	selected,
	className,
	drag,
	onKeyDown,
	reset,
	onSave,
	onReset,
	onClose,
}: {
	rowKey: string;
	href: string;
	/** The plane a pane row's pane shows. */
	pane?: string;
	links: Links;
	looks: Record<string, PlaneLook>;
	depth: number;
	selected: boolean;
	className?: string;
	drag: DragProps;
	onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => void;
	/** Its `resetAttr`, which the icon link carries once navigated. */
	reset: string;
	onSave: () => void;
	onReset: () => void;
	onClose: () => void;
}) {
	const now = shown(links);
	const look = lookOf(looks, now.plane);
	const navigated = !!links.recent;
	const original = lookOf(looks, links.original.plane);
	return (
		<SidebarRow
			rowKey={rowKey}
			planeId={now.plane}
			href={href}
			data-sidebar-pane={pane}
			label={look.title}
			lead={
				navigated ? (
					<span aria-hidden="true" className={sidebarCrumbSlash}>
						/
					</span>
				) : undefined
			}
			depth={depth}
			selected={selected}
			className={className}
			drag={drag}
			onKeyDown={onKeyDown}
			icon={
				navigated ? (
					<IconButton
						asChild
						variant="ghost"
						size="xs"
						ring="inset"
						aria-label={`Reset to ${original.title}`}
						tip={`Reset to ${original.title}`}
						className={sidebarResetIcon}
					>
						<a
							href={hrefFor(links.original.plane, links.original.params)}
							{...{ [RESET_ATTR]: reset }}
							tabIndex={-1}
							draggable={false}
							onMouseDown={(e) => e.preventDefault()}
						>
							<PlaneIcon icon={planeIcon(original.icon)} className={sidebarIcon(false)} />
						</a>
					</IconButton>
				) : (
					<PlaneIcon icon={planeIcon(look.icon)} className={sidebarIcon(false)} />
				)
			}
			trailing={{
				action: (
					<>
						{navigated ? (
							<>
								<RowAction label={`Save ${look.title}`} tip="Save" onClick={onSave}>
									<Save />
								</RowAction>
								<RowAction
									label={`Reset ${look.title} to ${original.title}`}
									tip={`Reset to ${original.title}`}
									onClick={onReset}
								>
									<RotateCcw />
								</RowAction>
							</>
						) : null}
						<RowAction label={`Close ${look.title}`} tip="Close" onClick={onClose}>
							<X />
						</RowAction>
					</>
				),
			}}
		/>
	);
}

/** A row's close, on hover. */
function CloseAction({ label, onClose }: { label: string; onClose: () => void }) {
	return (
		<RowAction label={label} tip="Close" onClick={onClose}>
			<X />
		</RowAction>
	);
}
