// A plane's key under its title, rendered in jsdom: the `@key` line shows
// only with a key and copies it, and the title row has no identity toggle:
// the key is edited from the pane's `...` menu. The plane menu copies its
// id, and leaves that row out where the menu shows the id itself.

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

describe("the title row", () => {
	it("has no identity toggle: the key is edited from the menu", () => {
		render("notes");
		expect(host.querySelector("[data-plane-identity]")).toBeNull();
		expect(host.querySelector("[data-identity]")).toBeNull();
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

function renderMenu(copyId?: boolean) {
	act(() => {
		root.render(<PlaneMenuItems parts={parts} planeId="p1" copyId={copyId} />);
	});
}

const row = (text: string) =>
	[...host.querySelectorAll("button")].find((b) => b.textContent === text);

describe("the plane menu", () => {
	it("copies the plane ID", async () => {
		renderMenu();
		await act(async () => {
			row("Copy plane ID")?.click();
		});
		expect(writeText).toHaveBeenLastCalledWith("p1");
	});

	it("leaves Copy plane ID out where the menu shows the id itself", () => {
		renderMenu(false);
		expect(row("Copy plane ID")).toBeUndefined();
	});
});
