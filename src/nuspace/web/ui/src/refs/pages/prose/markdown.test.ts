// Round-trip tests.
//
// The contract the storage format rests on: markdown in, the same markdown
// out. Anything the island can produce has to survive a lap through the
// document model unchanged, or blocks churn on disk every time someone
// touches a page.
//
// Two properties are tested separately because they are different claims:
//
//   stable(md)  - md -> doc -> md is the identity. This is the one that
//                 matters for churn, and it must hold for everything the
//                 serializer itself emits.
//   settles(md) - one lap normalizes (source hard-wrapping reflows), and
//                 every lap after that is the identity. This is the honest
//                 claim for hand-written markdown that was not written by us.
//
// Run: npm test

import { describe, expect, it } from "vitest";
import { parseMarkdown, posForOffset, serializeMarkdown } from "./markdown";

function lap(md: string): string {
	return serializeMarkdown(parseMarkdown(md).doc);
}

/** md -> doc -> md is the identity. */
function stable(md: string): void {
	expect(lap(md)).toBe(md);
}

/** One lap normalizes; every lap after that is the identity. */
function settles(md: string): string {
	const once = lap(md);
	expect(lap(once)).toBe(once);
	return once;
}

describe("blocks round-trip", () => {
	it("keeps paragraphs", () => stable("hello world\n"));

	it("keeps blank-line separated paragraphs", () =>
		stable("first para\n\nsecond para\n"));

	it("keeps all three heading levels", () =>
		stable("# one\n\n## two\n\n### three\n"));

	it("keeps bullet lists", () => stable("- a\n- b\n- c\n"));

	it("keeps numbered lists", () => stable("1. a\n2. b\n3. c\n"));

	it("keeps a numbered list that does not start at one", () =>
		stable("3. a\n4. b\n"));

	it("keeps blockquotes", () => stable("> quoted line\n"));

	it("keeps multi-paragraph blockquotes", () => stable("> one\n>\n> two\n"));

	it("keeps rules", () => stable("before\n\n---\n\nafter\n"));

	it("keeps nested lists", () => stable("- a\n  - b\n  - c\n- d\n"));

	it("keeps a list mixed with a heading", () =>
		stable("# title\n\n- a\n- b\n\nbody\n"));

	it("empty source is empty", () => {
		expect(lap("")).toBe("");
		expect(parseMarkdown("").doc.childCount).toBe(1);
	});
});

describe("marks round-trip", () => {
	it("keeps bold", () => stable("a **bold** b\n"));
	it("keeps italic", () => stable("a *slanted* b\n"));
	it("keeps code", () => stable("a `code()` b\n"));
	it("keeps links", () => stable("see [docs](https://nustack.dev) now\n"));
	it("keeps nested marks", () => stable("a **bold *and* more** b\n"));
	it("keeps a link around a mark", () =>
		stable("[**bold link**](https://x.dev)\n"));
	it("keeps marks inside a list item", () => stable("- `/` opens the menu\n"));
	it("keeps marks inside a heading", () => stable("# a **loud** title\n"));
});

describe("escaping", () => {
	it("escapes what would otherwise re-parse as a mark", () => {
		const md = lap("a *not emphasis b\n");
		expect(lap(md)).toBe(md);
		expect(parseMarkdown(md).doc.textContent).toBe("a *not emphasis b");
	});

	it("round-trips text that looks like markup", () => {
		const source = "2 * 3 * 4 and _under_ and `tick` and [link](x)";
		// serialize the *document* whose text is that literal string
		const doc = parseMarkdown(source.replace(/([*_`[\]])/g, "\\$1")).doc;
		expect(doc.textContent).toBe(source);
		const md = serializeMarkdown(doc);
		expect(parseMarkdown(md).doc.textContent).toBe(source);
		stable(md);
	});

	it("escapes a leading block marker in body text", () => {
		const doc = parseMarkdown("\\# not a heading\n").doc;
		expect(doc.firstChild?.type.name).toBe("paragraph");
		expect(doc.textContent).toBe("# not a heading");
		stable(serializeMarkdown(doc));
	});

	it("escapes a bare backslash", () => {
		const doc = parseMarkdown("back\\\\slash\n").doc;
		expect(doc.textContent).toBe("back\\slash");
		stable(serializeMarkdown(doc));
	});
});

describe("normalization settles after one lap", () => {
	// This is what the seeded demo prose looks like: hard-wrapped source.
	const WRAPPED = `# Pages

This is a **prose island**. One block, many paragraphs. Type freely, select
across paragraphs, retype a range -- inside an island it behaves like a text
editor, because it is one.

Program blocks break the run. Across that boundary you get block-level
selection, which is the only thing that means anything there.

- \`/\` at the start of an empty line opens the block menu
- \`cmd+enter\` in a program block saves and restarts *that block only*
- \`esc\` leaves an editor and selects its block
`;

	it("reflows hard wrapping once, then holds", () => {
		const once = settles(WRAPPED);
		expect(once).toContain("# Pages\n");
		expect(once).toContain("**prose island**");
		expect(once).toContain("- `/` at the start of an empty line");
		// the wrap is gone, the content is not
		expect(once).not.toContain("select\nacross paragraphs");
		expect(parseMarkdown(once).doc.textContent).toContain(
			"across paragraphs, retype a range",
		);
	});

	it("holds for every prose block the demo seeds", () => {
		const blocks = [
			WRAPPED,
			"A program block is a python module with an `out` entry\npoint that returns a Nu term.\n",
			"The block below names a ref whose *path* is itself read from\na ref.\n",
			"Every block above is a live Nu program in its own supervised\nsection.\n",
		];
		for (const md of blocks) settles(md);
	});
});

describe("source offsets", () => {
	it("maps a merge seam to the join point", () => {
		const head = "one two";
		const parsed = parseMarkdown(`${head}\n\nthree\n`);
		const pos = posForOffset(parsed, head.length);
		// the caret lands at the end of the first paragraph's text
		expect(parsed.doc.textBetween(1, pos)).toBe("one two");
	});
});
