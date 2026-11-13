import { describe, expect, it } from "vitest";
import {
	type MenuEntry,
	menuItems,
	menuMatch,
	menuPackages,
	menuRows,
	menuSections,
	OTHER,
} from "./rank";

const CELL_SPECS: MenuEntry[] = [
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
		const got = menuSections("", CELL_SPECS);
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
		expect(names(menuItems("lens", CELL_SPECS))).toEqual(["nuverse.lens", "nuverse.plane_lens"]);
		expect(names(menuItems("pl", CELL_SPECS))).toEqual(["nuverse.plane_lens"]);
		// A tie keeps the registry's order; a description's word comes last.
		expect(names(menuItems("p", CELL_SPECS))).toEqual([
			"nuverse.program",
			"nuverse.plane_lens",
			"nuverse.text",
		]);
		// A word's start beats a hit inside a word.
		expect(names(menuItems("le", CELL_SPECS))).toEqual(["nuverse.lens", "nuverse.plane_lens"]);
	});

	it("matches the group and the description, after the label", () => {
		expect(names(menuItems("debug", CELL_SPECS))).toEqual(["nuverse.lens", "nuverse.plane_lens"]);
		expect(names(menuItems("markdown", CELL_SPECS))).toEqual(["nuverse.text"]);
		expect(names(menuItems("t", CELL_SPECS))[0]).toBe("nuverse.text");
	});

	it("matches a name past its package only", () => {
		expect(names(menuItems("plane_", CELL_SPECS))).toEqual(["nuverse.plane_lens"]);
		expect(menuSections("nuverse", CELL_SPECS)).toEqual([]);
	});

	it("drops what misses", () => {
		expect(menuSections("zzz", CELL_SPECS)).toEqual([]);
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

const MIXED: MenuEntry[] = [
	{ name: "nudemos.memes", label: "Memes", group: "Demos" },
	{ name: "nuverse.text", label: "Text", group: "Content" },
	{ name: "nulogs.logs", label: "Logs" },
	{ name: "nuverse.slider", label: "Slider", group: "Inputs" },
	{ name: "nudemos.mnist", label: "MNIST", group: "Demos" },
];

const shape = (packages: ReturnType<typeof menuPackages>) =>
	packages.map((p) => [p.key, p.count, p.open]);

describe("menuPackages", () => {
	it("puts nuverse untitled on top, the rest folded titles with their counts", () => {
		expect(shape(menuPackages("", MIXED))).toEqual([
			[null, 2, true],
			["nudemos", 2, false],
			["nulogs", 1, false],
		]);
	});

	it("opens only the package the lit row is in", () => {
		expect(shape(menuPackages("", MIXED, "nudemos.mnist"))).toEqual([
			[null, 2, true],
			["nudemos", 2, true],
			["nulogs", 1, false],
		]);
		expect(shape(menuPackages("", MIXED, "nuverse.text"))).toEqual([
			[null, 2, true],
			["nudemos", 2, false],
			["nulogs", 1, false],
		]);
	});

	it("steps every row, folded or not, nuverse's first", () => {
		expect(menuRows(menuPackages("", MIXED)).map((i) => i.name)).toEqual([
			"nuverse.text",
			"nuverse.slider",
			"nudemos.memes",
			"nudemos.mnist",
			"nulogs.logs",
		]);
	});

	it("opens every package on a query, nuverse still first, then best match", () => {
		expect(shape(menuPackages("l", MIXED))).toEqual([
			[null, 1, true],
			["nulogs", 1, true],
		]);
		expect(shape(menuPackages("m", MIXED))).toEqual([["nudemos", 2, true]]);
	});

	it("draws no title for one package", () => {
		const got = menuPackages("", CELL_SPECS.slice(0, 3));
		expect(shape(got)).toEqual([[null, 3, true]]);
	});
});
