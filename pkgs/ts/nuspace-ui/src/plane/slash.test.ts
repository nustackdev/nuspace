import { describe, expect, it } from "vitest";
import { OTHER, slashItems, slashMatch, slashSections } from "./slash";
import type { SlashSnippet } from "./types";

const SNIPPETS: SlashSnippet[] = [
	{ name: "text", label: "Text", group: "Content", description: "Markdown a person edits." },
	{ name: "program", label: "Program", group: "Code" },
	{ name: "ticker", label: "Ticker", group: "Examples" },
	{ name: "lens", label: "Lens", group: "Debugging", description: "Browses the whole space." },
	{ name: "plane_lens", label: "Plane lens", group: "Debugging" },
	{ name: "loose", label: "Loose" },
];

const names = (items: SlashSnippet[]) => items.map((i) => i.name);

describe("slashSections", () => {
	it("keeps registry order, groups by first appearance, ungrouped last", () => {
		const got = slashSections("", SNIPPETS);
		expect(got.map((s) => s.heading)).toEqual(["Content", "Code", "Examples", "Debugging", OTHER]);
		expect(names(got[3].items)).toEqual(["lens", "plane_lens"]);
	});

	it("draws no headings when nothing is grouped", () => {
		const got = slashSections("", [
			{ name: "a", label: "A" },
			{ name: "b", label: "B" },
		]);
		expect(got).toEqual([
			{
				heading: null,
				items: [
					{ name: "a", label: "A" },
					{ name: "b", label: "B" },
				],
			},
		]);
	});

	it("puts the best match first, its group with it", () => {
		expect(names(slashItems("lens", SNIPPETS))).toEqual(["lens", "plane_lens"]);
		expect(names(slashItems("pl", SNIPPETS))).toEqual(["plane_lens"]);
		// A tie keeps the registry's order; a description's word comes last.
		expect(names(slashItems("p", SNIPPETS))).toEqual(["program", "plane_lens", "text"]);
		// A word's start beats a hit inside a word.
		expect(names(slashItems("le", SNIPPETS))).toEqual(["lens", "plane_lens"]);
	});

	it("matches the group and the description, after the label", () => {
		expect(names(slashItems("debug", SNIPPETS))).toEqual(["lens", "plane_lens"]);
		expect(names(slashItems("markdown", SNIPPETS))).toEqual(["text"]);
		expect(names(slashItems("t", SNIPPETS))[0]).toBe("text");
	});

	it("drops what misses", () => {
		expect(slashSections("zzz", SNIPPETS)).toEqual([]);
	});
});

describe("slashMatch", () => {
	it("lights a word's start before an earlier hit inside a word", () => {
		expect(slashMatch("le", "Plane lens")).toEqual([6, 8]);
		expect(slashMatch("pla", "Plane lens")).toEqual([0, 3]);
		expect(slashMatch("ane", "Plane lens")).toEqual([2, 5]);
		expect(slashMatch("x", "Plane lens")).toBeNull();
		expect(slashMatch("", "Plane lens")).toBeNull();
	});
});
