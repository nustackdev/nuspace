// The identity block, rendered in jsdom: the id copies, the key saves on
// Enter or Save, an empty key removes it, and a read-only plane only copies.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Identity } from "./Identity";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;
const onSave = vi.fn();
const onClose = vi.fn();
const writeText = vi.fn(() => Promise.resolve());

function render(value: string, editable = true) {
	act(() => {
		root.render(
			<TooltipProvider>
				<Identity
					kind="cell"
					id="c_1"
					value={value}
					onSave={editable ? onSave : undefined}
					onClose={onClose}
				/>
			</TooltipProvider>,
		);
	});
}

const byLabel = (name: string) => host.querySelector<HTMLButtonElement>(`[aria-label="${name}"]`);
const field = () => {
	const el = host.querySelector<HTMLInputElement>('input[aria-label="cell key"]');
	if (!el) throw new Error("no key field");
	return el;
};
const saveButton = () => [...host.querySelectorAll("button")].find((b) => b.textContent === "Save");

function type(text: string) {
	const input = field();
	const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
	act(() => {
		set?.call(input, text);
		input.dispatchEvent(new Event("input", { bubbles: true }));
	});
}

function press(key: string) {
	act(() => {
		field().dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
	});
}

beforeEach(() => {
	host = document.createElement("div");
	document.body.appendChild(host);
	root = createRoot(host);
	onSave.mockReset();
	onClose.mockReset();
	writeText.mockClear();
	Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("Identity", () => {
	it("shows the id and copies it", async () => {
		render("summary");
		expect(host.querySelector("[data-identity-id]")?.textContent).toBe("c_1");
		await act(async () => {
			byLabel("Copy cell id")?.click();
		});
		expect(writeText).toHaveBeenCalledWith("c_1");
	});

	it("copies the key, and has nothing to copy without one", async () => {
		render("summary");
		await act(async () => {
			byLabel("Copy cell key")?.click();
		});
		expect(writeText).toHaveBeenCalledWith("summary");
		render("");
		expect(field().value).toBe("");
		expect(byLabel("Copy cell key")?.disabled).toBe(true);
	});

	it("saves a new key on Enter and on Save", () => {
		render("summary");
		expect(saveButton()?.disabled).toBe(true);
		type("digest");
		press("Enter");
		expect(onSave).toHaveBeenLastCalledWith("digest");
		type("other");
		act(() => saveButton()?.click());
		expect(onSave).toHaveBeenLastCalledWith("other");
	});

	it("removes the key when saved empty", () => {
		render("summary");
		type("");
		press("Enter");
		expect(onSave).toHaveBeenCalledWith("");
	});

	it("says a misspelled key as it is typed, and will not save it", () => {
		render("summary");
		const error = () => host.querySelector('[role="alert"]')?.textContent ?? "";
		type("two");
		expect(error()).toBe("");
		type("two words");
		expect(error()).toBe("Use letters, digits, _ and -");
		expect(field().getAttribute("aria-invalid")).toBe("true");
		expect(saveButton()?.disabled).toBe(true);
		press("Enter");
		expect(onSave).not.toHaveBeenCalled();
		type("two_words");
		expect(error()).toBe("");
		expect(saveButton()?.disabled).toBe(false);
	});

	it("enables Save only for a changed, valid key, every keystroke and after a save lands", () => {
		render("summary");
		const enabled = () => saveButton()?.disabled === false;
		expect(enabled()).toBe(false);
		type("summary2");
		expect(enabled()).toBe(true);
		type("summary");
		expect(enabled()).toBe(false);
		type("");
		expect(enabled()).toBe(true);
		type("digest");
		act(() => saveButton()?.click());
		expect(onSave).toHaveBeenLastCalledWith("digest");
		// The new key arrives from the server: nothing left to save.
		render("digest");
		expect(field().value).toBe("digest");
		expect(enabled()).toBe(false);
	});

	it("saves nothing without a key to remove", () => {
		render("");
		expect(saveButton()?.disabled).toBe(true);
		press("Enter");
		expect(onSave).not.toHaveBeenCalled();
	});

	it("closes on Escape", () => {
		render("summary");
		press("Escape");
		expect(onClose).toHaveBeenCalled();
	});

	it("only shows and copies on a read-only plane", () => {
		render("summary", false);
		expect(field().readOnly).toBe(true);
		expect(saveButton()).toBeUndefined();
		expect(byLabel("Copy cell key")).not.toBeNull();
	});
});
