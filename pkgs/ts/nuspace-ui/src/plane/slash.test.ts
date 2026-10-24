import { describe, expect, it } from "vitest";
import { PROGRAM, slashItems } from "./slash";
import type { CellSpec } from "./types";

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
