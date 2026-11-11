// One column of a strip: its panes stacked top to bottom, 6px apart, each
// its share of the column's height. A pane is named by the plane it shows
// (its recent, else its original).
//
// Its width: the canvas's full width when it is the strip's only column,
// else its stored px (at least `MIN_WIDTH`), else two thirds of the canvas
// (`deskColumnWidth`).
// The window never changes a stored width.
//
// The column is `data-column`, each pane's place in it `data-share`. The
// column's width handle sits in the gap on its right, a share handle in each
// gap between its panes (./Resize.tsx). A drag starts from the width drawn,
// previews here and writes the desk once on release: `setWidth` with the
// px, `setShares` with the column's shares.
//
// The drop target's line (./drop.tsx) is drawn here too: on the edge or half
// of the pane it names.

import { type ReactNode, useRef, useState } from "react";
import { setShares, setWidth } from "../core/router";
import { deskColumn, deskColumnWidth, deskDropLine, deskShare } from "../design";
import { type Column as ColumnShape, MIN_WIDTH, shown } from "../desk/model";
import { useDropAim } from "./drop";
import { ColumnHandle, ShareHandle } from "./Resize";
import { GAP, resizeShares } from "./sizes";

/** A stored width as drawn: never under `MIN_WIDTH`. */
function drawn(width: number | undefined): number | undefined {
	return width === undefined ? undefined : Math.max(width, MIN_WIDTH);
}

export function Column({
	desk,
	item,
	column,
	only = false,
	last = false,
	pane,
}: {
	/** The desk and the strip the column is in. */
	desk: string;
	item: string;
	column: ColumnShape;
	/** The strip's only column: the full width, no width handle. */
	only?: boolean;
	/** The row's last column. */
	last?: boolean;
	/** Draw the pane showing a plane. */
	pane: (plane: string) => ReactNode;
}) {
	const aim = useDropAim();
	const ref = useRef<HTMLDivElement | null>(null);
	const [livePx, setLivePx] = useState<number | null>(null);
	const [liveShares, setLiveShares] = useState<number[] | null>(null);
	const planes = column.panes.map((p) => shown(p).plane);
	const first = planes[0] ?? "";
	const shares = liveShares ?? column.panes.map((p) => p.share);

	// The width drawn as a width drag starts, and the most it may get: the
	// canvas's width less the gap its handle sits in, so the handle stays on
	// screen.
	const from = useRef<{ px: number; most: number } | null>(null);
	const widthAt = (delta: number): number => {
		from.current ??= {
			px: ref.current?.offsetWidth ?? 0,
			most: (ref.current?.closest<HTMLElement>("[data-desk]")?.clientWidth ?? Infinity) - GAP,
		};
		const { px, most } = from.current;
		return Math.round(Math.max(MIN_WIDTH, Math.min(px + delta, most)));
	};
	const widthDone = (delta: number) => {
		const next = widthAt(delta);
		from.current = null;
		setLivePx(null);
		if (next !== column.width) setWidth(desk, item, first, next);
	};

	// The shares and the column's height without its gaps (what the shares
	// divide), taken as a share drag starts.
	const start = useRef<{ from: number[]; room: number } | null>(null);
	const shareAt = (index: number, delta: number): number[] => {
		start.current ??= {
			from: column.panes.map((p) => p.share),
			room: (ref.current?.clientHeight ?? 0) - GAP * (column.panes.length - 1),
		};
		return resizeShares(start.current.from, index, delta, start.current.room);
	};
	const shareDone = (index: number, delta: number) => {
		const next = shareAt(index, delta);
		const from = start.current?.from ?? [];
		start.current = null;
		setLiveShares(null);
		if (next.some((s, i) => Math.abs(s - from[i]) > 1e-6)) setShares(desk, item, first, next);
	};

	return (
		<div
			ref={ref}
			className={deskColumn}
			style={{ width: livePx ?? deskColumnWidth(only ? null : drawn(column.width)) }}
			data-column=""
		>
			{planes.map((plane, i) => (
				<div key={plane} className={deskShare} style={{ flexGrow: shares[i] }} data-share="">
					{pane(plane)}
					{aim?.kind === "strip" && "plane" in aim.drop && aim.drop.plane === plane ? (
						<span aria-hidden className={deskDropLine(aim.drop.edge)} />
					) : null}
					{i < planes.length - 1 ? (
						<ShareHandle
							onLive={(delta) => setLiveShares(shareAt(i, delta))}
							onDone={(delta) => shareDone(i, delta)}
						/>
					) : null}
				</div>
			))}
			{only ? null : (
				<ColumnHandle
					last={last}
					onLive={(delta) => setLivePx(widthAt(delta))}
					onDone={widthDone}
				/>
			)}
		</div>
	);
}
