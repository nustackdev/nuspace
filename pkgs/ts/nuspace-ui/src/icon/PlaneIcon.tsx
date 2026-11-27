// One plane icon, drawn: the kit's `IconMark`, with the plane default behind it.
//
// Kept for the mobile shell, which still draws through it. Everything else
// uses `IconMark` directly.

import { IconMark, type IconMarkSize, type IconValue } from "@nustackdev/ui-kit";
import type * as React from "react";
import { DEFAULT_ICON } from "./parse";

export function PlaneIcon({
	icon,
	size = "sm",
	className,
	ref,
}: {
	icon: IconValue;
	size?: IconMarkSize;
	className?: string;
	ref?: React.Ref<HTMLElement & SVGSVGElement>;
}) {
	return (
		<IconMark icon={icon} fallback={DEFAULT_ICON} size={size} className={className} ref={ref} />
	);
}
