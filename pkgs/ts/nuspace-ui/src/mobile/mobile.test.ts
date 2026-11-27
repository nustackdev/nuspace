// The mobile frame's logic: when the banner shows, and which plane the screen
// draws for a route.

import { describe, expect, it } from "vitest";
import type { Route } from "../core/router";
import { bannerText } from "./Banner";
import { shownPlane } from "./Viewer";

describe("bannerText", () => {
	it("shows only while the connection is down", () => {
		expect(bannerText("connecting")).toBeNull();
		expect(bannerText("connected")).toBeNull();
		expect(bannerText("reconnecting")).toBe("Reconnecting");
		expect(bannerText("disconnected")).toBe("Disconnected");
	});
});

describe("shownPlane", () => {
	it("shows a solo plane as itself", () => {
		expect(shownPlane({ kind: "solo", plane: "home", params: {} })).toEqual({
			plane: "home",
			at: { kind: "solo" },
		});
	});

	it("shows a desk item's focused plane", () => {
		const route = {
			kind: "item",
			desk: "abcd1234",
			name: "Work",
			item: { kind: "strip", id: "item01" },
			focus: "notes",
		} as unknown as Route;
		expect(shownPlane(route)).toEqual({
			plane: "notes",
			at: { kind: "strip", desk: "abcd1234", item: "item01" },
		});
	});

	it("shows nothing while pending or on an empty desk", () => {
		expect(shownPlane({ kind: "pending" })).toBeNull();
		expect(shownPlane({ kind: "desk", desk: "abcd1234", name: "Work" })).toBeNull();
	});
});
