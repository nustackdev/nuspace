import { describe, expect, it } from "vitest";
import { type MenuEntry, menuItems, menuMatch, menuSections, OTHER } from "./rank";

const SNIPPETS: MenuEntry[] = [
	{ name: "text", label: "Text", group: "Content", description: "Markdown a person edits." },
	{ name: "program", label: "Program", group: "Code" },
	{ name: "ticker", label: "Ticker", group: "Examples" },
	{ name: "lens", label: "Lens", group: "Debugging", description: "Browses the whole space." },
	{ name: "plane_lens", label: "Plane lens", group: "Debugging" },
	{ name: "loose", label: "Loose" },
];

const names = (items: MenuEntry[]) => items.map((i) => i.name);

describe("menuSections", () => {
	it("keeps registry order, groups by first appearance, ungrouped last", () => {
		const got = menuSections("", SNIPPETS);
		expect(got.map((s) => s.heading)).toEqual(["Content", "Code", "Examples", "Debugging", OTHER]);
		expect(names(got[3].items)).toEqual(["lens", "plane_lens"]);
	});

	it("draws no headings when nothing is grouped", () => {
		const got = menuSections("", [
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
		expect(names(menuItems("lens", SNIPPETS))).toEqual(["lens", "plane_lens"]);
		expect(names(menuItems("pl", SNIPPETS))).toEqual(["plane_lens"]);
		// A tie keeps the registry's order; a description's word comes last.
		expect(names(menuItems("p", SNIPPETS))).toEqual(["program", "plane_lens", "text"]);
		// A word's start beats a hit inside a word.
		expect(names(menuItems("le", SNIPPETS))).toEqual(["lens", "plane_lens"]);
	});

	it("matches the group and the description, after the label", () => {
		expect(names(menuItems("debug", SNIPPETS))).toEqual(["lens", "plane_lens"]);
		expect(names(menuItems("markdown", SNIPPETS))).toEqual(["text"]);
		expect(names(menuItems("t", SNIPPETS))[0]).toBe("text");
	});

	it("drops what misses", () => {
		expect(menuSections("zzz", SNIPPETS)).toEqual([]);
	});
});

describe("menuMatch", () => {
	it("lights a word's start before an earlier hit inside a word", () => {
		expect(menuMatch("le", "Plane lens")).toEqual([6, 8]);
		expect(menuMatch("pla", "Plane lens")).toEqual([0, 3]);
		expect(menuMatch("ane", "Plane lens")).toEqual([2, 5]);
		expect(menuMatch("x", "Plane lens")).toBeNull();
		expect(menuMatch("", "Plane lens")).toBeNull();
	});
});
