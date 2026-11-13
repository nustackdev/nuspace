// A plane's id and key next to its title, rendered in jsdom: the `@key` line
// shows only with a key and copies it, the title row's `#` opens and closes
// the identity block, a save sends the plane's key ops on the pane's own
// node, and the plane menu
// copies its id and key.

import type { Frame } from "@nustackdev/ui-core";
import { TooltipProvider, tree } from "@nustackdev/ui-kit";
import type * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlaneMenuItems } from "../menu/PlaneMenuItems";
import type { MenuParts } from "../menu/parts";
import { coerceHead } from "../plane/types";
import { Pane } from "./Pane";
import { panePath } from "./state";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
// The body's scroll area sizes itself with a ResizeObserver, which jsdom lacks.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

let host: HTMLDivElement;
let root: Root;
const writeText = vi.fn(() => Promise.resolve());
const VIEWER = ["viewer"];
const PANE = panePath(VIEWER, "p1");
/** What the pane sent, as the socket would have it. */
let sent: Frame[] = [];
/** The last op sent and its payload. */
const last = () => {
	const frame = sent.at(-1);
	return frame ? [frame.ref, frame.payload] : null;
};

function render(key: string, editable = true) {
	act(() => {
		tree.getState().write(
			PANE.map((s) => [s, null]),
			{ head: coerceHead({ title: "Notes", editable, width: "page", key }), cells: [] },
		);
		root.render(
			<TooltipProvider>
				<Pane viewerPath={VIEWER} planeId="p1" cellSpecs={[]} focused={false} />
			</TooltipProvider>,
		);
	});
}

const handle = () => host.querySelector<HTMLButtonElement>("[data-plane-key]");
const toggle = () => host.querySelector<HTMLButtonElement>("[data-plane-identity]");
const block = () => host.querySelector("[data-identity]");
const field = () => host.querySelector<HTMLInputElement>('input[aria-label="plane key"]');
const saveButton = () => [...host.querySelectorAll("button")].find((b) => b.textContent === "Save");

function type(text: string) {
	const input = field();
	const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
	act(() => {
		set?.call(input, text);
		input?.dispatchEvent(new Event("input", { bubbles: true }));
	});
}

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	sent = [];
	tree.getState().setSender((f) => sent.push(f));
	writeText.mockClear();
	Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().setSender(null);
	tree.getState().remove(VIEWER);
});

describe("the key line", () => {
	it("shows nothing without a key", () => {
		render("");
		expect(handle()).toBeNull();
		expect(host.textContent).not.toContain("@");
	});

	it("shows @key under the title, and a click copies it and says so in place", async () => {
		render("notes");
		expect(handle()?.textContent).toBe("@notes");
		expect(handle()?.getAttribute("aria-label")).toBe("Copy key");
		await act(async () => {
			handle()?.click();
		});
		expect(writeText).toHaveBeenCalledWith("notes");
		expect(handle()?.textContent).toBe("Copied");
	});

	it("copies on a read-only plane too", async () => {
		render("notes", false);
		await act(async () => {
			handle()?.click();
		});
		expect(writeText).toHaveBeenCalledWith("notes");
	});
});

describe("the identity toggle", () => {
	it("sits in the title row's right gutter, and opens and closes the block", () => {
		render("notes");
		const lane = toggle()?.parentElement;
		expect(lane?.className).toContain("col-[gutter-r]");
		expect(lane?.hasAttribute("data-pinned")).toBe(false);
		expect(block()).toBeNull();
		act(() => toggle()?.click());
		expect(block()?.getAttribute("data-identity")).toBe("plane");
		expect(host.querySelector("[data-identity-id]")?.textContent).toBe("p1");
		expect(field()?.value).toBe("notes");
		expect(toggle()?.parentElement?.hasAttribute("data-pinned")).toBe(true);
		// The key line stays while the block is open.
		expect(handle()).not.toBeNull();
		act(() => toggle()?.click());
		expect(block()).toBeNull();
	});

	it("closes on Escape in the key field", () => {
		render("notes");
		act(() => toggle()?.click());
		act(() => {
			field()?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		});
		expect(block()).toBeNull();
	});

	it("saves the key through the plane's ops, and an empty one removes it", () => {
		render("notes");
		act(() => toggle()?.click());
		type("journal");
		act(() => saveButton()?.click());
		// On the pane's own path: no plane id, the path says it.
		expect(last()).toEqual([[...PANE, "ops", "plane.key"], { key: "journal" }]);
		type("");
		act(() => saveButton()?.click());
		expect(last()).toEqual([[...PANE, "ops", "plane.remove_key"], {}]);
	});

	it("shows the key read-only on a read-only plane", () => {
		render("notes", false);
		act(() => toggle()?.click());
		expect(field()?.readOnly).toBe(true);
		expect(saveButton()).toBeUndefined();
	});
});

/** Plain buttons for the menu's parts, so the rows render without a menu open. */
const parts: MenuParts = {
	Item: ({ children, onSelect, disabled }) => (
		<button
			type="button"
			disabled={disabled}
			onClick={(e: React.MouseEvent) => onSelect?.(e.nativeEvent)}
		>
			{children}
		</button>
	),
	Separator: () => <hr />,
	Shortcut: () => null,
};

function renderMenu(planeKey?: string) {
	act(() => {
		root.render(<PlaneMenuItems parts={parts} planeId="p1" planeKey={planeKey} />);
	});
}

const row = (text: string) =>
	[...host.querySelectorAll("button")].find((b) => b.textContent === text);

describe("the plane menu", () => {
	it("copies the plane ID and key", async () => {
		renderMenu("notes");
		await act(async () => {
			row("Copy plane ID")?.click();
		});
		expect(writeText).toHaveBeenLastCalledWith("p1");
		await act(async () => {
			row("Copy plane key")?.click();
		});
		expect(writeText).toHaveBeenLastCalledWith("notes");
	});

	it("disables Copy plane key without a key", () => {
		renderMenu("");
		expect(row("Copy plane key")?.disabled).toBe(true);
	});

	it("leaves the key row out where the key is not known", () => {
		renderMenu();
		expect(row("Copy plane ID")).toBeDefined();
		expect(row("Copy plane key")).toBeUndefined();
	});
});
