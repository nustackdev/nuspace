// Typing rules and the empty-block hint.
//
// The input rules are the reason this reads as markdown even though nothing
// on screen is markdown: `# ` becomes a heading as you finish typing the
// space, `- ` starts a list, `**bold**` closes into a mark. The muscle memory
// people already have keeps working, and the source they would have typed is
// still exactly what gets stored.
//
// Deliberately no rule fires on anything the serializer cannot emit. The
// dialect is closed: what you can type, the slash menu can produce, and
// markdown.ts can write back.

import {
	InputRule,
	inputRules,
	textblockTypeInputRule,
	wrappingInputRule,
} from "prosemirror-inputrules";
import type { MarkType } from "prosemirror-model";
import { type EditorState, Plugin } from "prosemirror-state";
import { Decoration, DecorationSet } from "prosemirror-view";
import { markType, nodeType, proseSchema } from "./schema";

/**
 * `**text**` -> strong, on the closing delimiter. The lookbehind is what
 * keeps `***` from firing the em rule inside a strong run.
 */
function markInputRule(re: RegExp, type: MarkType): InputRule {
	return new InputRule(re, (state, match, start, end) => {
		const inner = match[1];
		if (!inner) return null;
		const existing = state.doc.resolve(start).marks();
		const tr = state.tr.replaceWith(
			start,
			end,
			proseSchema.text(inner, type.create().addToSet(existing)),
		);
		// Otherwise the mark stays armed and the next character joins it.
		return tr.removeStoredMark(type);
	});
}

export function proseInputRules(): Plugin {
	return inputRules({
		rules: [
			// blocks
			textblockTypeInputRule(/^(#{1,3})[ \t]$/, nodeType.heading, (m) => ({
				level: m[1].length,
			})),
			wrappingInputRule(/^\s*([-+*])[ \t]$/, nodeType.bulletList),
			wrappingInputRule(
				/^(\d+)[.)][ \t]$/,
				nodeType.orderedList,
				(m) => ({ order: Number(m[1]) }),
				// Only continue an existing list when the numbers line up.
				(m, node) => node.childCount + (node.attrs.order as number) === +m[1],
			),
			wrappingInputRule(/^\s*>[ \t]$/, nodeType.blockquote),
			new InputRule(/^(?:---|\*\*\*|___)$/, (state, _m, start, end) =>
				state.tr.replaceRangeWith(start, end, nodeType.rule.create()),
			),
			// marks
			markInputRule(
				/(?<!\*)\*\*([^*\s](?:[^*]*[^*\s])?)\*\*$/,
				markType.strong,
			),
			markInputRule(/(?<![*\w])\*([^*\s](?:[^*]*[^*\s])?)\*$/, markType.em),
			markInputRule(/(?<!`)`([^`]+)`$/, markType.code),
		],
	});
}

/* ============================== placeholder ============================== */

function isBlank(state: EditorState): boolean {
	const doc = state.doc;
	if (doc.childCount !== 1) return false;
	const first = doc.firstChild;
	return (
		first != null &&
		first.type === nodeType.paragraph &&
		first.content.size === 0
	);
}

/**
 * The hint on an empty island. A decoration, not a document node: it can
 * never be selected, copied, or serialized, which is the whole reason not to
 * do this with placeholder text in the model.
 */
export function placeholder(text: string): Plugin {
	return new Plugin({
		props: {
			decorations(state) {
				if (!isBlank(state)) return null;
				return DecorationSet.create(state.doc, [
					Decoration.node(0, state.doc.firstChild?.nodeSize ?? 2, {
						"data-nu-placeholder": text,
					}),
				]);
			},
		},
	});
}
