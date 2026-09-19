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

import { ContextMenu, ContextMenuContent, ContextMenuTrigger, NavLink } from "@nustackdev/ui-kit";
import type * as React from "react";
import {
	railActions,
	railIndent,
	railLabel,
	railLane,
	railLaneStyle,
	railRow,
	railSectionTitle,
	railTitle,
} from "../../design";

export function RailRow({
	rowKey,
	selected,
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
	onFocus,
	onKeyDown,
}: {
	/** What `useRailFocus` addresses this row by. */
	rowKey: string;
	selected: boolean;
	tabbable: boolean;
	/** Tree depth, for the left offset. A flat rail leaves it off. */
	indent?: number;
	/** aria-level, which is 1-based, so a root row is 1 and not 0. */
	level: number;
	posinset: number;
	setsize: number;
	/** Only for a row that has children. Leave it off for a leaf. */
	expanded?: boolean;
	/** The fixed-width lane: a twisty, a leaf icon, a status dot. */
	lane: React.ReactNode;
	/** The label lane: usually a `RailRowLink` or a `RailRowInput`. */
	label: React.ReactNode;
	/** The buttons of the hover-revealed action lane. */
	actions: React.ReactNode;
	/** Items for the right-click menu. */
	menu: React.ReactNode;
	onFocus: () => void;
	onKeyDown: (e: React.KeyboardEvent) => void;
}) {
	const body = (
		<div
			// A tree row takes its left offset from railIndent, so it needs no
			// inset. A flat rail leaves indent off and pays for the offset
			// itself, which is what the inset is.
			className={railRow(selected, indent === undefined)}
			style={indent === undefined ? undefined : railIndent(indent)}
			role="treeitem"
			tabIndex={tabbable ? 0 : -1}
			data-rail-key={rowKey}
			aria-selected={selected}
			aria-expanded={expanded}
			aria-level={level}
			aria-posinset={posinset}
			aria-setsize={setsize}
			onFocus={onFocus}
			onKeyDown={onKeyDown}
		>
			<span className={railLane} style={railLaneStyle}>
				{lane}
			</span>
			{label}
			<div className={railActions}>{actions}</div>
		</div>
	);

	return (
		<ContextMenu>
			<ContextMenuTrigger asChild>{body}</ContextMenuTrigger>
			<ContextMenuContent className="min-w-40">{menu}</ContextMenuContent>
		</ContextMenu>
	);
}

/**
 * The row's label: a real anchor that is not a tab stop, because the row it
 * sits in is the one.
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
	onDoubleClick: () => void;
}) {
	return (
		<NavLink
			size="sm"
			active={selected}
			href={href}
			title={label}
			tabIndex={-1}
			onClick={onClick}
			onDoubleClick={onDoubleClick}
			className={railLabel}
		>
			<span className={titleClassName}>{label}</span>
		</NavLink>
	);
}

/**
 * A section's label. Not an anchor, because a section is not a place: it is a
 * row that folds, and the only thing it opens is itself.
 */
export function RailSectionLabel({ label }: { label: string }) {
	return (
		<span className={railSectionTitle} title={label}>
			{label}
		</span>
	);
}
