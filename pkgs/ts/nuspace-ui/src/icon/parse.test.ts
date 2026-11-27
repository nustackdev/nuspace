import { describe, expect, it } from "vitest";
import { DEFAULT_ICON, planeIcon } from "./parse";

describe("plane icon", () => {
	it("shows the plane's own icon, the default only for one that does not read", () => {
		expect(planeIcon("emoji:🌱")).toEqual({ kind: "emoji", char: "🌱" });
		expect(planeIcon("lucide:cpu")).toEqual({ kind: "lucide", name: "cpu" });
		expect(planeIcon("FileText")).toEqual({ kind: "lucide", name: "file-text" });
		expect(planeIcon("lucide:gone")).toEqual(DEFAULT_ICON);
		expect(planeIcon(undefined)).toEqual(DEFAULT_ICON);
	});

	it("defaults to the page icon", () => {
		expect(DEFAULT_ICON).toEqual({ kind: "lucide", name: "file-text" });
	});
});
