// The sidebar's two drop marks (./drag.ts has the language): the line on the
// gap a drop between rows lands in, and the hint a ringed row says at its
// end. Both say what the drop does as a glyph and a word.

import { cn } from "@nustackdev/ui-kit";
import { ArrowUpDown, Ban, Columns2, CornerDownRight, Pin, Rows2 } from "lucide-react";
import {
	sidebarDropGap,
	sidebarDropGapHint,
	sidebarDropGapIndent,
	sidebarDropHint,
	sidebarDropHintAt,
} from "../design";
import type { Hint, HintIcon } from "./drag";

const GLYPHS: Record<HintIcon, typeof Pin> = {
	pin: Pin,
	move: ArrowUpDown,
	side: Columns2,
	column: Columns2,
	stack: Rows2,
	inside: CornerDownRight,
	refused: Ban,
};

/** What a drop does, as its glyph and label. `at`: placed at a ringed row's end. */
export function DropHint({ hint, at = false }: { hint: Hint; at?: boolean }) {
	const Glyph = GLYPHS[hint.icon];
	return (
		<span
			aria-hidden="true"
			data-drop-hint=""
			className={cn(
				sidebarDropHint(hint.icon === "refused"),
				at && sidebarDropHintAt(hint.icon === "refused"),
			)}
		>
			<Glyph />
			{hint.label}
		</span>
	);
}

/**
 * The line on the gap above (`before`) or under (`after`) the row box it is
 * drawn in, from `depth`, saying `hint` on its end.
 */
export function DropLine({
	edge,
	depth,
	hint,
}: {
	edge: "before" | "after";
	depth: number;
	hint: Hint;
}) {
	return (
		<span
			aria-hidden="true"
			data-drop-line={edge}
			className={sidebarDropGap(edge)}
			style={sidebarDropGapIndent(depth)}
		>
			<span className={sidebarDropGapHint}>
				<DropHint hint={hint} />
			</span>
		</span>
	);
}
