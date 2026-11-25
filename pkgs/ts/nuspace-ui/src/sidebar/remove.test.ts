import { afterEach, describe, expect, it, vi } from "vitest";
import { deletedPlane } from "../refs/toast";
import { canDelete, deletePlane } from "./remove";
import { coerceTree, ROOT_ID } from "./types";

vi.mock("../refs/toast", () => ({ deletedPlane: vi.fn() }));

const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["home", "a"] },
	{ id: "home", kind: "plane", title: "Home", parent: ROOT_ID, children: [], system: true },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: ["a1"] },
	{ id: "a1", kind: "plane", title: "A1", parent: "a", children: [] },
]);

describe("deleting a plane", () => {
	afterEach(() => vi.resetAllMocks());

	it("is not offered for a system plane or one the tree lacks", () => {
		expect(tree.home.system).toBe(true);
		expect(tree.a.system).toBe(false);
		expect(canDelete(tree, "home")).toBe(false);
		expect(canDelete(tree, "gone")).toBe(false);
		expect(canDelete(tree, "a")).toBe(true);
	});

	it("sends one op at once, toasts an Undo, and leaves the tab where it is", () => {
		window.history.replaceState(null, "", "/p/a1");
		const notify = vi.fn();
		deletePlane(notify, "a", "A");
		expect(notify).toHaveBeenCalledExactlyOnceWith("plane.delete", { plane_id: "a" });
		expect(deletedPlane).toHaveBeenCalledWith("a", "A");
		expect(window.location.pathname).toBe("/p/a1");
	});
});
