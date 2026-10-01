// The plane's one gutter owner, case by case in priority order.

import { describe, expect, it } from "vitest";
import { gutterOwner } from "./state";

const ed = (selected: string[], focused: string | null = null) => ({ selected, focused });

describe("gutterOwner", () => {
	it("is nobody with more than one cell selected, whatever else holds", () => {
		expect(gutterOwner(ed(["a", "b"], "a"), "c", null)).toBeNull();
		expect(gutterOwner(ed(["a", "b"]), "a", "a")).toBeNull();
	});

	it("is the cell whose menu is open, until it closes", () => {
		expect(gutterOwner(ed([], "b"), "c", "a")).toBe("a");
		expect(gutterOwner(ed(["b"]), "c", "a")).toBe("a");
	});

	it("is the one selected cell, over focus and hover", () => {
		expect(gutterOwner(ed(["a"], "b"), "c", null)).toBe("a");
	});

	it("is the focused cell, over hover", () => {
		expect(gutterOwner(ed([], "b"), "c", null)).toBe("b");
	});

	it("is the hovered cell when nothing pins one", () => {
		expect(gutterOwner(ed([]), "c", null)).toBe("c");
	});

	it("is nobody when nothing pins and nothing is hovered", () => {
		expect(gutterOwner(ed([]), null, null)).toBeNull();
	});
});
