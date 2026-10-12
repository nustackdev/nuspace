import { describe, expect, it } from "vitest";
import { PROGRAM, slashItems } from "./slash";
import type { SlashSnippet } from "./types";

const SNIPPETS: SlashSnippet[] = [
	{ name: "text", label: "Text", group: "Content" },
	{ name: "prose", label: "Prose", group: "Content" },
	{ name: "slider", label: "Slider", group: "Inputs" },
];

const names = (items: SlashSnippet[]) => items.map((i) => i.name);

describe("slashItems", () => {
	it("pins the empty program above every snippet", () => {
		expect(names(slashItems("", SNIPPETS))).toEqual(["", "text", "prose", "slider"]);
		expect(slashItems("", [])).toEqual([PROGRAM]);
	});

	it("stays on top when it matches, and leaves when it does not", () => {
		expect(names(slashItems("em", SNIPPETS))).toEqual([""]);
		// "program" still finds it, through its description.
		expect(names(slashItems("program", SNIPPETS))).toEqual([""]);
		expect(names(slashItems("sl", SNIPPETS))).toEqual(["slider"]);
	});
});
