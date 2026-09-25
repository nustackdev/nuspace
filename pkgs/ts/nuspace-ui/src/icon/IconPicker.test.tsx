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

/** Render, and let the emoji load inside the act so no update lands outside it. */
async function render(value = "") {
	await act(async () => {
		root.render(<IconPicker value={value} onPick={onPick} onRemove={onRemove} />);
		await new Promise((r) => setTimeout(r, 0));
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

/** Let the emoji's dynamic import land. */
async function settle() {
	await act(async () => {
		await new Promise((r) => setTimeout(r, 0));
	});
}

const tabs = () => [...host.querySelectorAll('[role="tab"]')].map((t) => t.textContent);

/** Switch to the Icons tab the way a click does: Radix tabs go on mousedown. */
function toIcons() {
	const tab = [...host.querySelectorAll('[role="tab"]')].find((t) => t.textContent === "Icons");
	act(() => {
		tab?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, button: 0 }));
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
	it("opens on the emoji first, loading them, with the caret in the search", async () => {
		act(() => {
			root.render(<IconPicker value="" onPick={onPick} onRemove={onRemove} />);
		});
		expect(tabs()).toEqual(["Emoji", "Icons"]);
		expect(document.activeElement).toBe(search());
		expect(host.querySelector('[role="status"]')?.getAttribute("aria-label")).toBe("Loading emoji");
		await settle();
		expect(host.querySelector('[role="status"]')).toBeNull();
		act(() => cell("cat face")?.click());
		expect(onPick).toHaveBeenCalledWith("emoji:🐱");
	});

	it("picks an icon from the icons tab", async () => {
		await render();
		toIcons();
		act(() => cell("folder")?.click());
		expect(onPick).toHaveBeenCalledWith("lucide:folder");
	});

	it("filters by name and keyword, and Enter takes the first match", async () => {
		await render();
		toIcons();
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

	it("moves through the grid with the arrows and picks with the focused cell", async () => {
		await render();
		toIcons();
		type("chart");
		key(search(), "ArrowDown");
		const first = document.activeElement as HTMLElement;
		expect(first.dataset.cell).toBe("0");
		key(first, "ArrowRight");
		expect((document.activeElement as HTMLElement).dataset.cell).toBe("1");
		key(document.activeElement as Element, "ArrowUp");
		expect(document.activeElement).toBe(search());
	});

	it("opens on the icons for a pack icon, marks it and removes it", async () => {
		await render("lucide:cpu");
		expect(cell("cpu")?.getAttribute("aria-pressed")).toBe("true");
		const remove = [...host.querySelectorAll("button")].find((b) => b.textContent === "Remove");
		act(() => remove?.click());
		expect(onRemove).toHaveBeenCalled();
	});

	it("offers no remove when there is nothing to remove", async () => {
		await render();
		expect([...host.querySelectorAll("button")].some((b) => b.textContent === "Remove")).toBe(
			false,
		);
	});

	it("marks an emoji icon, and remembers picks", async () => {
		await render("emoji:🌱");
		expect(cell("seedling")?.getAttribute("aria-pressed")).toBe("true");
		act(() => cell("cat face")?.click());
		expect(onPick).toHaveBeenCalledWith("emoji:🐱");
		expect(JSON.parse(window.localStorage.getItem("nuspace.icons.recent") ?? "[]")).toEqual([
			"emoji:🐱",
		]);
	});
});
