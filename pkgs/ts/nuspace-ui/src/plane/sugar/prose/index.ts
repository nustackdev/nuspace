// The prose set, v0: writing across prose cells as one document.
//
// Bound to the `prose` class, a protocol a cell declares on its spec: it
// draws exactly one kit document, and its value is markdown. Any cell that
// keeps the class gets this set, whoever wrote it and whatever spec made
// it; a heading or to-do variant that starts its text with `# ` is prose
// like any other. Which spec made a cell is never looked at.
//
// The set is its rule table (./rules.ts) and its hints (./hints.ts). It
// holds no state, attaches no listeners and queries no DOM: each handler
// below offers the intent to its table and answers whether a rule ran.

import type { Sugar } from "..";
import { NEW_CELL_HINT, WRITE_HINT } from "./hints";
import { answer, documentRules, inputRules, PROSE, titleRules } from "./rules";

export const prose: Sugar = {
	class: PROSE,
	onDocument: (cell, i, api) => answer(documentRules, { at: cell, i, api }),
	onInput: (after, i, api) => answer(inputRules, { at: after, i, api }),
	onTitle: (i, api) => answer(titleRules, { at: null, i, api }),
	inputHint: WRITE_HINT,
	documentHint: { blank: WRITE_HINT, tail: NEW_CELL_HINT },
};
