// The icon picker, rendered in jsdom: pick, search, keyboard, remove.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IconPicker } from "./IconPicker";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("unicode-emoji-json/data-by-group.json", () => ({
	default: [
		{
			name: "Animals & Nature",
			slug: "animals_nature",
			emojis: [
				{ emoji: "🐱", name: "cat face", slug: "cat_face", emoji_version: "0.6" },
				{ emoji: "🌱", name: "seedling", slug: "seedling", emoji_version: "0.6" },
			],
		},
	],
}));

let host: HTMLDivElement;
let root: Root;
const onPick = vi.fn();
const onRemove = vi.fn();

function render(value = "") {
	act(() => {
		root.render(<IconPicker value={value} onPick={onPick} onRemove={onRemove} />);
	});
}

const cell = (label: string) =>
	host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
const search = () => {
	const el = host.querySelector<HTMLInputElement>('input[type="search"]');
	if (!el) throw new Error("no search");
	return el;
};

/** Set a React-controlled input's value the way typing would. */
function type(text: string) {
	const el = search();
	const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
	act(() => {
		set?.call(el, text);
		el.dispatchEvent(new Event("input", { bubbles: true }));
	});
}

function key(el: Element, k: string) {
	act(() => {
		el.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }));
	});
}

beforeEach(() => {
	window.localStorage.clear();
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	onPick.mockClear();
	onRemove.mockClear();
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("icon picker", () => {
	it("opens on the icons with the caret in the search, and picks one", () => {
		render();
		expect(document.activeElement).toBe(search());
		act(() => cell("folder")?.click());
		expect(onPick).toHaveBeenCalledWith("lucide:folder");
	});

	it("filters by name and keyword, and Enter takes the first match", () => {
		render();
		type("stopwatch");
		const shown = [...host.querySelectorAll("button[data-cell]")].map((b) =>
			b.getAttribute("aria-label"),
		);
		expect(shown).toEqual(["timer"]);
		key(search(), "Enter");
		expect(onPick).toHaveBeenCalledWith("lucide:timer");
		type("no such icon");
		expect(host.textContent).toContain("Nothing matches");
	});

	it("moves through the grid with the arrows and picks with the focused cell", () => {
		render();
		type("chart");
		key(search(), "ArrowDown");
		const first = document.activeElement as HTMLElement;
		expect(first.dataset.cell).toBe("0");
		key(first, "ArrowRight");
		expect((document.activeElement as HTMLElement).dataset.cell).toBe("1");
		key(document.activeElement as Element, "ArrowUp");
		expect(document.activeElement).toBe(search());
	});

	it("marks the current icon and removes it", () => {
		render("lucide:cpu");
		expect(cell("cpu")?.getAttribute("aria-pressed")).toBe("true");
		const remove = [...host.querySelectorAll("button")].find((b) => b.textContent === "Remove");
		act(() => remove?.click());
		expect(onRemove).toHaveBeenCalled();
	});

	it("offers no remove when there is nothing to remove", () => {
		render();
		expect([...host.querySelectorAll("button")].some((b) => b.textContent === "Remove")).toBe(
			false,
		);
	});

	it("opens on the emoji for an emoji icon, and remembers picks", async () => {
		render("emoji:🌱");
		await act(async () => {
			await new Promise((r) => setTimeout(r, 0));
		});
		expect(cell("seedling")?.getAttribute("aria-pressed")).toBe("true");
		act(() => cell("cat face")?.click());
		expect(onPick).toHaveBeenCalledWith("emoji:🐱");
		expect(JSON.parse(window.localStorage.getItem("nuspace.icons.recent") ?? "[]")).toEqual([
			"emoji:🐱",
		]);
	});
});
