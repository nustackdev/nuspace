// The desk screen's pure parts: pages in reading order, the page a scroll
// stands on, and the counter.

import { describe, expect, it } from "vitest";
import type { Item } from "../../desk/model";
import { pageAt, pageCount, pageOf, pagesOf } from "./model";

const link = (plane: string) => ({ original: { plane, params: {} } });

describe("pagesOf", () => {
	it("reads a strip column by column, top to bottom", () => {
		const strip: Item = {
			id: "item01",
			kind: "strip",
			columns: [
				{
					panes: [
						{ share: 1, ...link("a") },
						{ share: 1, ...link("b") },
					],
				},
				{ panes: [{ share: 1, ...link("c") }] },
				{
					panes: [
						{ share: 1, ...link("d") },
						{ share: 1, ...link("e") },
					],
				},
			],
		};
		expect(pagesOf(strip).map((p) => p.plane)).toEqual(["a", "b", "c", "d", "e"]);
	});

	it("shows a pane's recent over its original", () => {
		const strip: Item = {
			id: "item01",
			kind: "strip",
			columns: [
				{ panes: [{ share: 1, ...link("a"), recent: { plane: "z", params: { q: "1" } } }] },
			],
		};
		expect(pagesOf(strip)).toEqual([{ plane: "z", params: { q: "1" } }]);
	});

	it("makes a plane item one page", () => {
		const item: Item = { id: "item02", kind: "plane", ...link("solo") };
		expect(pagesOf(item).map((p) => p.plane)).toEqual(["solo"]);
	});
});

describe("pageOf", () => {
	const pages = ["a", "b", "c"].map((plane) => ({ plane, params: {} }));
	it("finds the focused pane's page", () => {
		expect(pageOf(pages, "c")).toBe(2);
	});
	it("falls back to the first page", () => {
		expect(pageOf(pages, "")).toBe(0);
		expect(pageOf(pages, "gone")).toBe(0);
	});
});

describe("pageAt", () => {
	it("rounds to the nearest page", () => {
		expect(pageAt(0, 375, 3)).toBe(0);
		expect(pageAt(180, 375, 3)).toBe(0);
		expect(pageAt(200, 375, 3)).toBe(1);
		expect(pageAt(750, 375, 3)).toBe(2);
	});
	it("stays inside the pages, past either end too", () => {
		expect(pageAt(-40, 375, 3)).toBe(0);
		expect(pageAt(2000, 375, 3)).toBe(2);
		expect(pageAt(100, 0, 3)).toBe(0);
		expect(pageAt(100, 375, 0)).toBe(0);
	});
});

describe("pageCount", () => {
	it("says n/m for a pager", () => {
		expect(pageCount(1, 3)).toBe("2/3");
	});
	it("says nothing for a single page", () => {
		expect(pageCount(0, 1)).toBeNull();
	});
});
