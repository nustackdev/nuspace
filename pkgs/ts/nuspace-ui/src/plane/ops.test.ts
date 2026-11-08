import { describe, expect, it } from "vitest";
import { anchorAt } from "../sidebar/ops";
import { cellMoves } from "./ops";

describe("cellMoves", () => {
	it("moves nothing for the same order", () => {
		expect(cellMoves(["a", "b", "c"], ["a", "b", "c"])).toEqual([]);
	});

	it("moves one cell to the top before the first", () => {
		expect(cellMoves(["a", "b", "c"], ["c", "a", "b"])).toEqual([{ cell_id: "c", before: "a" }]);
	});

	it("moves one cell down after the one it lands under", () => {
		expect(cellMoves(["a", "b", "c"], ["b", "c", "a"])).toEqual([
			{ cell_id: "b", before: "a" },
			{ cell_id: "c", after: "b" },
		]);
		expect(cellMoves(["a", "b", "c"], ["a", "c", "b"])).toEqual([{ cell_id: "c", after: "a" }]);
	});
});

describe("anchorAt", () => {
	it("is the item it lands before, or nothing for the end", () => {
		expect(anchorAt(["a", "b"], 0)).toEqual({ before: "a" });
		expect(anchorAt(["a", "b"], 2)).toEqual({});
		expect(anchorAt(["a", "b"], -1)).toEqual({});
	});
});
