import { describe, expect, it } from "vitest";
import type { CellSpec } from "../types";
import { PROGRAM, slashItems, slashPackages } from "./slash";

const CELL_SPECS: CellSpec[] = [
	{ name: "nuverse.text", label: "Text", group: "Content" },
	{ name: "nuverse.prose", label: "Prose", group: "Content" },
	{ name: "nuverse.slider", label: "Slider", group: "Inputs" },
];

const names = (items: CellSpec[]) => items.map((i) => i.name);

describe("slashItems", () => {
	it("pins the empty program above every registered cell", () => {
		expect(names(slashItems("", CELL_SPECS))).toEqual([
			"",
			"nuverse.text",
			"nuverse.prose",
			"nuverse.slider",
		]);
		expect(slashItems("", [])).toEqual([PROGRAM]);
	});

	it("stays on top when it matches, and leaves when it does not", () => {
		expect(names(slashItems("em", CELL_SPECS))).toEqual([""]);
		// "program" still finds it, through its description.
		expect(names(slashItems("program", CELL_SPECS))).toEqual([""]);
		expect(names(slashItems("sl", CELL_SPECS))).toEqual(["nuverse.slider"]);
	});
});

describe("slashPackages", () => {
	it("keeps the program and nuverse on top, other packages folded until lit", () => {
		const specs = [...CELL_SPECS, { name: "nulogs.logs", label: "Logs" }];
		const shape = (lit?: string) => slashPackages("", specs, lit).map((p) => [p.key, p.open]);
		expect(shape()).toEqual([
			[null, true],
			[null, true],
			["nulogs", false],
		]);
		expect(shape("nulogs.logs")).toEqual([
			[null, true],
			[null, true],
			["nulogs", true],
		]);
		expect(names(slashItems("", specs))).toEqual([
			"",
			"nuverse.text",
			"nuverse.prose",
			"nuverse.slider",
			"nulogs.logs",
		]);
	});
});
