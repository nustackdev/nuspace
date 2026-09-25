// The tab's title and favicon: what the focused plane makes them, and the
// emoji favicon's data URL.

import { describe, expect, it } from "vitest";
import { applyTab, DEFAULT_TAB, emojiFavicon, tabOf } from "./tab";

function svgOf(url: string): string {
	expect(url.startsWith("data:image/svg+xml,")).toBe(true);
	return decodeURIComponent(url.slice("data:image/svg+xml,".length));
}

describe("tab", () => {
	it("shows the defaults with no plane", () => {
		expect(tabOf(null)).toEqual({ title: "nuspace", emoji: null });
	});

	it("shows the plane's title, the pane's fallback when empty", () => {
		expect(tabOf({ title: "Notes", icon: "" }).title).toBe("Notes");
		expect(tabOf({ title: "", icon: "" }).title).toBe("Untitled");
	});

	it("takes an emoji icon, keeps the logo for lucide or none", () => {
		expect(tabOf({ title: "a", icon: "emoji:🚀" }).emoji).toBe("🚀");
		expect(tabOf({ title: "a", icon: "lucide:folder" }).emoji).toBeNull();
		expect(tabOf({ title: "a", icon: "folder" }).emoji).toBeNull();
		expect(tabOf({ title: "a", icon: undefined }).emoji).toBeNull();
		expect(tabOf({ title: "a", icon: "" }, "emoji:🌱").emoji).toBe("🌱");
		expect(tabOf({ title: "a", icon: "lucide:folder" }, "emoji:🌱").emoji).toBeNull();
	});

	it("draws the emoji as one svg text", () => {
		const svg = svgOf(emojiFavicon("👩🏽‍💻"));
		expect(svg).toContain('viewBox="0 0 100 100"');
		expect(svg).toMatch(/<text [^>]*>👩🏽‍💻<\/text>/);
		expect(svgOf(emojiFavicon("<&>"))).toContain(">&#60;&#38;&#62;</text>");
	});

	it("swaps the icon links and puts the logo back", () => {
		document.head.innerHTML =
			'<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />' +
			'<link rel="apple-touch-icon" href="/apple-icon.png" />';
		const link = document.head.querySelector<HTMLLinkElement>('link[rel="icon"]');
		const apple = document.head.querySelector<HTMLLinkElement>('link[rel="apple-touch-icon"]');

		applyTab({ title: "Notes", emoji: "🚀" });
		expect(document.title).toBe("Notes");
		expect(link?.getAttribute("href")).toBe(emojiFavicon("🚀"));
		expect(link?.type).toBe("image/svg+xml");
		expect(apple?.getAttribute("href")).toBe("/apple-icon.png");

		applyTab(DEFAULT_TAB);
		expect(document.title).toBe("nuspace");
		expect(link?.getAttribute("href")).toBe("/favicon-32.png");
		expect(link?.type).toBe("image/png");
		expect(link?.getAttribute("sizes")).toBe("32x32");
	});
});
