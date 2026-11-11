// Drag and drop on the canvas side: the target off the pointer for each
// surface (a strip's edges, halves and end zone, a plane item's sides, an
// empty desk), no drop onto itself, and what a pane header carries per view.

import type * as React from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { resetRouter, setDesks, setRoles } from "../core/router";
import { dragging, endDrag, ITEM_MIME, PANE_MIME, PLANE_MIME, type Target } from "./dnd";
import { dropAt, edgeAt, headerDragProps, sameDrop, sameTarget, sideAt, targetAt } from "./drag";

const RECT = { left: 100, top: 50, width: 400, height: 200 };
const DESK = "desk0001";

describe("the drop target off the pointer", () => {
	it("is an edge in the outer quarters, a half in the middle", () => {
		expect(edgeAt(RECT, 110, 60)).toBe("left");
		expect(edgeAt(RECT, 199, 240)).toBe("left");
		expect(edgeAt(RECT, 490, 60)).toBe("right");
		expect(edgeAt(RECT, 401, 240)).toBe("right");
		expect(edgeAt(RECT, 300, 60)).toBe("top");
		expect(edgeAt(RECT, 300, 149)).toBe("top");
		expect(edgeAt(RECT, 300, 151)).toBe("bottom");
	});

	it("is a side of a plane item in its outer quarters only", () => {
		expect(sideAt(RECT, 110)).toBe("left");
		expect(sideAt(RECT, 490)).toBe("right");
		expect(sideAt(RECT, 300)).toBeNull();
	});

	it("reads the pane under the pointer, else the end zone, else nothing", () => {
		const desk = document.createElement("div");
		desk.innerHTML = `
			<div class="cols"><section data-pane="a"><p>x</p></section><div data-end="1"></div></div>`;
		document.body.append(desk);
		const pane = desk.querySelector<HTMLElement>("[data-pane]") as HTMLElement;
		pane.getBoundingClientRect = () => ({ ...RECT }) as DOMRect;
		const inner = pane.querySelector("p");
		expect(dropAt(inner, 120, 60, desk)).toEqual({ plane: "a", edge: "left" });
		expect(dropAt(inner, 300, 200, desk)).toEqual({ plane: "a", edge: "bottom" });
		expect(dropAt(desk.querySelector("[data-end]"), 0, 0, desk)).toEqual({ at: 1 });
		expect(dropAt(desk.querySelector(".cols"), 0, 0, desk)).toBeNull();
		expect(dropAt(desk, 0, 0, desk)).toBeNull();
		desk.remove();
	});

	it("reads nothing outside the canvas", () => {
		const outer = document.createElement("div");
		outer.innerHTML = `<div data-end="0"><div class="desk"></div></div>`;
		const desk = outer.querySelector(".desk") as HTMLElement;
		expect(dropAt(desk, 0, 0, desk)).toBeNull();
	});

	it("builds the target for each surface", () => {
		const canvas = document.createElement("div");
		canvas.innerHTML = `<section data-pane="a"><p>x</p></section><div data-end="1"></div>`;
		document.body.append(canvas);
		const pane = canvas.querySelector<HTMLElement>("[data-pane]") as HTMLElement;
		pane.getBoundingClientRect = () => ({ ...RECT }) as DOMRect;
		const inner = pane.querySelector("p");
		const strip = { kind: "strip", desk: DESK, item: "strip1" } as const;
		const plane = { kind: "plane", desk: DESK, item: "lone01" } as const;

		expect(targetAt(strip, inner, 120, 60, canvas)).toEqual({
			kind: "strip",
			desk: DESK,
			item: "strip1",
			drop: { plane: "a", edge: "left" },
		});
		expect(targetAt(strip, canvas.querySelector("[data-end]"), 0, 0, canvas)).toEqual({
			kind: "strip",
			desk: DESK,
			item: "strip1",
			drop: { at: 1 },
		});
		expect(targetAt(strip, canvas, 0, 0, canvas)).toBeNull();

		expect(targetAt(plane, inner, 490, 60, canvas)).toEqual({
			kind: "onto",
			desk: DESK,
			item: "lone01",
			side: "right",
		});
		expect(targetAt(plane, inner, 300, 60, canvas)).toBeNull();
		expect(targetAt(plane, canvas, 0, 0, canvas)).toBeNull();

		expect(targetAt({ kind: "desk", desk: DESK }, canvas, 0, 0, canvas)).toEqual({
			kind: "end",
			desk: DESK,
		});
		canvas.remove();
	});

	it("compares drops and targets by place", () => {
		expect(sameDrop({ at: 1 }, { at: 1 })).toBe(true);
		expect(sameDrop({ at: 1 }, { at: 2 })).toBe(false);
		expect(sameDrop({ column: 0 }, { column: 0 })).toBe(true);
		expect(sameDrop({ column: 0 }, { at: 0 })).toBe(false);
		expect(sameDrop({ plane: "a", edge: "left" }, { plane: "a", edge: "left" })).toBe(true);
		expect(sameDrop({ plane: "a", edge: "left" }, { plane: "a", edge: "top" })).toBe(false);
		expect(sameDrop({ at: 0 }, null)).toBe(false);
		expect(sameDrop(null, null)).toBe(true);

		const onto: Target = { kind: "onto", desk: DESK, item: "lone01", side: "left" };
		const strip: Target = { kind: "strip", desk: DESK, item: "strip1", drop: { at: 2 } };
		expect(sameTarget(onto, { ...onto })).toBe(true);
		expect(sameTarget(onto, { ...onto, side: "right" })).toBe(false);
		expect(sameTarget(strip, { ...strip, drop: { at: 2 } })).toBe(true);
		expect(sameTarget(strip, { ...strip, drop: { at: 1 } })).toBe(false);
		expect(sameTarget({ kind: "end", desk: DESK }, { kind: "end", desk: DESK })).toBe(true);
		expect(sameTarget({ kind: "end", desk: DESK }, { kind: "end", desk: "desk0002" })).toBe(false);
		expect(sameTarget(onto, null)).toBe(false);
		expect(sameTarget(null, null)).toBe(true);
	});
});

describe("what a pane header's drag carries", () => {
	beforeEach(() => {
		resetRouter();
		setDesks({});
		setRoles({ home: "", settings: "", search: "" });
	});
	afterEach(() => endDrag());

	/** A drag start's `DataTransfer`, recording what is set on it. */
	function start(props: { onDragStart: (e: React.DragEvent) => void }) {
		const data: Record<string, string> = {};
		const dt = {
			effectAllowed: "none",
			setData: (mime: string, value: string) => {
				data[mime] = value;
			},
		};
		props.onDragStart({ dataTransfer: dt } as unknown as React.DragEvent);
		return { data, dt };
	}

	it("in a strip, the pane", () => {
		const props = headerDragProps({ kind: "strip", desk: DESK, item: "strip1" }, "a");
		expect(props.draggable).toBe(true);
		const { data, dt } = start(props);
		expect(Object.keys(data)).toEqual([PANE_MIME]);
		expect(JSON.parse(data[PANE_MIME])).toEqual({ desk: DESK, item: "strip1", plane: "a" });
		expect(dt.effectAllowed).toBe("move");
		expect(dragging()).toEqual({ kind: "pane", desk: DESK, item: "strip1", plane: "a" });
		props.onDragEnd();
		expect(dragging()).toBeNull();
	});

	it("shows the one drag chip, the marked icon and title, not the whole header", async () => {
		const header = document.createElement("header");
		header.innerHTML =
			'<span data-drag-icon><svg data-icon="x"></svg></span><nav><span>Parent</span><span data-drag-title>Logs</span></nav><button>...</button>';
		document.body.append(header);
		let image: Element | null = null;
		const dataTransfer = {
			setData: () => {},
			setDragImage: (el: Element) => {
				image = el;
			},
		};
		const props = headerDragProps({ kind: "solo" }, "p_solo");
		props.onDragStart({ currentTarget: header, dataTransfer } as unknown as React.DragEvent);
		const chip = image as Element | null;
		expect(chip?.querySelector("svg[data-icon]")).not.toBeNull();
		expect(chip?.textContent).toBe("Logs");
		expect(chip?.querySelector("button")).toBeNull();
		await new Promise((r) => setTimeout(r));
		expect(chip?.isConnected).toBe(false);
		header.remove();
		props.onDragEnd();
	});

	it("on a plane item, the item", () => {
		const { data } = start(headerDragProps({ kind: "plane", desk: DESK, item: "lone01" }, "e"));
		expect(Object.keys(data)).toEqual([ITEM_MIME]);
		expect(JSON.parse(data[ITEM_MIME])).toEqual({ desk: DESK, item: "lone01" });
		expect(dragging()).toEqual({ kind: "item", desk: DESK, item: "lone01" });
	});

	it("on a solo plane, the plane with the params it shows", () => {
		window.history.replaceState(null, "", "/p_solo?run=42");
		const { data } = start(headerDragProps({ kind: "solo" }, "p_solo"));
		expect(Object.keys(data)).toEqual([PLANE_MIME]);
		const link = { plane: "p_solo", params: { run: "42" } };
		expect(JSON.parse(data[PLANE_MIME])).toEqual(link);
		expect(dragging()).toEqual({ kind: "plane", link });
	});
});
