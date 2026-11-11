// The sidebar's pieces and its order, rendered in jsdom: the nav section
// through the roles, the section's options, the action row, the Specs, and
// the whole column top to bottom.

import { tree as store, TooltipProvider } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyDesksWrite, resetDesks } from "../core/desks";
import { focusedRoute, resetRouter } from "../core/router";
import { PLANE_MIME } from "../desk/dnd";
import { ActionRow } from "./ActionRow";
import { SidebarBody } from "./harness";
import { NAV_KEYS, NavSection } from "./NavSection";
import { rolePlanes, useNavShortcuts } from "./nav";
import { Sidebar } from "./Sidebar";
import { SidebarSection } from "./SidebarSection";
import { Specs, specGroups, specLines } from "./Specs";
import { patchSidebar } from "./state";
import { visibleRows } from "./tree";
import { childrenOf, coerceTree, ROOT_ID } from "./types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;

const ROLES = { home: "p-home", search: "p-search", settings: "p-settings" };

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
	window.history.replaceState({}, "", "/");
	window.localStorage.clear();
	resetRouter();
	resetDesks();
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

function draw(node: React.ReactNode) {
	act(() => {
		root.render(<TooltipProvider>{node}</TooltipProvider>);
	});
}

const rowOf = (key: string) => host.querySelector<HTMLElement>(`[data-key="${key}"]`);

describe("the nav section", () => {
	function Nav({ sel = "" }: { sel?: string }) {
		useNavShortcuts();
		return (
			<SidebarBody keys={NAV_KEYS}>
				<NavSection selKey={sel} />
			</SidebarBody>
		);
	}

	it("draws home, search and settings, untitled, their shortcuts shown", () => {
		draw(<Nav />);
		const rows = [...host.querySelectorAll<HTMLElement>('[role="treeitem"]')];
		expect(rows.map((r) => r.querySelector(".truncate")?.textContent)).toEqual([
			"Home",
			"Search",
			"Settings",
		]);
		expect(host.querySelector("h2, h3")).toBeNull();
		for (const r of rows) expect(r.querySelector('[data-slot="shortcut"], kbd')).not.toBeNull();
	});

	it("links each row to the plane its role points at, not a fixed id", () => {
		draw(<Nav />);
		expect(rowOf("nav:home")?.querySelector("a")).toBeNull();
		act(() => applyDesksWrite(null, { op: "set_roles", roles: ROLES }));
		expect(rowOf("nav:home")?.querySelector("a")?.getAttribute("href")).toBe("/p-home");
		expect(rowOf("nav:search")?.querySelector("a")?.getAttribute("href")).toBe("/p-search");
		expect(rowOf("nav:settings")?.querySelector("a")?.getAttribute("href")).toBe("/p-settings");
	});

	it("selects the row whose plane is focused", () => {
		act(() => applyDesksWrite(null, { op: "set_roles", roles: ROLES }));
		draw(<Nav sel="p-settings" />);
		expect(rowOf("nav:settings")?.getAttribute("aria-selected")).toBe("true");
		expect(rowOf("nav:home")?.getAttribute("aria-selected")).toBe("false");
	});

	it("drags a row's plane as the desk reads it, not only its link's url", () => {
		act(() => applyDesksWrite(null, { op: "set_roles", roles: ROLES }));
		draw(<Nav />);
		const data = new Map<string, string>();
		const e = new Event("dragstart", { bubbles: true, cancelable: true });
		Object.assign(e, {
			dataTransfer: { setData: (k: string, v: string) => data.set(k, v), effectAllowed: "" },
		});
		act(() => {
			rowOf("nav:settings")?.querySelector("a")?.dispatchEvent(e);
		});
		expect(JSON.parse(data.get(PLANE_MIME) ?? "")).toEqual({ plane: "p-settings", params: {} });
	});

	it("opens a role's plane from its key, through the roles", () => {
		draw(<Nav />);
		const press = (init: KeyboardEventInit) =>
			act(() => {
				window.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, ...init }));
			});
		press({ key: ",", metaKey: true });
		expect(window.location.pathname).toBe("/");
		act(() => {
			applyDesksWrite(null, { op: "set_desks", desks: {} });
			applyDesksWrite(null, { op: "set_roles", roles: ROLES });
		});
		press({ key: ",", metaKey: true });
		expect(focusedRoute()).toBe("p-settings");
		press({ key: "k", ctrlKey: true });
		expect(focusedRoute()).toBe("p-search");
		press({ key: "H", metaKey: true, shiftKey: true });
		expect(focusedRoute()).toBe("p-home");
	});

	it("leaves the role planes out of the Planes tree, by role", () => {
		const t = coerceTree([
			{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["p-home", "x"] },
			{ id: "p-home", kind: "plane", title: "Home", parent: ROOT_ID, children: ["kid"] },
			{ id: "kid", kind: "plane", title: "Kid", parent: "p-home", children: [] },
			{ id: "x", kind: "plane", title: "X", parent: ROOT_ID, children: [] },
		]);
		const rows = visibleRows(t, childrenOf(t, ROOT_ID), new Set(), rolePlanes(ROLES));
		expect(rows.map((r) => r.id)).toEqual(["kid", "x"]);
		expect(rolePlanes(null).size).toBe(0);
	});
});

describe("the section", () => {
	it("is only its body with no title", () => {
		draw(
			<SidebarSection id="t" label="Things">
				<span>body</span>
			</SidebarSection>,
		);
		expect(host.querySelector("section")?.getAttribute("aria-label")).toBe("Things");
		expect(host.querySelector("button")).toBeNull();
		expect(host.textContent).toBe("body");
	});

	it("shows a title, a count and its actions", () => {
		draw(
			<SidebarSection id="t" title="Things" count={3} actions={<button type="button">act</button>}>
				<span>body</span>
			</SidebarSection>,
		);
		expect(host.textContent).toBe("Things3actbody");
	});

	it("folds and unfolds from its title, when it folds", () => {
		const onFold = vi.fn();
		const at = (folded: boolean) =>
			draw(
				<SidebarSection id="t" title="Things" folded={folded} onFoldedChange={onFold}>
					<span>body</span>
				</SidebarSection>,
			);
		at(false);
		const title = host.querySelector<HTMLButtonElement>("button[aria-expanded]");
		expect(title?.getAttribute("aria-expanded")).toBe("true");
		act(() => title?.click());
		expect(onFold).toHaveBeenCalledWith(true);
		at(true);
		expect(host.textContent).not.toContain("body");
	});

	it("folds from its title, which opens nothing and is never selected", () => {
		const onFold = vi.fn();
		draw(
			<SidebarSection id="t" title="Desk" folded={false} onFoldedChange={onFold}>
				<span>body</span>
			</SidebarSection>,
		);
		const title = host.querySelector<HTMLButtonElement>("button[aria-expanded]");
		expect(title?.textContent).toBe("Desk");
		expect(title?.hasAttribute("aria-current")).toBe(false);
		expect(title?.parentElement?.className).not.toMatch(/(^|\s)bg-sidebar-a-fill/);
		act(() => title?.click());
		expect(onFold).toHaveBeenCalledWith(true);
	});
});

describe("the action row", () => {
	it("is a row with a plus, its label and its shortcut, pressed by click or Enter", () => {
		const onClick = vi.fn();
		draw(
			<SidebarBody keys={["new"]}>
				<ActionRow rowKey="new" label="New plane" keys={["mod", "N"]} onClick={onClick} />
			</SidebarBody>,
		);
		const row = rowOf("new");
		expect(row?.getAttribute("role")).toBe("treeitem");
		expect(row?.textContent).toContain("New plane");
		expect(row?.querySelector("svg")).not.toBeNull();
		act(() => row?.click());
		act(() => {
			row?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		});
		expect(onClick).toHaveBeenCalledTimes(2);
	});
});

describe("the specs", () => {
	const registered = [
		{ name: "nuverse.notes", label: "Notes", group: "", icon: "", description: "" },
		{ name: "nuverse.jobs", label: "Jobs", group: "", icon: "", description: "" },
		{ name: "nolabel", label: "Lost", group: "", icon: "", description: "" },
	];

	it("folds one group per package and makes a plane from an entry", () => {
		const groups = specGroups(registered);
		expect(groups.map((g) => g.pkg)).toEqual(["nuverse"]);
		const onToggle = vi.fn();
		const notify = vi.fn();
		const at = (expanded: string[]) => {
			const lines = specLines(groups, new Set(expanded));
			draw(
				<SidebarBody keys={lines.map((l) => l.key)}>
					<Specs
						groups={groups}
						lines={lines}
						expanded={new Set(expanded)}
						onToggle={onToggle}
						notify={notify}
					/>
				</SidebarBody>,
			);
		};
		at([]);
		act(() => rowOf("ext:nuverse")?.click());
		expect(onToggle).toHaveBeenCalledWith("ext:nuverse");
		at(["ext:nuverse"]);
		act(() => rowOf("ext:nuverse/nuverse.jobs")?.click());
		expect(notify).toHaveBeenCalledWith(
			"plane.create",
			expect.objectContaining({ spec: "nuverse.jobs", title: "Jobs", parent_id: ROOT_ID }),
		);
	});
});

describe("the sidebar", () => {
	it("stacks header, nav, desk folders, Planes, Specs, footer", () => {
		const path = ["sidebar"];
		act(() => {
			store.getState().write(path.map((seg) => [seg, null]));
			store.getState().setProps(path, {
				loaded: true,
				registered: [
					{ name: "nuverse.notes", label: "Notes", group: "", icon: "", description: "" },
				],
				tree: coerceTree([
					{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["x"] },
					{ id: "x", kind: "plane", title: "X", parent: ROOT_ID, children: [] },
				]),
			});
		});
		const item = (id: string, plane: string) => ({
			id,
			kind: "plane",
			original: { plane, params: {} },
		});
		act(() =>
			applyDesksWrite(null, {
				op: "set_desks",
				desks: { desk0001: { name: "Work", items: [item("item01", "x"), item("item02", "y")] } },
				order: ["desk0001"],
			}),
		);
		draw(<Sidebar path={path} />);
		const sections = [...host.querySelectorAll("section")].map((s) => s.getAttribute("aria-label"));
		expect(sections).toEqual(["Navigation", "Work", "Planes", "Specs"]);
		expect(host.querySelector('[data-key="new-desk"]')).toBeNull();
		expect(host.querySelector('[role="separator"]')).toBeNull();
		const planes = host.querySelector('section[aria-label="Planes"]');
		expect(planes?.querySelector('[data-key="new-plane"]')?.textContent).toContain("New plane");
		expect(planes?.querySelector('[data-key="x"]')).not.toBeNull();
		expect(host.textContent).not.toMatch(/rail/i);
	});

	it("focuses its body on a click in the empty room under the sections", () => {
		const path = ["sidebar"];
		act(() => {
			store.getState().write(path.map((seg) => [seg, null]));
			store.getState().setProps(path, {
				loaded: true,
				registered: [],
				tree: coerceTree([
					{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: [] },
				]),
			});
		});
		draw(<Sidebar path={path} />);
		const body = host.querySelector<HTMLElement>('nav[aria-label="Planes"]');
		const scroller = host.querySelector<HTMLElement>('[data-slot="scroll-area"]');
		act(() => scroller?.dispatchEvent(new MouseEvent("click", { bubbles: true })));
		expect(document.activeElement).toBe(body);
	});

	it("collapses every open plane from the Planes title, and has no expand all", () => {
		const path = ["sidebar"];
		act(() => {
			store.getState().write(path.map((seg) => [seg, null]));
			store.getState().setProps(path, {
				loaded: true,
				registered: [],
				tree: coerceTree([
					{ id: ROOT_ID, kind: "space", title: "", parent: ROOT_ID, children: ["x"] },
					{ id: "x", kind: "plane", title: "X", parent: ROOT_ID, children: ["x1"] },
					{ id: "x1", kind: "plane", title: "X1", parent: "x", children: [] },
				]),
			});
		});
		act(() => patchSidebar(path, { expanded: ["x"] }));
		draw(<Sidebar path={path} />);
		expect(rowOf("x1")).not.toBeNull();
		const planes = host.querySelector('section[aria-label="Planes"]');
		expect(planes?.querySelector('[aria-label^="Expand all"]')).toBeNull();
		expect(planes?.querySelector('[aria-label="New desk"]')).toBeNull();
		act(() =>
			planes?.querySelector<HTMLButtonElement>('[aria-label="Collapse all planes"]')?.click(),
		);
		expect(rowOf("x1")).toBeNull();
		expect(rowOf("x")).not.toBeNull();
	});
});
