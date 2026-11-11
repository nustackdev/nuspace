// The browser side of desks and roles: a feed lands in the router (older
// shape desks skipped), a desk op goes out as a create for a desk the server
// does not have yet and as a set after, a closed desk goes out as a delete,
// and a role as its op.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { dropOn } from "../desk/dnd";
import type { Desk } from "../desk/model";
import {
	applyDesksWrite,
	currentRoles,
	currentTitles,
	deleteDesk,
	deskOrder,
	moveDesk,
	resetDesks,
	setRole,
} from "./desks";
import {
	closeDesk,
	createDesk,
	currentRoute,
	currentRoutes,
	ensureLanding,
	knownDesks,
	renameDesk,
	resetRouter,
} from "./router";
import { notifyOp } from "./wire";

vi.mock("./wire", () => ({ notifyOp: vi.fn() }));

const AT = ["shell", "desks"];
const DESK = "desk0001";
const STRIP = "strip1";

/** A desk of one strip, one column per plane. */
function row(...planes: string[]): Desk {
	return {
		name: "Row",
		items: [
			{
				id: STRIP,
				kind: "strip",
				columns: planes.map((plane) => ({
					panes: [{ share: 1, original: { plane, params: {} } }],
				})),
			},
		],
	};
}

const roles = () =>
	applyDesksWrite(AT, { op: "set_roles", roles: { home: "p_home", settings: "", search: "" } });

const sent = () => vi.mocked(notifyOp).mock.calls.map(([path, op, args]) => ({ path, op, args }));

beforeEach(() => {
	resetRouter();
	resetDesks();
	vi.mocked(notifyOp).mockClear();
	window.history.replaceState(null, "", "/");
});

describe("feed in", () => {
	it("hands set_desks to the router, read whole", () => {
		roles();
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a", "b"), junk: 3 } });
		expect(knownDesks()).toEqual({ [DESK]: row("a", "b") });
		window.history.replaceState(null, "", `/${DESK}/${STRIP}`);
		expect(currentRoutes()).toEqual(["a", "b"]);
	});

	it("skips a desk stored in an older shape", () => {
		const columns = [{ width: 1, panes: [{ plane: "a", share: 1, params: {} }] }];
		const older = {
			desk0002: { name: "Old", strips: [{ columns }] },
			desk0003: { name: "Flat", columns },
		};
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a", "b"), ...older } });
		expect(knownDesks()).toEqual({ [DESK]: row("a", "b") });
	});

	it("keeps the shipped order, desks it misses after, a closed desk out", () => {
		const desks = { desk0003: row("c"), [DESK]: row("a"), desk0002: row("b") };
		applyDesksWrite(AT, { op: "set_desks", desks, order: ["desk0002", DESK, "gone0000"] });
		expect(deskOrder()).toEqual(["desk0002", DESK, "desk0003"]);
		const id = createDesk();
		expect(deskOrder()).toEqual(["desk0002", DESK, "desk0003", id]);
		closeDesk(DESK);
		expect(deskOrder()).toEqual(["desk0002", "desk0003", id]);
		// The new desk's create is not echoed yet: it stays, after the shipped order.
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a") }, order: [DESK] });
		expect(deskOrder()).toEqual([DESK, id]);
	});

	it("replaces what it had: a desk gone from the feed is gone", () => {
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a", "b") } });
		applyDesksWrite(AT, { op: "set_desks", desks: {} });
		expect(knownDesks()).toEqual({});
	});

	it("takes the shipped desk as the truth, over this tab's own move", () => {
		roles();
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a", "b") } });
		window.history.replaceState(null, "", `/${DESK}/${STRIP}`);
		dropOn(
			{ kind: "pane", desk: DESK, item: STRIP, plane: "a" },
			{
				kind: "strip",
				desk: DESK,
				item: STRIP,
				drop: { plane: "b", edge: "right" },
			},
		);
		expect(currentRoutes()).toEqual(["b", "a"]);
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a", "b", "c") } });
		expect(currentRoutes()).toEqual(["a", "b", "c"]);
	});

	it("hands set_roles to the router, and / lands on home with the desks", async () => {
		ensureLanding();
		expect(currentRoute()).toEqual({ kind: "pending" });
		applyDesksWrite(AT, { op: "set_desks", desks: {} });
		applyDesksWrite(AT, { op: "set_roles", roles: { home: "p_home", settings: "p_set" } });
		expect(currentRoles()).toEqual({ home: "p_home", settings: "p_set", search: "" });
		await Promise.resolve();
		expect(window.location.pathname).toBe("/p_home");
	});

	it("keeps set_titles, each write replacing the last", () => {
		expect(currentTitles().a?.title ?? "").toBe("");
		applyDesksWrite(AT, {
			op: "set_titles",
			titles: { a: { title: "Train run 42", icon: "lucide:flame" }, b: { title: 3 }, c: null },
		});
		expect(currentTitles().a?.title ?? "").toBe("Train run 42");
		expect(currentTitles().b?.title ?? "").toBe("");
		expect(currentTitles().c?.title ?? "").toBe("");
		applyDesksWrite(AT, { op: "set_titles", titles: { b: { title: "Logs", icon: "" } } });
		expect(currentTitles().a?.title ?? "").toBe("");
		expect(currentTitles().b?.title ?? "").toBe("Logs");
		expect(knownDesks()).toBeNull();
	});

	it("ignores any other write", () => {
		applyDesksWrite(AT, { op: "noise" });
		applyDesksWrite(AT, null);
		expect(knownDesks()).toBeNull();
		expect(currentRoles()).toBeNull();
	});
});

describe("moving a desk", () => {
	const three = () =>
		applyDesksWrite(AT, {
			op: "set_desks",
			desks: { aaaa0001: row("a", "b"), bbbb0002: row("a", "b"), cccc0003: row("a", "b") },
			order: ["aaaa0001", "bbbb0002", "cccc0003"],
		});

	it("moves it in front of another, or last, here at once, and sends desk.move", () => {
		three();
		vi.mocked(notifyOp).mockClear();
		moveDesk("cccc0003", "aaaa0001");
		expect(deskOrder()).toEqual(["cccc0003", "aaaa0001", "bbbb0002"]);
		moveDesk("cccc0003", "");
		expect(deskOrder()).toEqual(["aaaa0001", "bbbb0002", "cccc0003"]);
		expect(sent().map((s) => [s.op, s.args])).toEqual([
			["desk.move", { desk_id: "cccc0003", before: "aaaa0001" }],
			["desk.move", { desk_id: "cccc0003", before: "" }],
		]);
	});

	it("sends nothing for a move that leaves the order as it is", () => {
		three();
		vi.mocked(notifyOp).mockClear();
		moveDesk("aaaa0001", "aaaa0001");
		moveDesk("aaaa0001", "bbbb0002");
		expect(sent()).toEqual([]);
	});

	it("takes the shipped order as the truth after its own move", () => {
		three();
		moveDesk("cccc0003", "aaaa0001");
		three();
		expect(deskOrder()).toEqual(["aaaa0001", "bbbb0002", "cccc0003"]);
	});
});

describe("writes out", () => {
	it("sets a desk the server has, through the node's path", () => {
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a", "b") } });
		dropOn(
			{ kind: "pane", desk: DESK, item: STRIP, plane: "a" },
			{
				kind: "strip",
				desk: DESK,
				item: STRIP,
				drop: { plane: "b", edge: "right" },
			},
		);
		expect(sent()).toEqual([
			{ path: AT, op: "desk.set", args: { desk_id: DESK, desk: knownDesks()?.[DESK] } },
		]);
	});

	it("creates a desk the server does not have, then sets it until the echo", () => {
		applyDesksWrite(AT, { op: "set_desks", desks: {} });
		const id = createDesk();
		expect(sent().map((s) => s.op)).toEqual(["desk.create"]);
		expect(sent()[0].args).toEqual({ desk_id: id, desk: { name: "Untitled", items: [] } });
		// Another tab's feed before the echo: the new desk stays.
		applyDesksWrite(AT, { op: "set_desks", desks: {} });
		expect(knownDesks()?.[id]).toEqual({ name: "Untitled", items: [] });
		renameDesk(id, "Mine");
		expect(sent().map((s) => s.op)).toEqual(["desk.create", "desk.set"]);
		// The echo lands: from now on it is the store's.
		applyDesksWrite(AT, { op: "set_desks", desks: { [id]: { name: "Mine", items: [] } } });
		applyDesksWrite(AT, { op: "set_desks", desks: {} });
		expect(knownDesks()).toEqual({});
	});

	it("deletes a desk at once, and sends the delete", () => {
		applyDesksWrite(AT, { op: "set_desks", desks: { [DESK]: row("a", "b") } });
		deleteDesk(DESK);
		expect(knownDesks()).toEqual({});
		expect(sent()).toEqual([{ path: AT, op: "desk.delete", args: { desk_id: DESK } }]);
	});

	it("sends the delete for a desk the router closes, a tab on it going home", () => {
		roles();
		const two = { [DESK]: row("a", "b"), desk0002: row("x", "y") };
		applyDesksWrite(AT, { op: "set_desks", desks: two });
		window.history.replaceState(null, "", `/desk0002/${STRIP}`);
		closeDesk("desk0002");
		expect(window.location.pathname).toBe("/p_home");
		expect(knownDesks()).toEqual({ [DESK]: row("a", "b") });
		expect(sent()).toEqual([{ path: AT, op: "desk.delete", args: { desk_id: "desk0002" } }]);
	});

	it("sends a role", () => {
		applyDesksWrite(AT, { op: "set_roles", roles: { home: "a", settings: "b", search: "c" } });
		setRole("home", "p_new");
		expect(sent()).toEqual([
			{ path: AT, op: "role.set", args: { role: "home", plane_id: "p_new" } },
		]);
	});

	it("sends nothing before the node has fed it", () => {
		setRole("home", "p_new");
		expect(sent()).toEqual([]);
	});
});
