// The section: the one piece every group of the sidebar is.
//
// Everything optional: a title, a count after it, a fold, right actions on
// the rows' right edge. The body is rows, a
// tree, or anything custom. With no title it is just the body (the nav
// section).
//
// The title folds and unfolds the body, the chevron after it saying which.
// It can take drops (`head`, a desk folder's), and while `rename` is set it
// is the kit's `InlineEdit` instead.
//
// The fold is controlled, because the body's one tab stop (./focus.ts) has to
// know which rows are drawn: `useSectionFold` keeps it, per section, across
// reloads.

import { cn, IconButton, InlineEdit, readStored, writeStored } from "@nustackdev/ui-kit";
import { ChevronRight } from "lucide-react";
import type * as React from "react";
import { useCallback, useState } from "react";
import {
	sidebarInput,
	sidebarRows,
	sidebarSection,
	sidebarSectionAction,
	sidebarSectionActions,
	sidebarSectionChevron,
	sidebarSectionCount,
	sidebarSectionHead,
	sidebarSectionLabel,
	sidebarSectionTitle,
	sidebarSectionTitleButton,
} from "../design";
import type { RowRename } from "./SidebarRow";

export type SidebarSectionProps = {
	/** Names the section for what it stores (fold, height). Unique in the sidebar. */
	id: string;
	title?: string;
	/** The body's accessible name when there is no title. */
	label?: string;
	count?: number;
	/** Controlled fold: the title folds and unfolds the body. Leave both off for a section that never folds. */
	folded?: boolean;
	onFoldedChange?: (folded: boolean) => void;
	/** Buttons on the title line's right end, shown while it is hovered. */
	actions?: React.ReactNode;
	/** Handlers and attributes on the title line (drops onto the title). */
	head?: React.HTMLAttributes<HTMLDivElement>;
	/** A class on the title line on top of its own (a drop mark). */
	headClassName?: string;
	/** Drawn inside the title line, last (a drop line above or under it). */
	headMark?: React.ReactNode;
	/** Rename in place: the title becomes an input while set. */
	rename?: RowRename | null;
	children?: React.ReactNode;
};

export function SidebarSection({
	id,
	title,
	label,
	count,
	folded = false,
	onFoldedChange,
	actions,
	head,
	headClassName,
	headMark,
	rename,
	children,
}: SidebarSectionProps) {
	const foldable = !!onFoldedChange;
	const open = !foldable || !folded;
	const body = (
		<div role="tree" aria-label={title ?? label} className={sidebarRows}>
			{children}
		</div>
	);
	return (
		<section aria-label={title ?? label} className={sidebarSection} data-section={id}>
			{title ? (
				<div {...head} className={cn(sidebarSectionHead, headClassName)}>
					{rename ? (
						<span className={sidebarSectionTitle}>
							<InlineEdit
								initial={title}
								label={rename.label}
								onCommit={(value) => rename.onCommit(value)}
								onCancel={rename.onCancel}
								className={sidebarInput}
							/>
						</span>
					) : foldable ? (
						<button
							type="button"
							aria-expanded={open}
							onClick={() => onFoldedChange?.(!folded)}
							className={cn(sidebarSectionTitle, sidebarSectionTitleButton)}
						>
							<span data-drag-title className={sidebarSectionLabel}>
								{title}
							</span>
							<ChevronRight aria-hidden="true" className={sidebarSectionChevron(open)} />
						</button>
					) : (
						<span className={sidebarSectionTitle}>
							<span data-drag-title className={sidebarSectionLabel}>
								{title}
							</span>
						</span>
					)}
					{count !== undefined ? <span className={sidebarSectionCount}>{count}</span> : null}
					{actions ? (
						<div data-row-action="" className={sidebarSectionActions}>
							{actions}
						</div>
					) : null}
					{headMark}
				</div>
			) : null}
			{open ? body : null}
		</section>
	);
}

/** A section's fold, kept across reloads. */
export function useSectionFold(id: string): [boolean, (folded: boolean) => void] {
	const key = `nuspace.sidebar.${id}.folded`;
	const [folded, setFolded] = useState(() => readStored(key) === "1");
	const set = useCallback(
		(next: boolean) => {
			setFolded(next);
			writeStored(key, next ? "1" : "0");
		},
		[key],
	);
	return [folded, set];
}

/** A section title's action: the section buttons' look, with its tooltip. */
export function SectionAction({
	label,
	tip,
	onClick,
	children,
}: {
	/** The accessible name. */
	label: string;
	tip: React.ReactNode;
	onClick: () => void;
	children: React.ReactNode;
}) {
	return (
		<IconButton
			variant="ghost"
			size="xs"
			ring="inset"
			aria-label={label}
			tip={tip}
			onClick={onClick}
			className={sidebarSectionAction}
		>
			{children}
		</IconButton>
	);
}
