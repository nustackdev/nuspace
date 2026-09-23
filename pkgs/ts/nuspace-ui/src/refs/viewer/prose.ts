// The document dialect.
//
// nuspace does not own a prose engine any more. The schema, the input rules,
// the markdown parser/serializer and the editor all live in ui-kit, which is
// where they belong: they are how a `ProseRef` renders, and `ProseRef` is a
// nu Ref. What nuspace still owns is the *look* -- a document surface has a
// typographic rhythm and the kit's own `Prose` container has a different one
// -- so the schema is built here, from `../../design` recipes, and handed to
// the kit editor.
//
// `createMarkdown` comes off the kit index alongside the schema. nuspace
// needs it, not just the editor: splitting a block at the caret means
// serializing a *range* of the document to markdown, and merging up means
// serializing the whole document to hand to the block above. Neither is
// expressible with the editor alone -- it only ever hands out the full
// document, and only at a commit.

import { createMarkdown, createProseSchema } from "@nustackdev/ui-kit";
import {
	docBlockquote,
	docBulletList,
	docEm,
	docHeading,
	docInlineCode,
	docLink,
	docListItem,
	docOrderedList,
	docParagraph,
	docRule,
	docStrong,
} from "../../design";

/**
 * The document's dialect: paragraphs, three heading levels, two list
 * flavours, a quote, a rule, four inline marks.
 *
 * That ceiling is the "how much did we borrow" line, and the kit draws it in
 * the same place. There is no node for a program block, a section or a page,
 * so the engine cannot represent the document nuspace actually owns and
 * cannot grow opinions about ordering, lifecycle or structure above the
 * block. Nu owns those.
 *
 * Every recipe below is the same one the reader sees, because `toDOM` gets
 * it directly. That is what removes the old leaf's mode-swap layout shift:
 * there is no second rendering to disagree with.
 */
export const proseDialect = createProseSchema({
	paragraph: docParagraph,
	heading: docHeading,
	blockquote: docBlockquote,
	bulletList: docBulletList,
	orderedList: docOrderedList,
	listItem: docListItem,
	rule: docRule,
	strong: docStrong,
	em: docEm,
	code: docInlineCode,
	link: docLink,
});

export const { nodeType, markType } = proseDialect;

/** Parser + serializer for the dialect above. Bound once; both are pure. */
export const markdown = createMarkdown(proseDialect);

export const { parseMarkdown, serializeMarkdown, serializeRange, posForOffset } = markdown;

export type { Parsed } from "@nustackdev/ui-kit";
