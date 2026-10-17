import { describe, expect, it } from "vitest";
import { type MenuEntry, menuItems, menuMatch, menuSections, OTHER } from "./rank";

const SNIPPETS: MenuEntry[] = [
	{
		name: "nuverse.text",
		label: "Text",
		group: "Content",
		description: "Markdown a person edits.",
	},
	{ name: "nuverse.program", label: "Program", group: "Code" },
	{ name: "nuverse.ticker", label: "Ticker", group: "Examples" },
	{
		name: "nuverse.lens",
		label: "Lens",
		group: "Debugging",
		description: "Browses the whole space.",
	},
	{ name: "nuverse.plane_lens", label: "Plane lens", group: "Debugging" },
	{ name: "loose", label: "Loose" },
];

const names = (items: MenuEntry[]) => items.map((i) => i.name);

describe("menuSections", () => {
	it("keeps registry order, groups by first appearance, ungrouped last", () => {
		const got = menuSections("", SNIPPETS);
		expect(got.map((s) => s.heading)).toEqual(["Content", "Code", "Examples", "Debugging", OTHER]);
		expect(names(got[3].items)).toEqual(["nuverse.lens", "nuverse.plane_lens"]);
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
		expect(names(menuItems("lens", SNIPPETS))).toEqual(["nuverse.lens", "nuverse.plane_lens"]);
		expect(names(menuItems("pl", SNIPPETS))).toEqual(["nuverse.plane_lens"]);
		// A tie keeps the registry's order; a description's word comes last.
		expect(names(menuItems("p", SNIPPETS))).toEqual([
			"nuverse.program",
			"nuverse.plane_lens",
			"nuverse.text",
		]);
		// A word's start beats a hit inside a word.
		expect(names(menuItems("le", SNIPPETS))).toEqual(["nuverse.lens", "nuverse.plane_lens"]);
	});

	it("matches the group and the description, after the label", () => {
		expect(names(menuItems("debug", SNIPPETS))).toEqual(["nuverse.lens", "nuverse.plane_lens"]);
		expect(names(menuItems("markdown", SNIPPETS))).toEqual(["nuverse.text"]);
		expect(names(menuItems("t", SNIPPETS))[0]).toBe("nuverse.text");
	});

	it("matches a name past its package only", () => {
		expect(names(menuItems("plane_", SNIPPETS))).toEqual(["nuverse.plane_lens"]);
		expect(menuSections("nuverse", SNIPPETS)).toEqual([]);
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
