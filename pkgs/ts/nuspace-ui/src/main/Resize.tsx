// The resize handles of a column: its width, on its right edge, and its pane
// shares, on the borders between its panes. Mouse only.
//
// A drag previews through `onLive` and writes the desk once, on release
// (`onDone`), so a gesture is one desk write. A press that never travels
// is a click and writes nothing (the kit's `trackDrag`).

import { trackDrag } from "@nustackdev/ui-kit";
import type * as React from "react";
import { useState } from "react";
import { deskColumnHandle, deskShareHandle } from "../design";

/**
 * A drag handle: `axis` x for a column's width, y for a share. `onLive` gets
 * the distance from the press, px, `onDone` the last one, on release.
 */
function Handle({
	axis,
	className,
	onLive,
	onDone,
}: {
	axis: "x" | "y";
	className: string;
	onLive: (delta: number) => void;
	onDone: (delta: number) => void;
}) {
	const [dragging, setDragging] = useState(false);
	const down = (e: React.PointerEvent) => {
		let last = 0;
		const started = trackDrag(
			e,
			axis,
			(delta) => {
				last = delta;
				setDragging(true);
				onLive(delta);
			},
			() => {
				setDragging(false);
				onDone(last);
			},
		);
		if (started) e.stopPropagation();
	};
	return (
		// Mouse only: hidden from assistive tech, like the gap it sits in.
		<div
			aria-hidden
			className={className}
			data-dragging={dragging ? "" : undefined}
			onPointerDown={down}
		/>
	);
}

/** A column's width handle, in the gap on its right. */
export function ColumnHandle({
	last = false,
	onLive,
	onDone,
}: {
	/** The row's last column: the handle sits inside its right edge, not in a gap. */
	last?: boolean;
	onLive: (delta: number) => void;
	onDone: (delta: number) => void;
}) {
	return <Handle axis="x" className={deskColumnHandle(last)} onLive={onLive} onDone={onDone} />;
}

/** The share handle under a pane, in the gap to the next one. */
export function ShareHandle({
	onLive,
	onDone,
}: {
	onLive: (delta: number) => void;
	onDone: (delta: number) => void;
}) {
	return <Handle axis="y" className={deskShareHandle} onLive={onLive} onDone={onDone} />;
}
