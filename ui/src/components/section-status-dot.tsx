// SectionStatusDot / SectionStatusPill.
//
// The two ways a section's state shows up in the editor:
//   - dot   8px, lives in the block gutter. Always-on, must not be noisy.
//   - pill  hue + icon + word. For a block header or a page-level summary.
//
// The dot is drawn with borders and clip-path rather than an icon font, so it
// stays crisp at 8px and carries zero dependency. Its color is `currentColor`,
// set by the --section-* token on the wrapper, so there is exactly one place
// a status hue is chosen (tokens.css) and nothing here can drift from it.
//
// The pill is the kit's StatusPill, unmodified. We only pick its tone.
//
// GRADUATION CANDIDATE: the dot is a generic primitive (see the task report).
// Nothing about it is nuspace-specific except the state names it is fed.

import { cn, StatusPill } from "@nustackdev/ui-kit";
import type * as React from "react";

import type { SectionDotShape, SectionStatus } from "../design";
import { SECTION_STATUS } from "../design";

/* Silhouettes. Each is a distinct outline at 8px, so the state reads without
 * color for anyone who cannot separate the hues (a11y.md §7). */
const SHAPE: Record<SectionDotShape, string> = {
	hollow: "rounded-full border-[1.5px] border-current bg-transparent",
	pulse: "rounded-full bg-current animate-pulse",
	solid: "rounded-full bg-current",
	square: "rounded-[1px] bg-current",
	triangle: "bg-current [clip-path:polygon(50%_0%,100%_100%,0%_100%)]",
	diamond: "rounded-[1px] bg-current rotate-45",
};

export interface SectionStatusDotProps
	extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> {
	status: SectionStatus;
	/** Render as decoration next to a visible label. Drops the a11y text. */
	decorative?: boolean;
}

export function SectionStatusDot({
	status,
	decorative = false,
	className,
	...props
}: SectionStatusDotProps) {
	const t = SECTION_STATUS[status];
	const shape = cn(
		"inline-block size-doc-dot shrink-0",
		"transition-colors duration-fast ease-out",
		t.fg,
		SHAPE[t.shape],
		className,
	);

	// Two branches rather than conditional aria props: a decorative dot sits
	// next to a visible label and must not be announced twice.
	if (decorative) {
		return (
			<span
				aria-hidden="true"
				data-slot="section-status-dot"
				data-status={status}
				className={shape}
				{...props}
			/>
		);
	}

	return (
		<span
			role="img"
			aria-label={`section ${t.label}, ${t.hint}`}
			data-slot="section-status-dot"
			data-status={status}
			title={t.hint}
			className={shape}
			{...props}
		/>
	);
}

export interface SectionStatusPillProps
	extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> {
	status: SectionStatus;
	size?: "sm" | "md";
}

export function SectionStatusPill({
	status,
	size = "sm",
	className,
	...props
}: SectionStatusPillProps) {
	const t = SECTION_STATUS[status];
	return (
		<StatusPill
			tone={t.tone}
			size={size}
			data-status={status}
			title={t.hint}
			className={className}
			{...props}
		>
			{t.label}
		</StatusPill>
	);
}
