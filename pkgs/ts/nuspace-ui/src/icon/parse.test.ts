import { describe, expect, it } from "vitest";
import { shapeEmoji } from "./emoji";
import { PACK_GROUPS, PACK_ICONS } from "./pack";
import { DEFAULT_ICON, formatIcon, parseIcon, planeIcon } from "./parse";

describe("icon spelling", () => {
	it("reads the pack, emoji, and a bare lucide name", () => {
		expect(parseIcon("lucide:folder")).toEqual({ kind: "lucide", name: "folder" });
		expect(parseIcon("folder")).toEqual({ kind: "lucide", name: "folder" });
		expect(parseIcon("FileText")).toEqual({ kind: "lucide", name: "file-text" });
		expect(parseIcon("Gamepad2")).toEqual({ kind: "lucide", name: "gamepad-2" });
		expect(parseIcon("emoji:🚀")).toEqual({ kind: "emoji", char: "🚀" });
		expect(parseIcon(" emoji:👩🏽‍💻 ")).toEqual({ kind: "emoji", char: "👩🏽‍💻" });
	});

	it("reads anything else as no icon", () => {
		for (const raw of [
			"",
			"  ",
			"emoji:",
			"lucide:",
			"lucide:no-such",
			"svg:x",
			7,
			null,
			undefined,
		]) {
			expect(parseIcon(raw)).toBeNull();
		}
	});

	it("round trips through the stored spelling", () => {
		for (const raw of ["lucide:cpu", "emoji:✨"]) expect(formatIcon(parseIcon(raw))).toBe(raw);
		expect(formatIcon(parseIcon("layers"))).toBe("lucide:layers");
		expect(formatIcon(null)).toBe("");
	});

	it("falls back from the plane's own to its registered Plane's to the default", () => {
		expect(planeIcon("emoji:🌱", "cpu")).toEqual({ kind: "emoji", char: "🌱" });
		expect(planeIcon("", "cpu")).toEqual({ kind: "lucide", name: "cpu" });
		expect(planeIcon("lucide:gone", "gone too")).toEqual(DEFAULT_ICON);
		expect(planeIcon(undefined)).toEqual(DEFAULT_ICON);
	});
});

describe("icon pack", () => {
	it("holds every icon nuspace and the shipped Planes name, once each", () => {
		for (const name of ["file-text", "folder", "list", "activity", "briefcase", "cpu", "layers"]) {
			expect(parseIcon(name)).not.toBeNull();
		}
		const names = PACK_ICONS.map((i) => i.name);
		expect(new Set(names).size).toBe(names.length);
		expect(names.length).toBeGreaterThanOrEqual(60);
		expect(names.length).toBeLessThanOrEqual(120);
		for (const { id } of PACK_GROUPS) expect(PACK_ICONS.some((i) => i.group === id)).toBe(true);
	});
});

describe("emoji data", () => {
	it("keeps names, sentence-cases groups, and drops what fonts cannot draw yet", () => {
		const got = shapeEmoji([
			{
				name: "Smileys & Emotion",
				emojis: [
					{ emoji: "😀", name: "grinning face", emoji_version: "1.0" },
					{ emoji: "🫩", name: "face with bags under eyes", emoji_version: "16.0" },
				],
			},
			{ name: "Flags", emojis: [{ emoji: "🇦🇶", name: "flag Antarctica", emoji_version: "17.0" }] },
		]);
		expect(got).toEqual([
			{ label: "Smileys & emotion", emojis: [{ char: "😀", name: "grinning face" }] },
		]);
	});
});
