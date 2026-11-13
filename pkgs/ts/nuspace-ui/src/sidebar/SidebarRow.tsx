// The row: the one line every section draws, and the action row built on it.
//
// An icon lane, a label (after an optional `lead`), and one optional
// trailing thing: a shortcut, a count or a hover action (`RowAction`). A
// tree row is the same row with a `depth`. A rename is the kit's
// `InlineEdit` in place of the label. One selected state for all (design/sidebar.ts).
//
// A row with an `href` is a link: its label is a real anchor (the kit's
// `NavLink`), so the sidebar's anchor catcher takes its click (./links.ts: a
// plain one is the app's, Cmd to the browser), and Enter or Space on the row
// clicks it the same way. A row with no `href` is one button: `onClick`,
// Enter and Space.
//
// The row, not the anchor, is the focusable item: one tab stop for the whole
// body (./focus.ts), the anchor out of the tab order.

import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuTrigger,
	cn,
	IconButton,
	InlineEdit,
	NavLink,
	ROVING_KEY,
	Shortcut,
} from "@nustackdev/ui-kit";
import type * as React from "react";
import {
	planeMenu,
	sidebarCount,
	sidebarHoverAction,
	sidebarIndent,
	sidebarInput,
	sidebarLabel,
	sidebarLane,
	sidebarLink,
	sidebarRow,
	sidebarRowAction,
	sidebarTitle,
	sidebarTitleEmpty,
	sidebarTrailing,
} from "../design";
import { useSidebarNav } from "./focus";

/** The one thing a row may carry at its end. */
export type Trailing =
	/** Keys by name, always shown; the kit `Shortcut` spells them. */
	| { shortcut: readonly string[] }
	| { count: number }
	/** A control shown on hover, on keyboard focus and while its menu is open. */
	| { action: React.ReactNode };

/** An inline rename in place of the label. */
export type RowRename = {
	/** The input's accessible name. */
	label: string;
	onCommit: (value: string) => void;
	onCancel: () => void;
};

export type SidebarRowProps = Omit<
	React.HTMLAttributes<HTMLDivElement>,
	"onClick" | "onKeyDown" | "onDoubleClick"
> & {
	/** What the body's focus addresses this row by. Unique in the sidebar. */
	rowKey: string;
	/** The icon lane: a glyph, or for a tree row the icon and the chevron that swaps in. */
	icon: React.ReactNode;
	label: string;
	/** Drawn between the icon lane and the label (a navigated desk row's slash). */
	lead?: React.ReactNode;
	/** Draw the label a tier back (a row with no name yet). */
	muted?: boolean;
	/** Where the row goes: a plane or desk url. Leave it off for a button row. */
	href?: string;
	selected?: boolean;
	/** Tree depth. A flat row leaves it off. */
	depth?: number;
	trailing?: Trailing;
	/** Rename in place: the label becomes an input while set. */
	rename?: RowRename | null;
	/** The row's plane, for what acts on the plane you are on (./add.ts). */
	planeId?: string;
	/** Items for the right-click menu. */
	menu?: React.ReactNode;
	/** Where focus goes when the right-click menu closes. */
	onMenuCloseAutoFocus?: (e: Event) => void;
	/** Drag handlers (./drag.ts). */
	drag?: React.HTMLAttributes<HTMLDivElement> & { draggable?: boolean };
	/** A button row's press: a click, Enter or Space. A link row's click, after the link's own. */
	onClick?: () => void;
	onDoubleClick?: () => void;
	/** Keys on top of the body's arrows. `preventDefault` to keep Enter and Space from the row. */
	onKeyDown?: (e: React.KeyboardEvent<HTMLDivElement>) => void;
	/** aria-level, 1 based, for a tree row. */
	level?: number;
	posinset?: number;
	setsize?: number;
	/** Whether the row is unfolded. Leave it off for a row that never folds. */
	expanded?: boolean;
	/** What a kit trigger (a tooltip's) hands the row it wraps. */
	ref?: React.Ref<HTMLDivElement>;
};

export function SidebarRow({
	rowKey,
	icon,
	label,
	lead,
	muted = false,
	href,
	selected = false,
	depth,
	trailing,
	rename,
	planeId,
	menu,
	onMenuCloseAutoFocus,
	drag,
	onClick,
	onDoubleClick,
	onKeyDown,
	level,
	posinset,
	setsize,
	expanded,
	className,
	ref,
	...rest
}: SidebarRowProps) {
	const { tabKey, setActiveKey, arrows } = useSidebarNav();

	const keyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
		if (arrows(e, rowKey)) return;
		onKeyDown?.(e);
		if (e.defaultPrevented || e.target !== e.currentTarget) return;
		if (e.key !== "Enter" && e.key !== " ") return;
		e.preventDefault();
		if (href) {
			// The link's own click, so the anchor catcher reads it.
			e.currentTarget
				.querySelector("a")
				?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
		} else onClick?.();
	};

	const body = (
		<div
			{...rest}
			ref={ref}
			className={cn(sidebarRow(selected, depth === undefined), className)}
			style={depth === undefined ? undefined : sidebarIndent(depth)}
			role="treeitem"
			tabIndex={tabKey === rowKey ? 0 : -1}
			{...{ [ROVING_KEY]: rowKey }}
			data-plane-id={planeId}
			aria-selected={selected}
			aria-expanded={expanded}
			aria-level={level}
			aria-posinset={posinset}
			aria-setsize={setsize}
			onFocus={(e) => {
				if (e.target === e.currentTarget) setActiveKey(rowKey);
			}}
			onKeyDown={keyDown}
			onClick={href ? undefined : onClick}
			onDoubleClick={href ? undefined : onDoubleClick}
			{...drag}
		>
			<span data-drag-icon className={sidebarLane}>
				{icon}
			</span>
			{lead}
			{rename ? (
				<InlineEdit
					initial={label}
					label={rename.label}
					onCommit={(value) => rename.onCommit(value)}
					onCancel={rename.onCancel}
					className={sidebarInput}
				/>
			) : href ? (
				<NavLink
					size="sm"
					active={selected}
					href={href}
					tabIndex={-1}
					onClick={onClick}
					onDoubleClick={onDoubleClick}
					className={sidebarLink}
				>
					<span data-drag-title className={muted ? sidebarTitleEmpty : sidebarTitle}>
						{label}
					</span>
				</NavLink>
			) : (
				<span className={sidebarLabel}>
					<span data-drag-title className={muted ? sidebarTitleEmpty : sidebarTitle}>
						{label}
					</span>
				</span>
			)}
			{trailing ? <TrailingThing trailing={trailing} /> : null}
		</div>
	);

	if (!menu) return body;

	return (
		<ContextMenu>
			<ContextMenuTrigger asChild>{body}</ContextMenuTrigger>
			<ContextMenuContent className={planeMenu} onCloseAutoFocus={onMenuCloseAutoFocus}>
				{menu}
			</ContextMenuContent>
		</ContextMenu>
	);
}

function TrailingThing({ trailing }: { trailing: Trailing }) {
	if ("shortcut" in trailing)
		return (
			<Shortcut
				keys={trailing.shortcut}
				variant="ghost"
				size="sm"
				className={sidebarTrailing}
				aria-hidden="true"
			/>
		);
	if ("count" in trailing) return <span className={sidebarCount}>{trailing.count}</span>;
	return (
		<div data-row-action="" className={sidebarHoverAction}>
			{trailing.action}
		</div>
	);
}

/**
 * A row's hover action: a small ghost icon button with its tooltip, out of
 * the tab order (the row is the tab stop), its click kept from the row.
 */
export function RowAction({
	label,
	tip,
	onClick,
	children,
}: {
	label: string;
	tip: React.ReactNode;
	onClick: () => void;
	children: React.ReactNode;
}) {
	return (
		<IconButton
			variant="ghost"
			size="sm"
			ring="inset"
			tabIndex={-1}
			aria-label={label}
			tip={tip}
			onClick={(e) => {
				e.stopPropagation();
				onClick();
			}}
			className={sidebarRowAction}
		>
			{children}
		</IconButton>
	);
}
