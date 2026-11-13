// The pane menu: the column group (width presets and moving the column, in a
// strip only, through the router), the plane link, Close per view, and no
// separator with nothing under it.

import { TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as router from "../core/router";
import type { Desk } from "../desk/model";
import { COPY_LINK, PaneMenu, planeLink } from "./PaneMenu";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ID = "desk0001";

const STRIP = "strip1";
const LONE = "lone01";

/** A strip [a | b | c], and a plane item on e. */
const ROW: Desk = {
	name: "Row",
	items: [
		{
			id: STRIP,
			kind: "strip",
			columns: ["a", "b", "c"].map((plane) => ({
				panes: [{ share: 1, original: { plane, params: {} } }],
			})),
		},
		{ id: LONE, kind: "plane", original: { plane: "e", params: {} } },
	],
};

const ROLES = { home: "", settings: "", search: "" };

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
	router.resetRouter();
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	vi.restoreAllMocks();
});

function menu(path: string, planeId: string, onClose?: () => void, desk: Desk = ROW) {
	window.history.replaceState(null, "", path);
	act(() => {
		router.setDesks({ [ID]: desk });
		router.setRoles(ROLES);
	});
	act(() => {
		root.render(
			<TooltipProvider>
				<PaneMenu open planeId={planeId} meta={null} onChange={() => {}} onClose={onClose} />
			</TooltipProvider>,
		);
	});
}

const STRIP_URL = `/d/${ID}/${STRIP}`;

const items = () => [...document.querySelectorAll<HTMLElement>('[role^="menuitem"]')];
const item = (label: string) => items().find((i) => i.textContent?.trim() === label);

describe("the pane menu in a strip", () => {
	it("lists the link and Close, no width or move rows", () => {
		menu(STRIP_URL, "b", () => {});
		expect(items().map((i) => i.textContent?.trim())).toEqual([COPY_LINK, "Close"]);
	});

	it("lists the same on a plane item", () => {
		menu(`/d/${ID}/${LONE}`, "e", () => {});
		expect(items().map((i) => i.textContent?.trim())).toEqual([COPY_LINK, "Close"]);
	});
});

describe("the pane's own rows", () => {
	it("copies the plane link: the plane url with the pane's params, absolute", async () => {
		const writeText = vi.fn(() => Promise.resolve());
		Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
		const withParams: Desk = {
			...ROW,
			items: [{ id: LONE, kind: "plane", original: { plane: "a", params: { run: "42" } } }],
		};
		menu(`/d/${ID}/${LONE}`, "a", undefined, withParams);
		expect(planeLink("a")).toBe(`${window.location.origin}/p/a?run=42`);
		await act(async () => item(COPY_LINK)?.click());
		expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/p/a?run=42`);
	});

	it("closes through the pane's close", () => {
		const onClose = vi.fn();
		menu(STRIP_URL, "b", onClose);
		act(() => item("Close")?.click());
		expect(onClose).toHaveBeenCalledOnce();
	});

	it("has the link and no Close on a solo plane, ending on no separator", () => {
		menu("/p/p_solo", "p_solo");
		expect(items().map((i) => i.textContent?.trim())).toEqual([COPY_LINK]);
		const content = document.querySelector('[role="menu"]');
		expect(content?.lastElementChild?.getAttribute("role")).not.toBe("separator");
	});
});
