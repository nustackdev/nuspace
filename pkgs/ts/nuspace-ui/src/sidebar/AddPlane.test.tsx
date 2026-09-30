// The Add plane popup, rendered in jsdom: picking an entry sends the create
// and opens the new Plane's pane. What it runs on is the server's business.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { replacePane } from "../core/router";
import { AddPlane } from "./AddPlane";
import { closeAddPlane, openAddPlane } from "./add";
import { ROOT_ID } from "./types";

vi.mock("../core/router", () => ({ focusPane: vi.fn(), replacePane: vi.fn() }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;
Element.prototype.scrollIntoView ??= () => {};

const registered = [
	{ name: "plain", label: "Plain", icon: "", description: "" },
	{ name: "jobs", label: "Jobs", icon: "", description: "" },
];

let host: HTMLDivElement;
let root: Root;
const notify = vi.fn();

beforeEach(() => {
	notify.mockClear();
	vi.mocked(replacePane).mockClear();
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	act(() => root.render(<AddPlane registered={registered} notify={notify} reveal={() => {}} />));
});

afterEach(() => {
	act(() => closeAddPlane());
	act(() => root.unmount());
	host.remove();
});

const item = (label: string) =>
	[...document.querySelectorAll<HTMLElement>('[cmdk-item=""]')].find((i) =>
		i.textContent?.includes(label),
	);

describe("AddPlane", () => {
	it("sends the create for the entry picked and opens its pane", () => {
		act(() => openAddPlane({ parent: ROOT_ID }));
		act(() => item("Jobs")?.click());
		expect(notify).toHaveBeenCalledTimes(1);
		const [op, args] = notify.mock.calls[0];
		expect(op).toBe("plane.create");
		expect(args).toEqual({
			plane_id: expect.any(String),
			parent_id: ROOT_ID,
			made_by: "jobs",
			title: "Jobs",
		});
		expect(replacePane).toHaveBeenCalledWith(args.plane_id);
		expect(document.querySelector('[cmdk-item=""]')).toBeNull();
	});

	it("names a plain Plane Untitled", () => {
		act(() => openAddPlane({ parent: ROOT_ID }));
		act(() => item("Plain")?.click());
		expect(notify).toHaveBeenCalledWith(
			"plane.create",
			expect.objectContaining({ made_by: "plain", title: "Untitled" }),
		);
	});
});
