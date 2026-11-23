import { describe, expect, it } from "vitest";
import { anchorAt } from "../sidebar/ops";

describe("anchorAt", () => {
	it("is the item it lands before, or nothing for the end", () => {
		expect(anchorAt(["a", "b"], 0)).toEqual({ before: "a" });
		expect(anchorAt(["a", "b"], 2)).toEqual({});
		expect(anchorAt(["a", "b"], -1)).toEqual({});
	});
});
