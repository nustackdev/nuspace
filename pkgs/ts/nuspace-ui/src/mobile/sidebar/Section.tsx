// The sidebar screen's one section: every group on the screen is one, as on
// desktop (../../sidebar/SidebarSection.tsx). An optional title, then the
// body; with no title it is just the body (the nav).
//
// The title is a row (./Row.tsx, kind "head"): the same grid as the rows
// under it, the text at the icons' edge in the quieter title style, and its
// fold chevron or its + in the trail lane, the column every row's chevron
// sits in. A title that folds is one button: a tap folds or unfolds the
// body. Titles and rows are the same object; only the text says heading.

import type * as React from "react";
import { mobileSection, mobileSectionFold } from "../../design";
import { MobileRow, RowChevron } from "./Row";

export function MobileSection({
	title,
	label,
	folded,
	onFold,
	trail,
	head,
	children,
}: {
	title?: React.ReactNode;
	/** The section's accessible name, when the title is not plain text or there is none. */
	label: string;
	/** Controlled fold: set both to make the title fold the body. */
	folded?: boolean;
	onFold?: (folded: boolean) => void;
	/** The title's trail lane when it does not fold: a +. */
	trail?: React.ReactNode;
	/** Attributes on the title row (a data hook). */
	head?: Record<`data-${string}`, string>;
	children?: React.ReactNode;
}) {
	const foldable = !!onFold;
	const open = !foldable || !folded;
	return (
		<section aria-label={label} className={mobileSection}>
			{title === undefined ? null : foldable ? (
				<MobileRow
					{...head}
					as="button"
					kind="head"
					aria-expanded={open}
					onClick={() => onFold(!folded)}
					className={mobileSectionFold}
					label={title}
					trail={<RowChevron open={open} />}
				/>
			) : (
				<MobileRow {...head} kind="head" label={title} trail={trail} />
			)}
			{open ? children : null}
		</section>
	);
}
