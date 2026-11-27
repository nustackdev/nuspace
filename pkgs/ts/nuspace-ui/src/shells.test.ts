// The shell split: a touch device gets the mobile shell, anything else the
// desktop one, each its own module.

import { describe, expect, it } from "vitest";
import { loadShell, shellFor } from "./shells";

describe("shellFor", () => {
	it("gives a touch device the mobile shell", () => {
		expect(shellFor(true)).toBe("mobile");
	});
	it("gives everything else the desktop shell", () => {
		expect(shellFor(false)).toBe("desktop");
	});
});

describe("loadShell", () => {
	// Each import transforms a whole shell, cold: slow beside other test files.
	it("loads each shell's own root", { timeout: 30_000 }, async () => {
		const mobile = await loadShell("mobile");
		const desktop = await loadShell("desktop");
		expect(mobile.name).toBe("MobileApp");
		expect(desktop.name).toBe("App");
	});
});
