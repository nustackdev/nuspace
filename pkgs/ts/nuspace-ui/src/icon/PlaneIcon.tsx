// One plane icon, drawn: a lucide glyph (by the kit) or an emoji, in the same box.
//
// Decorative everywhere it is used (the title or the row beside it names the
// plane), so it is hidden from a screen reader. The ref reaches the element,
// so a popover can anchor on it.

import { iconFor } from "@nustackdev/ui-kit";
import type * as React from "react";
import { type IconSize, iconEmoji, iconGlyph } from "../design";
import { DEFAULT_ICON_NAME } from "./pack";
import type { Icon } from "./parse";

export function PlaneIcon({
	icon,
	size = "sm",
	className,
	ref,
}: {
	icon: Icon;
	size?: IconSize;
	className?: string;
	ref?: React.Ref<HTMLElement & SVGSVGElement>;
}) {
	if (icon.kind === "emoji") {
		return (
			<span ref={ref} aria-hidden="true" className={iconEmoji(size, className)}>
				{icon.char}
			</span>
		);
	}
	const Glyph = iconFor(icon.name) ?? iconFor(DEFAULT_ICON_NAME);
	if (!Glyph) return null;
	return <Glyph ref={ref} aria-hidden="true" className={iconGlyph(size, className)} />;
}
