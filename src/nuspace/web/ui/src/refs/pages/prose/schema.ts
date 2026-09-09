// The prose island's document schema.
//
// This is where the "how much did we borrow" line is drawn, and it is drawn
// on purpose. ProseMirror is a document engine; a schema is how you tell it
// what a document is allowed to be. Ours says: paragraphs, three heading
// levels, two list flavours, a quote, a rule, and four inline marks. That is
// an *island* - a few paragraphs of prose - and nothing wider.
//
// What is deliberately absent is the whole reason this is safe. There is no
// node for a program block, no node for a section, no node for a page. The
// engine cannot represent the document nuspace actually owns, so it cannot
// grow opinions about ordering, lifecycle or structure above the island. Nu
// owns those. The island owns its own contents and nothing else.
//
// Every `toDOM` reaches into ../../design. That is what removes the old
// leaf's layout shift: there is no separate "rendered" pass to disagree with
// the editing pass, because a heading is styled by the same recipe whether
// the caret is in it or not.

import { type MarkSpec, type NodeSpec, Schema } from "prosemirror-model";
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
} from "../../../design";

const nodes: Record<string, NodeSpec> = {
	doc: { content: "block+" },

	paragraph: {
		content: "inline*",
		group: "block",
		parseDOM: [{ tag: "p" }],
		toDOM: () => ["p", { class: docParagraph }, 0],
	},

	heading: {
		attrs: { level: { default: 1 } },
		content: "inline*",
		group: "block",
		defining: true,
		parseDOM: [
			{ tag: "h1", attrs: { level: 1 } },
			{ tag: "h2", attrs: { level: 2 } },
			{ tag: "h3", attrs: { level: 3 } },
			// Deeper headings exist in pasted HTML. Markdown only ever stores
			// three, so they fold down rather than round-trip to nothing.
			{ tag: "h4", attrs: { level: 3 } },
			{ tag: "h5", attrs: { level: 3 } },
			{ tag: "h6", attrs: { level: 3 } },
		],
		toDOM: (node) => [
			`h${node.attrs.level}`,
			{ class: docHeading(node.attrs.level as number) },
			0,
		],
	},

	blockquote: {
		content: "block+",
		group: "block",
		defining: true,
		parseDOM: [{ tag: "blockquote" }],
		toDOM: () => ["blockquote", { class: docBlockquote }, 0],
	},

	bullet_list: {
		content: "list_item+",
		group: "block",
		parseDOM: [{ tag: "ul" }],
		toDOM: () => ["ul", { class: docBulletList }, 0],
	},

	ordered_list: {
		attrs: { order: { default: 1 } },
		content: "list_item+",
		group: "block",
		parseDOM: [
			{
				tag: "ol",
				getAttrs: (dom) => ({
					order: Number((dom as HTMLElement).getAttribute("start")) || 1,
				}),
			},
		],
		toDOM: (node) => {
			const order = node.attrs.order as number;
			const attrs: Record<string, string> = { class: docOrderedList };
			if (order !== 1) attrs.start = String(order);
			return ["ol", attrs, 0];
		},
	},

	list_item: {
		// `paragraph block*` is what makes splitListItem / sinkListItem behave.
		content: "paragraph block*",
		defining: true,
		parseDOM: [{ tag: "li" }],
		toDOM: () => ["li", { class: docListItem }, 0],
	},

	horizontal_rule: {
		group: "block",
		parseDOM: [{ tag: "hr" }],
		toDOM: () => ["hr", { class: docRule }],
	},

	text: { group: "inline" },
};

const marks: Record<string, MarkSpec> = {
	// Order matters: it is the order marks nest in when serialized, so link
	// wraps emphasis rather than the other way round.
	link: {
		attrs: { href: { default: "" } },
		inclusive: false,
		parseDOM: [
			{
				tag: "a[href]",
				getAttrs: (dom) => ({
					href: (dom as HTMLElement).getAttribute("href") ?? "",
				}),
			},
		],
		toDOM: (mark) => [
			"a",
			{
				href: String(mark.attrs.href),
				class: docLink,
				target: "_blank",
				rel: "noreferrer",
			},
			0,
		],
	},

	strong: {
		parseDOM: [
			{ tag: "strong" },
			{ tag: "b" },
			{ style: "font-weight=bold" },
			{ style: "font-weight=700" },
		],
		toDOM: () => ["strong", { class: docStrong }, 0],
	},

	em: {
		parseDOM: [{ tag: "em" }, { tag: "i" }, { style: "font-style=italic" }],
		toDOM: () => ["em", { class: docEm }, 0],
	},

	// Code excludes everything else, the way markdown's backticks do: the
	// span between them is literal, so bold-inside-code has no serialization.
	code: {
		excludes: "_",
		parseDOM: [{ tag: "code" }],
		toDOM: () => ["code", { class: docInlineCode }, 0],
	},
};

export const proseSchema = new Schema({ nodes, marks });

export const nodeType = {
	paragraph: proseSchema.nodes.paragraph,
	heading: proseSchema.nodes.heading,
	blockquote: proseSchema.nodes.blockquote,
	bulletList: proseSchema.nodes.bullet_list,
	orderedList: proseSchema.nodes.ordered_list,
	listItem: proseSchema.nodes.list_item,
	rule: proseSchema.nodes.horizontal_rule,
};

export const markType = {
	strong: proseSchema.marks.strong,
	em: proseSchema.marks.em,
	code: proseSchema.marks.code,
	link: proseSchema.marks.link,
};
