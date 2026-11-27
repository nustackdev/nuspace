// A strip row's two parts: its lead, the planes' icons as one composite in
// the 20px box every row's icon takes, and its label, the planes' titles on
// one line with a +N of those it cannot show in full.
//
// The arrangement and the count are pure (./model.ts `compositeOf`,
// `hiddenTitles`); this draws them, and measures the label for the count.

import { useLayoutEffect, useRef, useState } from "react";
import {
	mobileComposite,
	mobileCompositeCell,
	mobileCompositeMore,
	mobileStripLabel,
	mobileStripMore,
	mobileStripTitles,
} from "../../design";
import { PlaneIcon } from "../../icon/PlaneIcon";
import { planeIcon } from "../../icon/parse";
import { compositeOf, hiddenTitles, ICON_BOX, TITLE_SEP } from "./model";

/** A strip's planes' icons, in pager order, as one icon the size of any row's. */
export function StripIcon({ icons }: { icons: string[] }) {
	// A strip of one pane: its icon, as a plane row draws it.
	if (icons.length === 1) return <PlaneIcon icon={planeIcon(icons[0])} />;
	const { cells, shown, more } = compositeOf(icons.length);
	return (
		<span
			data-composite={icons.length}
			className={mobileComposite}
			style={{ width: ICON_BOX, height: ICON_BOX }}
		>
			{cells.map((c, i) => (
				<span
					// biome-ignore lint/suspicious/noArrayIndexKey: cells are positions, not things
					key={i}
					className={mobileCompositeCell}
					style={{ left: c.x, top: c.y, width: c.w, height: c.h }}
				>
					{i < shown ? (
						<PlaneIcon icon={planeIcon(icons[i])} />
					) : (
						<small className={mobileCompositeMore}>+{more}</small>
					)}
				</span>
			))}
		</span>
	);
}

/** The gap before the +N, in px: the `pl-1` of `mobileStripMore`. */
const MORE_GAP = 4;

/**
 * A strip's titles, in pager order, on one line: truncating with an
 * ellipsis, then "+N" for the titles not fully shown, never cut. N is
 * measured: where each title ends on the line against the room the label
 * has, again whenever that room changes.
 */
export function StripLabel({ titles }: { titles: string[] }) {
	const box = useRef<HTMLSpanElement | null>(null);
	const line = useRef<HTMLSpanElement | null>(null);
	const [hidden, setHidden] = useState(0);
	const key = titles.join("\n");

	// biome-ignore lint/correctness/useExhaustiveDependencies: the titles are compared by value.
	useLayoutEffect(() => {
		const outer = box.current;
		const text = line.current;
		if (!outer || !text) return;
		let alive = true;
		const measure = () => {
			if (!alive) return;
			const left = text.getBoundingClientRect().left;
			const ends = Array.from(
				text.querySelectorAll("[data-title]"),
				(t) => t.getBoundingClientRect().right - left,
			);
			const width = textWidth(text);
			setHidden(
				hiddenTitles(ends, outer.clientWidth, width("…"), (n) => width(`+${n}`) + MORE_GAP),
			);
		};
		measure();
		const watch = new ResizeObserver(measure);
		watch.observe(outer);
		// A late web font moves every end.
		document.fonts?.ready.then(measure);
		return () => {
			alive = false;
			watch.disconnect();
		};
	}, [key]);

	return (
		<span ref={box} className={mobileStripLabel}>
			<span ref={line} className={mobileStripTitles}>
				{titles.map((t, i) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: two panes can show one title
					<span key={i}>
						{i ? TITLE_SEP : null}
						<span data-title="">{t}</span>
					</span>
				))}
			</span>
			{hidden ? (
				<span data-more="" className={mobileStripMore}>
					+{hidden}
				</span>
			) : null}
		</span>
	);
}

let canvas: HTMLCanvasElement | null = null;

/** Measures text in element `el`'s font, letter spacing included. */
function textWidth(el: HTMLElement): (text: string) => number {
	canvas ??= document.createElement("canvas");
	const ctx = canvas.getContext("2d");
	if (!ctx) return () => 0;
	const style = getComputedStyle(el);
	ctx.font = style.font;
	if ("letterSpacing" in ctx) ctx.letterSpacing = style.letterSpacing;
	return (text) => ctx.measureText(text).width;
}
