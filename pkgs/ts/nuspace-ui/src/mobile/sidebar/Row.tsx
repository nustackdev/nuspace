// The sidebar screen's one row: every line under the header is drawn by it,
// the section titles included, so every edge lines up. The header
// (../Header.tsx) is drawn on the same lanes.
//
//   | pad | indent | lead | label ................... | trail |
//
//   pad      12px, inside the body's 8px gutter
//   indent   one lead per depth level: a child's icon sits under its
//            parent's label
//   lead     32px: a 20px icon, then the gap to the label. The lane sizes
//            whatever it holds (a lucide glyph, a plane's emoji, a folder)
//   label    the rest, truncating
//   trail    44px at the right edge, a tap target: every chevron and every +
//            on the screen sits in it, so they form one column
//
// A row's tap does what its element does (a link, a button); `main` makes
// the lead and the label one link, so the trailing button stays its own tap.

import { IconButton } from "@nustackdev/ui-kit";
import { ChevronRight, Plus } from "lucide-react";
import type * as React from "react";
import {
	mobileChevron,
	mobileIndent,
	mobileRow,
	mobileRowLabel,
	mobileRowLead,
	mobileRowMain,
	mobileRowTrail,
	mobileTrailButton,
} from "../../design";

type Kind = "row" | "note" | "head";

type RowProps = {
	/** The element the row is: a link, a button, or a plain line. */
	as?: "a" | "button" | "div";
	kind?: Kind;
	depth?: number;
	selected?: boolean;
	/** The leading icon; a row's lane stays (empty) without one, so labels line up. */
	icon?: React.ReactNode;
	label: React.ReactNode;
	/** The trail lane's content: a chevron, a + or a chevron button. */
	trail?: React.ReactNode;
	/** The lead and label as one link inside a plain row, apart from the trail. */
	main?: { href: string; current?: boolean };
	className?: string;
	style?: React.CSSProperties;
	children?: never;
} & Omit<React.AllHTMLAttributes<HTMLElement>, "label" | "as">;

export function MobileRow({
	as = "div",
	kind = "row",
	depth = 0,
	selected = false,
	icon,
	label,
	trail,
	main,
	className,
	style,
	...rest
}: RowProps) {
	const Tag = as as React.ElementType;
	// Titles start at the icons' edge; rows and notes keep the lane.
	const lane = kind === "row" || kind === "note";
	const head = (
		<>
			{lane ? (
				<span aria-hidden="true" className={mobileRowLead}>
					{icon}
				</span>
			) : null}
			<span className={mobileRowLabel}>{label}</span>
		</>
	);
	return (
		<Tag
			{...(as === "button" ? { type: "button" } : null)}
			{...rest}
			className={mobileRow(kind, selected, className)}
			style={{ ...mobileIndent(depth), ...style }}
		>
			{main ? (
				<a
					href={main.href}
					aria-current={main.current ? "page" : undefined}
					className={mobileRowMain}
				>
					{head}
				</a>
			) : (
				head
			)}
			<span className={mobileRowTrail}>{trail}</span>
		</Tag>
	);
}

/** The chevron of a folding row: right when folded, down when open. Decorative. */
export function RowChevron({ open }: { open: boolean }) {
	return <ChevronRight aria-hidden="true" className={mobileChevron(open)} />;
}

/** A + in the trail lane. */
export function RowAdd({ label, onClick }: { label: string; onClick: () => void }) {
	return (
		<IconButton
			variant="ghost"
			ring="inset"
			aria-label={label}
			onClick={onClick}
			className={mobileTrailButton}
		>
			<Plus />
		</IconButton>
	);
}

/** A chevron button in the trail lane: folds a branch, apart from the row's own tap. */
export function RowFold({
	open,
	label,
	onClick,
}: {
	open: boolean;
	label: string;
	onClick: () => void;
}) {
	return (
		<button type="button" aria-label={label} className={mobileTrailButton} onClick={onClick}>
			<RowChevron open={open} />
		</button>
	);
}
