// The plane's icon beside its title, rendered in jsdom: always there, and a
// click opens the picker.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TitleIcon } from "./TitleIcon";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("unicode-emoji-json/data-by-group.json", () => ({
	default: [
		{
			name: "Animals & Nature",
			slug: "animals_nature",
			emojis: [{ emoji: "🐱", name: "cat face", slug: "cat_face", emoji_version: "0.6" }],
		},
	],
}));

let host: HTMLDivElement;
let root: Root;
const onChange = vi.fn();

function render(value: unknown, registered = "") {
	act(() => {
		root.render(
			<TooltipProvider>
				<TitleIcon value={value} registered={registered} onChange={onChange} />
			</TooltipProvider>,
		);
	});
}

const button = () => {
	const el = host.querySelector<HTMLButtonElement>('button[aria-label="Change icon"]');
	if (!el) throw new Error("no icon button");
	return el;
};

/** The glyph drawn: a lucide svg's class names it, an emoji is its text. */
const drawn = () => {
	const svg = button().querySelector("svg");
	return svg ? (svg.getAttribute("class") ?? "") : (button().textContent ?? "");
};

/** Radix opens a popover on a click. Let the picker's emoji load inside the act. */
async function open() {
	await act(async () => {
		button().click();
		await new Promise((r) => setTimeout(r, 0));
	});
}

/** A button in the open picker, by its label or its text. */
const inPicker = (name: string) =>
	[...document.body.querySelectorAll<HTMLButtonElement>("button")].find(
		(b) => b.getAttribute("aria-label") === name || b.textContent === name,
	);

beforeEach(() => {
	window.localStorage.clear();
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	onChange.mockClear();
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("title icon", () => {
	it("always shows a button, falling back to the page icon", () => {
		render(undefined);
		expect(button().type).toBe("button");
		expect(drawn()).toContain("lucide-file-text");
	});

	it("falls back to the registered Plane's icon before the page icon", () => {
		render("", "folder");
		expect(drawn()).toContain("lucide-folder");
	});

	it("draws the plane's own icon, an emoji as text", () => {
		render("emoji:🐱", "folder");
		expect(drawn()).toBe("🐱");
	});

	it("opens the picker on a click, and a pick sends the icon", async () => {
		render("");
		await open();
		expect(button().getAttribute("aria-expanded")).toBe("true");
		act(() => inPicker("cat face")?.click());
		expect(onChange).toHaveBeenCalledWith("emoji:🐱");
		expect(button().getAttribute("aria-expanded")).toBe("false");
	});

	it("sends an empty icon on remove", async () => {
		render("lucide:cpu");
		await open();
		act(() => inPicker("Remove")?.click());
		expect(onChange).toHaveBeenCalledWith("");
	});
});
