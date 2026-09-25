// A plane on the way: its title row and a few cells as kit `Skeleton` bars,
// on the grid the real plane uses. One component for both waits, the boot
// (before the viewer is on the tree) and a plane switch (before its
// `set_plane` lands), so the two look the same.
//
// It holds its fire for `SKELETON_DELAY_MS`, so a plane that lands fast
// never flashes it. See ../core/delay.ts.

import { Skeleton } from "@nustackdev/ui-kit";
import { useSkeleton } from "../core/delay";
import {
	docColumn,
	docRow,
	docSkeleton,
	docSkeletonCell,
	docSkeletonTitle,
	docTitleHead,
	docTitleRow,
} from "../design";

/** Line widths per placeholder cell: a paragraph, a short line, a paragraph. */
const CELLS = [["w-full", "w-11/12", "w-2/3"], ["w-1/3"], ["w-full", "w-3/4"]];

export function ViewerSkeleton() {
	const shown = useSkeleton();
	return (
		<div className={docSkeleton} aria-busy="true" data-viewer-skeleton="">
			{shown ? (
				<>
					<header className={docTitleHead()}>
						<div className={docTitleRow()}>
							<Skeleton className={docSkeletonTitle} />
						</div>
					</header>
					<div className={docColumn()}>
						{CELLS.map((lines, i) => (
							// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
							<div key={i} className={docRow}>
								<div className={docSkeletonCell}>
									{lines.map((width, j) => (
										// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
										<Skeleton key={j} shape="text" className={width} />
									))}
								</div>
							</div>
						))}
					</div>
				</>
			) : null}
		</div>
	);
}
