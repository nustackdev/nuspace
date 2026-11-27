// The desk screen: one desk item, its panes as pages you swipe through, in
// reading order (column by column, top to bottom). The layout stays as saved:
// the phone only reads it. Switching item goes through the sidebar.
//
// On top the header every screen wears (../Header.tsx) names the desk,
// dimmed, and the pane on screen, with the pager's ‹ n/m › at its end: the
// buttons turn the page as a swipe does, and the counter follows a swipe as
// it moves. A plane item is one page: no pager. Last the ⋯, the facts of the
// pane on screen (../plane/PlaneInfoSheet.tsx).
//
// The pager is the browser's own sideways scroll with snapping, and each page
// is a plane screen (../plane/MobilePlane.tsx) scrolling up and down inside
// itself. The browser locks a drag to the axis it starts on, so reading down
// a pane never turns the page and a swipe never scrolls the pane.
//
// The page on screen is the item's focused pane, as a click on a pane is on
// desktop: a swipe that settles focuses its pane through the router, so the
// + and the tab title follow it, and a focus that moves from elsewhere (a link
// followed inside a pane, a pane asked for again) brings its page on screen.
// Only the page on screen answers the +.

import type { Path } from "@nustackdev/ui-core";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { usePlaneLooks } from "../../core/looks";
import { focusPane, onReveal, type Route } from "../../core/router";
import {
	mobileDesk,
	mobileDeskPage,
	mobileDeskPager,
	mobileDeskTitle,
	mobileDeskTitleDesk,
	mobileDeskTitleDot,
	mobileDeskTitlePane,
} from "../../design";
import { panePath, usePaneHead } from "../../pane/state";
import type { CellSpec } from "../../plane/types";
import { HeaderButton, HeaderCount, MobileHeader } from "../Header";
import { InfoButton, MobilePlane } from "../plane/MobilePlane";
import { PlaneInfoSheet } from "../plane/PlaneInfoSheet";
import { pageAt, pageCount, pageOf, pagesOf, stepPage } from "./model";

/** How long a scroll stays still before its page counts as settled, where `scrollend` is missing. */
const SETTLE_MS = 120;

export function MobileDesk({
	viewerPath,
	route,
	cellSpecs,
}: {
	viewerPath: Path;
	route: Extract<Route, { kind: "item" }>;
	cellSpecs: CellSpec[];
}) {
	const { desk, item, focus } = route;
	const pages = useMemo(() => pagesOf(item), [item]);
	const planes = useMemo(() => pages.map((p) => p.plane), [pages]);
	const focused = pageOf(pages, focus);

	// The page the scroll stands on now, live while a swipe moves.
	const [index, setIndex] = useState(focused);
	const pager = useRef<HTMLDivElement | null>(null);
	const drawn = useRef(false);

	const scrollTo = useCallback((at: number, smooth: boolean) => {
		const el = pager.current;
		if (!el) return;
		const left = at * el.clientWidth;
		if (Math.abs(el.scrollLeft - left) < 1) return;
		el.scrollTo({ left, behavior: smooth ? "smooth" : "instant" });
	}, []);

	// The focused pane on screen: at once the first time, then sliding over.
	useLayoutEffect(() => {
		setIndex(focused);
		scrollTo(focused, drawn.current);
		drawn.current = true;
	}, [focused, scrollTo]);

	// A pane asked for again while it is shown: its page comes on screen.
	useEffect(
		() =>
			onReveal((plane) => {
				const at = planes.indexOf(plane);
				if (at >= 0) scrollTo(at, true);
			}),
		[planes, scrollTo],
	);

	// The swipe: the counter follows it, and where it settles is focused.
	useEffect(() => {
		const el = pager.current;
		if (!el) return;
		let timer = 0;
		const at = () => pageAt(el.scrollLeft, el.clientWidth, planes.length);
		const settle = () => {
			window.clearTimeout(timer);
			const plane = planes[at()];
			if (plane) focusPane(desk, item.id, plane);
		};
		const onScroll = () => {
			setIndex(at());
			window.clearTimeout(timer);
			timer = window.setTimeout(settle, SETTLE_MS);
		};
		el.addEventListener("scroll", onScroll, { passive: true });
		el.addEventListener("scrollend", settle);
		return () => {
			window.clearTimeout(timer);
			el.removeEventListener("scroll", onScroll);
			el.removeEventListener("scrollend", settle);
		};
	}, [desk, item.id, planes]);

	// A turned phone: the page it was on stays on screen.
	useEffect(() => {
		const el = pager.current;
		if (!el) return;
		let width = el.clientWidth;
		const kept = new ResizeObserver(() => {
			// Only a new width moves pages; the browser bars coming and going change the height.
			if (el.clientWidth === width) return;
			width = el.clientWidth;
			scrollTo(pageOf(pages, focus), false);
		});
		kept.observe(el);
		return () => kept.disconnect();
	}, [pages, focus, scrollTo]);

	const shown = Math.min(index, pages.length - 1);
	// The pane whose facts are open, held through the sheet's close.
	const [info, setInfo] = useState<string | null>(null);
	const [infoPlane, setInfoPlane] = useState("");
	useEffect(() => {
		if (info) setInfoPlane(info);
	}, [info]);
	const count = pageCount(shown, pages.length);

	return (
		<section className={mobileDesk} aria-label={route.name} data-desk-screen="">
			<DeskHeader
				viewerPath={viewerPath}
				name={route.name}
				plane={planes[shown] ?? ""}
				count={count}
				onStep={(by) => scrollTo(stepPage(shown, by, pages.length), true)}
				onInfo={() => setInfo(planes[shown] ?? null)}
				first={shown <= 0}
				last={shown >= pages.length - 1}
			/>
			<div ref={pager} className={mobileDeskPager} data-desk-pager="">
				{pages.map((page, i) => (
					<div key={page.plane} className={mobileDeskPage} data-desk-page={i}>
						<MobilePlane
							viewerPath={viewerPath}
							planeId={page.plane}
							cellSpecs={cellSpecs}
							active={page.plane === focus}
							titled={false}
						/>
					</div>
				))}
			</div>
			{infoPlane ? (
				<PlaneInfoSheet
					viewerPath={viewerPath}
					planeId={infoPlane}
					open={info !== null}
					onClose={() => setInfo(null)}
				/>
			) : null}
		</section>
	);
}

const NO_PATH: string[] = [];

/**
 * The header: the desk's name, dimmed, then the title of the pane on screen,
 * the pager, ‹ n/m ›, its buttons dimmed at the ends, and the ⋯ of the
 * pane on screen.
 */
function DeskHeader({
	viewerPath,
	name,
	plane,
	count,
	onStep,
	onInfo,
	first,
	last,
}: {
	viewerPath: Path;
	name: string;
	plane: string;
	count: string | null;
	onStep: (by: -1 | 1) => void;
	onInfo: () => void;
	first: boolean;
	last: boolean;
}) {
	const head = usePaneHead(plane ? panePath(viewerPath, plane) : NO_PATH);
	const looks = usePlaneLooks(useMemo(() => (plane ? [plane] : []), [plane]));
	const title = head?.title || looks[plane]?.title || "";
	return (
		<MobileHeader
			label={title ? `${name} · ${title}` : name}
			title={
				<span className={mobileDeskTitle}>
					<span className={mobileDeskTitleDesk}>{name}</span>
					{title ? (
						<>
							<span aria-hidden="true" className={mobileDeskTitleDot}>
								·
							</span>
							<span className={mobileDeskTitlePane} data-desk-title="">
								{title}
							</span>
						</>
					) : null}
				</span>
			}
			actions={
				<>
					{count ? (
						<>
							<HeaderButton
								label="Previous pane"
								data-desk-step="prev"
								disabled={first}
								onClick={() => onStep(-1)}
							>
								<ChevronLeft />
							</HeaderButton>
							<HeaderCount>
								<span data-desk-count="">{count}</span>
							</HeaderCount>
							<HeaderButton
								label="Next pane"
								data-desk-step="next"
								disabled={last}
								onClick={() => onStep(1)}
							>
								<ChevronRight />
							</HeaderButton>
						</>
					) : null}
					{head ? <InfoButton onClick={onInfo} /> : null}
				</>
			}
		/>
	);
}
