import { afterEach, describe, expect, it, vi } from "vitest";
import { confirm } from "../shell/confirm";
import { canDelete, deletePlane } from "./remove";
import { coerceTree, ROOT_ID } from "./types";

vi.mock("../shell/confirm", () => ({ confirm: vi.fn() }));

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

	it("sends one op and closes the subtree, landing home when nothing is left", async () => {
		window.history.replaceState({}, "", "/a+a1");
		vi.mocked(confirm).mockResolvedValue(true);
		const notify = vi.fn();
		await deletePlane(notify, tree, "a", "A");
		expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ action: "Delete" }));
		expect(notify).toHaveBeenCalledWith("plane.delete", { plane_id: "a" });
		expect(window.location.pathname).toBe("/home");
	});

	it("does nothing when not confirmed", async () => {
		window.history.replaceState({}, "", "/a");
		vi.mocked(confirm).mockResolvedValue(false);
		const notify = vi.fn();
		await deletePlane(notify, tree, "a", "A");
		expect(notify).not.toHaveBeenCalled();
		expect(window.location.pathname).toBe("/a");
	});
});
