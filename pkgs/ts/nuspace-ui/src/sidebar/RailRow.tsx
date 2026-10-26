// One rail row: the tree item, its three lanes, and the right-click menu.
//
// The lane, the label and the actions are slots rather than props with
// opinions, so what a row carries is the caller's business and the shell stays
// the one place the three lanes are positioned against each other.
//
// The row, not the anchor, is the tree item: an ARIA tree wants focus on the
// item and the roving tabindex has to land somewhere that owns aria-level and
// aria-expanded. The anchor stays a real anchor (cmd-click, middle-click,
// aria-current) but drops out of the tab order.

import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuTrigger,
	cn,
	NavLink,
} from "@nustackdev/ui-kit";
import type * as React from "react";
import {
	railActions,
	railIndent,
	railLabel,
	railLane,
	railMenu,
	railRow,
	railTitle,
} from "../design";

export function RailRow({
	rowKey,
	selected,
	open = false,
	tabbable,
	indent,
	level,
	posinset,
	setsize,
	expanded,
	lane,
	label,
	actions,
	menu,
	onMenuCloseAutoFocus,
	drag,
	className,
	onFocus,
	onKeyDown,
	planeId,
	onClick,
	ref,
	...rest
}: Omit<React.HTMLAttributes<HTMLDivElement>, "onClick" | "onFocus" | "onKeyDown"> & {
	/** What `useRailFocus` addresses this row by. */
	rowKey: string;
	/** The row's Plane, for what acts on the Plane you are on (../sidebar/add.ts). */
	planeId?: string;
	/** The focused pane's Plane. */
	selected: boolean;
	/** Showing in a pane that is not the focused one. */
	open?: boolean;
	tabbable: boolean;
	/** Tree depth, for the left offset. A flat rail leaves it off. */
	indent?: number;
	/** aria-level, which is 1-based, so a root row is 1 and not 0. */
	level: number;
	posinset: number;
	setsize: number;
	/** Whether the row is unfolded. Leave it off for a row that never folds. */
	expanded?: boolean;
	/** The fixed-width lane: the icon, and the chevron that stacks in its place. */
	lane: React.ReactNode;
	/** The label lane: usually a `RailRowLink` or a `RailRowInput`. */
	label: React.ReactNode;
	/** The buttons of the hover-revealed action lane. Null for a row with none, which then takes no room for it. */
	actions: React.ReactNode;
	/** Items for the right-click menu. Null for a row with none. */
	menu: React.ReactNode;
	/** Where focus goes when the right-click menu closes. See the kit's menu. */
	onMenuCloseAutoFocus?: (e: Event) => void;
	/** Drag and drop handlers, see ./useRailDrag.ts. */
	drag?: React.HTMLAttributes<HTMLDivElement> & { draggable?: boolean };
	/** Extra classes, eg while dragged or dropped into. */
	className?: string;
	onFocus: (e: React.FocusEvent<HTMLDivElement>) => void;
	onKeyDown: (e: React.KeyboardEvent) => void;
	/** A click anywhere on the row, for a row that is one button (eg an extension's). */
	onClick?: (e: React.MouseEvent<HTMLDivElement>) => void;
	/**
	 * With `ref` and the rest, what a kit trigger (a tooltip's) hands the row
	 * it wraps. The row takes them on its own box.
	 */
	ref?: React.Ref<HTMLDivElement>;
}) {
	const body = (
		<div
			{...rest}
			ref={ref}
			// A tree row takes its left offset from railIndent, so it needs no
			// inset. A flat rail leaves indent off and pays for the offset
			// itself, which is what the inset is.
			className={cn(railRow(selected, indent === undefined, open), className)}
			style={indent === undefined ? undefined : railIndent(indent)}
			role="treeitem"
			tabIndex={tabbable ? 0 : -1}
			data-rail-key={rowKey}
			data-plane-id={planeId}
			aria-selected={selected}
			aria-expanded={expanded}
			aria-level={level}
			aria-posinset={posinset}
			aria-setsize={setsize}
			onFocus={onFocus}
			onKeyDown={onKeyDown}
			// Focus on click is the body's (./useRailFocus.ts).
			onClick={onClick}
			{...drag}
		>
			<span className={railLane}>{lane}</span>
			{label}
			{actions === null ? null : <div className={railActions}>{actions}</div>}
		</div>
	);

	if (menu === null) return body;

	return (
		<ContextMenu>
			<ContextMenuTrigger asChild>{body}</ContextMenuTrigger>
			<ContextMenuContent className={railMenu} onCloseAutoFocus={onMenuCloseAutoFocus}>
				{menu}
			</ContextMenuContent>
		</ContextMenu>
	);
}

/**
 * The row's label: a real anchor that is not a tab stop, because the row it
 * sits in is the one. It carries no tooltip: a cut-off name is read by
 * widening the rail.
 */
export function RailRowLink({
	href,
	label,
	selected,
	titleClassName = railTitle,
	onClick,
	onDoubleClick,
}: {
	href: string;
	label: string;
	selected: boolean;
	/** Override only to drop the title a tier, e.g. for a row with no name. */
	titleClassName?: string;
	onClick: (e: React.MouseEvent<HTMLElement>) => void;
	/** A tree row renames on it; a pinned row leaves it off. */
	onDoubleClick?: () => void;
}) {
	return (
		<NavLink
			size="sm"
			active={selected}
			href={href}
			tabIndex={-1}
			onClick={onClick}
			onDoubleClick={onDoubleClick}
			className={railLabel}
		>
			<span className={titleClassName}>{label}</span>
		</NavLink>
	);
}
