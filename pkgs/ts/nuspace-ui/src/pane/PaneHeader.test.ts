import { describe, expect, it } from "vitest";
import type { Crumb } from "../plane/types";
import { crumbsOf } from "./PaneHeader";

const crumb = (id: string): Crumb => ({ id, title: id.toUpperCase() });
const ids = (trail: string[]) =>
	crumbsOf(trail.map(crumb)).map((c) => (c === "fold" ? "..." : c.id));

describe("pane trail", () => {
	it("shows up to two parents, then folds the middle", () => {
		expect(ids([])).toEqual([]);
		expect(ids(["a"])).toEqual(["a"]);
		expect(ids(["a", "b"])).toEqual(["a", "b"]);
		expect(ids(["a", "b", "c"])).toEqual(["a", "...", "c"]);
	});
});
