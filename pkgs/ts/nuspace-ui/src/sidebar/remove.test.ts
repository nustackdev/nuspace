import { afterEach, describe, expect, it, vi } from "vitest";
import { canDelete, deletePlane } from "./remove";
import { coerceTree, ROOT_ID } from "./types";

const tree = coerceTree([
	{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["home", "a"] },
	{ id: "home", kind: "plane", title: "Home", parent: ROOT_ID, children: [], system: true },
	{ id: "a", kind: "plane", title: "A", parent: ROOT_ID, children: ["a1"] },
	{ id: "a1", kind: "plane", title: "A1", parent: "a", children: [] },
]);

describe("deleting a plane", () => {
	afterEach(() => vi.restoreAllMocks());

	it("is not offered for a system plane or one the tree lacks", () => {
		expect(tree.home.system).toBe(true);
		expect(tree.a.system).toBe(false);
		expect(canDelete(tree, "home")).toBe(false);
		expect(canDelete(tree, "gone")).toBe(false);
		expect(canDelete(tree, "a")).toBe(true);
	});

	it("sends one op and closes the subtree, landing home when nothing is left", () => {
		window.history.replaceState({}, "", "/a+a1");
		vi.spyOn(window, "confirm").mockReturnValue(true);
		const notify = vi.fn();
		deletePlane(notify, tree, "a", "A");
		expect(notify).toHaveBeenCalledWith("plane.delete", { plane_id: "a" });
		expect(window.location.pathname).toBe("/home");
	});

	it("does nothing when not confirmed", () => {
		window.history.replaceState({}, "", "/a");
		vi.spyOn(window, "confirm").mockReturnValue(false);
		const notify = vi.fn();
		deletePlane(notify, tree, "a", "A");
		expect(notify).not.toHaveBeenCalled();
		expect(window.location.pathname).toBe("/a");
	});
});
