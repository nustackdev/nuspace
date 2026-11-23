import { describe, expect, it } from "vitest";
import { anchorAt } from "../sidebar/ops";
import { orderMoves } from "./ops";

describe("orderMoves", () => {
	it("moves nothing for the same order", () => {
		expect(orderMoves(["a", "b", "c"], ["a", "b", "c"])).toEqual([]);
	});

	it("moves one cell to the top before the first", () => {
		expect(orderMoves(["a", "b", "c"], ["c", "a", "b"])).toEqual([{ id: "c", before: "a" }]);
	});

	it("moves one cell down after the one it lands under", () => {
		expect(orderMoves(["a", "b", "c"], ["b", "c", "a"])).toEqual([
			{ id: "b", before: "a" },
			{ id: "c", after: "b" },
		]);
		expect(orderMoves(["a", "b", "c"], ["a", "c", "b"])).toEqual([{ id: "c", after: "a" }]);
	});
});

describe("anchorAt", () => {
	it("is the item it lands before, or nothing for the end", () => {
		expect(anchorAt(["a", "b"], 0)).toEqual({ before: "a" });
		expect(anchorAt(["a", "b"], 2)).toEqual({});
		expect(anchorAt(["a", "b"], -1)).toEqual({});
	});
});
