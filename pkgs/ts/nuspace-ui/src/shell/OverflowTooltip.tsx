// A tooltip for a title that truncates: it shows the full text, and only when
// the ellipsis is actually hiding some of it.
//
// Whether the text is cut off is read when the tooltip asks to open, not on
// every render, so a resize, a rename or a rail drag needs nothing to keep it
// right. The measured box is the trigger or any element inside it, so a link
// whose inner span carries the ellipsis works the same as a bare span.

import { Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useCallback, useEffect, useRef, useState } from "react";

/** Whether `el` shows less than all of its text. */
export function isTruncated(el: Element): boolean {
	return el.scrollWidth > el.clientWidth;
}

/** The first box under `trigger`, itself included, that cuts its text off. */
function truncatedIn(trigger: HTMLElement | null): Element | null {
	if (!trigger) return null;
	if (isTruncated(trigger)) return trigger;
	for (const el of trigger.querySelectorAll("*")) if (isTruncated(el)) return el;
	return null;
}

// What the kit's TooltipContent adds around the text (px-2, a 1px border, a
// 4px side offset) and its cap (max-w-xs), to guess its width before it opens.
const TOOLTIP_CHROME = 22;
const TOOLTIP_MAX = 320;

/** Whether a tooltip for `text` fits to the right of `trigger`. */
function fitsRight(trigger: HTMLElement, text: Element): boolean {
	const width = Math.min(text.scrollWidth + TOOLTIP_CHROME, TOOLTIP_MAX + 4);
	return trigger.getBoundingClientRect().right + width <= document.documentElement.clientWidth;
}

export function OverflowTooltip({
	label,
	side = "right",
	disabled = false,
	children,
}: {
	/** The full text. */
	label: string;
	/** Where it opens. Right drops to bottom when there is no room. */
	side?: "right" | "bottom";
	/** Refuse to open, and close if open. Eg while a row is dragged. */
	disabled?: boolean;
	/** The trigger, rendered `asChild`, so it keeps its own element and handlers. */
	children: React.ReactElement;
}) {
	const trigger = useRef<HTMLElement | null>(null);
	// A callback, since the kit types the trigger as a button and `asChild`
	// puts whatever element the caller hands in there.
	const triggerRef = useCallback((el: HTMLElement | null) => {
		trigger.current = el;
	}, []);
	const [open, setOpen] = useState(false);
	const [at, setAt] = useState(side);

	// A drag that starts under an open tooltip closes it for good, so it does
	// not come back once the drag ends.
	useEffect(() => {
		if (disabled) setOpen(false);
	}, [disabled]);

	const onOpenChange = useCallback(
		(next: boolean) => {
			if (!next || disabled) {
				setOpen(false);
				return;
			}
			const el = trigger.current;
			const text = truncatedIn(el);
			if (!el || !text) return;
			setAt(side === "right" && !fitsRight(el, text) ? "bottom" : side);
			setOpen(true);
		},
		[disabled, side],
	);

	return (
		<Tooltip open={open && !disabled} onOpenChange={onOpenChange}>
			<TooltipTrigger asChild ref={triggerRef}>
				{children}
			</TooltipTrigger>
			<TooltipContent side={at}>{label}</TooltipContent>
		</Tooltip>
	);
}
