// Editing a plane's cells: the mode as a history entry, and a cell in and out
// of it. Browsing, a cell is only its content and takes no gesture; editing,
// it is one button over inert content.

import { History, TooltipProvider, TouchProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Cell } from "../../plane/types";
import { SIDEBAR_STATE } from "../sidebar/open";
import { doneEditing, EDITING_STATE, editCells, editingOf, settleEditing } from "./editing";
import { MobileCell } from "./MobileCell";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("editing cells as a history entry", () => {
	beforeEach(() => {
		window.history.replaceState(null, "", "/p/home");
	});
	afterEach(() => {
		window.history.replaceState(null, "", "/");
	});

	it("reads the plane off the entry, nothing for none", () => {
		expect(editingOf({ state: null })).toBeNull();
		expect(editingOf({ state: { [EDITING_STATE]: "home" } })).toBe("home");
		expect(editingOf({ state: { [EDITING_STATE]: "" } })).toBeNull();
		expect(editingOf({ state: { [EDITING_STATE]: true } })).toBeNull();
	});

	it("enters by pushing the same url with the plane, once", () => {
		const before = window.history.length;
		editCells("home");
		expect(window.history.length).toBe(before + 1);
		expect(History.current().url).toBe("/p/home");
		expect(editingOf(History.current())).toBe("home");
		editCells("home");
		expect(window.history.length).toBe(before + 1);
	});

	it("turns into another plane's mode in place", () => {
		editCells("home");
		const before = window.history.length;
		editCells("notes");
		expect(window.history.length).toBe(before);
		expect(editingOf(History.current())).toBe("notes");
	});

	it("keeps what else the entry carries", () => {
		window.history.replaceState({ a: 1 }, "", "/p/home");
		editCells("home");
		expect(History.current().state).toEqual({ a: 1, [EDITING_STATE]: "home" });
	});

	it("leaves by going back", async () => {
		editCells("home");
		const back = new Promise<void>((resolve) => {
			const off = History.subscribe((move) => {
				if (move.kind !== "pop") return;
				off();
				resolve();
			});
		});
		doneEditing();
		await back;
		expect(editingOf(History.current())).toBeNull();
	});

	it("does nothing when not editing", () => {
		const back = vi.spyOn(History, "back");
		doneEditing();
		expect(back).not.toHaveBeenCalled();
		back.mockRestore();
	});

	it("drops the mark in place after a reload while editing, the sidebar's kept", () => {
		window.history.replaceState({ [EDITING_STATE]: "home", [SIDEBAR_STATE]: true }, "", "/p/home");
		const before = window.history.length;
		settleEditing();
		expect(editingOf(History.current())).toBeNull();
		expect(History.current().state).toEqual({ [SIDEBAR_STATE]: true });
		expect(window.history.length).toBe(before);
	});
});

describe("a cell in and out of editing", () => {
	const cell = {
		id: "c1",
		name: "welcome",
		key: "hello",
		source: "",
		draws: false,
		classes: [],
		status: { state: "idle", error: null },
	} as unknown as Cell;

	let host: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
	});
	afterEach(() => {
		act(() => root.unmount());
		host.remove();
	});

	const draw = (editing: boolean, onOptions = () => {}) =>
		act(() => {
			root.render(
				<TouchProvider value>
					<TooltipProvider>
						<MobileCell
							cell={cell}
							uiPath={["viewer", "cells", "c1"]}
							pressed={false}
							editing={editing}
							onOptions={onOptions}
						/>
					</TooltipProvider>
				</TouchProvider>,
			);
		});
	const el = () => host.querySelector("[data-cell=c1]") as HTMLElement;

	it("browsing, is only its content: no button, nothing inert", () => {
		draw(false);
		expect(el().getAttribute("role")).toBeNull();
		expect(el().querySelector("[inert]")).toBeNull();
		expect(el().textContent).toContain("No view");
	});

	it("editing, is one button over inert content that opens its options", () => {
		const onOptions = vi.fn();
		draw(true, onOptions);
		expect(el().getAttribute("role")).toBe("button");
		expect(el().getAttribute("aria-label")).toBe("Options for @hello");
		expect(el().firstElementChild?.hasAttribute("inert")).toBe(true);
		act(() => el().click());
		act(() => {
			el().dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		});
		expect(onOptions).toHaveBeenCalledTimes(2);
	});

	it("keeps what it draws mounted going in and out", () => {
		draw(false);
		const content = el().firstElementChild;
		draw(true);
		expect(el().firstElementChild).toBe(content);
		draw(false);
		expect(el().firstElementChild).toBe(content);
	});
});
