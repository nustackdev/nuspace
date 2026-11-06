// The sugar layer: sets of rules bound to a cell class, on top of a plane
// that works without any of them.
//
// The core plane (..) is kind-blind: cells, order, classes, an input line
// and `/` to pick what to insert. A sugar set is how writing in it gets
// easier for cells that keep one class: it hears what the person tried to
// do (an intent: a document's edge, a key on the input line or the title)
// and answers true when it acted, through the plane API (../api.ts) and the
// cell's document handle. It holds no state, attaches no listeners and
// queries no DOM. False, and the core does its own default.
//
// Which set hears what is the core's routing (../intents.ts): a document's
// intents go to the sets bound to one of its cell's classes, the input line
// and the title to the sets whose class has a default spec installed. A set
// looks at classes only; which spec made a cell is never its business.
//
// A plain shape and a list, built for the sets we have and not for ones we
// do not: no lifecycle, no priorities, no composition between sets. This
// file is the one place a set is named.

import type { DocIntent } from "@nustackdev/ui-kit";
import type { PlaneApi } from "../api";
import type { InputIntent, TitleIntent } from "../intents";
import { prose } from "./prose";

export interface Sugar {
	/** The class it is bound to: "prose". */
	class: string;
	/** An intent from the document of `cell`, a cell that keeps the class. */
	onDocument?(cell: string, i: DocIntent, api: PlaneApi): boolean;
	/** Typed text or Enter on the input line after `after` (null: the top). */
	onInput?(after: string | null, i: InputIntent, api: PlaneApi): boolean;
	/** Enter in the title, or leaving it down or right at its end. */
	onTitle?(i: TitleIntent, api: PlaneApi): boolean;
	/** The input line's placeholder while this set has it. */
	inputHint?: string;
	/**
	 * What the document of a cell in the class draws while it has the caret
	 * (the kit's `DocumentHandle.hint`): on it blank, and on the empty last
	 * line of one with text. The core sets them as the caret arrives and
	 * clears them as it leaves; a set only says what they read.
	 */
	documentHint?: { blank?: string; tail?: string };
}

/** The sets, in the order they are offered an intent. */
export const sugars: Sugar[] = [prose];
