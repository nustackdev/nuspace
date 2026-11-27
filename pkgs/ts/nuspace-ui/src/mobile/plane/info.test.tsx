// The facts the phone shows, read-only: a plane's in the ⋯ sheet, a cell's
// over its long-press actions. The answers land on the pane node as they do
// for desktop's menus; the rows are desktop's.
//
// The sheet itself is the kit's and drawn plainly here: open, its title and
// its body inline. Its drawer (vaul) and scroll lock are the kit's to test.

import { TooltipProvider, TouchProvider, tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { notifyOp } from "../../core/wire";
import { applyPaneWrite, panePath } from "../../pane/state";
import type { Cell } from "../../plane/types";
import { openAddPlane } from "../../sidebar/add";
import { CellSheet } from "./CellSheet";
import { PlaneInfoSheet } from "./PlaneInfoSheet";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("@nustackdev/ui-kit", async (kit) => ({
	...(await kit<typeof import("@nustackdev/ui-kit")>()),
	BottomSheet: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
		open ? children : null,
	BottomSheetContent: ({
		title,
		label: _label,
		children,
		...rest
	}: {
		title?: React.ReactNode;
		label?: string;
		children: React.ReactNode;
	}) => (
		<div {...rest}>
			<h2>{title}</h2>
			{children}
		</div>
	),
}));

vi.mock("../../core/wire", async (wire) => ({
	...(await wire<typeof import("../../core/wire")>()),
	notifyOp: vi.fn(),
}));

vi.mock("../../sidebar/add", async (add) => ({
	...(await add<typeof import("../../sidebar/add")>()),
	openAddPlane: vi.fn(),
}));

const VIEWER = ["viewer"];
const PLANE = "p_jobs";

const HEAD = {
	op: "set_head",
	title: "Jobs",
	icon: "emoji:🌱",
	key: "jobs",
	system: false,
	editable: true,
	width: "board",
};

let host: HTMLDivElement;
let root: Root;

/** One write onto the pane's node, through its own write body. */
function land(payload: Record<string, unknown>) {
	act(() => {
		const path = panePath(VIEWER, PLANE);
		tree.getState().write(path.map((s) => [s, null]));
		const props = { ...(tree.getState().getIn(path)?.props ?? {}) };
		applyPaneWrite(props, payload);
		tree.getState().setProps(path, props);
	});
}

function draw(node: React.ReactNode) {
	act(() => {
		root.render(
			<TouchProvider value>
				<TooltipProvider>{node}</TooltipProvider>
			</TouchProvider>,
		);
	});
}

/** The label and value rows a sheet shows, as "label: value". */
function details(sheet: string): string[] {
	const el = document.querySelector(sheet);
	return [...(el?.querySelectorAll("dt") ?? [])].map(
		(dt) => `${dt.textContent}: ${dt.nextElementSibling?.textContent ?? ""}`,
	);
}

const actions = (sheet: string) =>
	[...(document.querySelector(sheet)?.querySelectorAll("[role=menuitem]") ?? [])].map((e) =>
		e.textContent?.trim(),
	);

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().remove(VIEWER);
});

describe("the plane's facts", () => {
	const sheet = "[data-plane-info-sheet]";
	const open = () =>
		draw(<PlaneInfoSheet viewerPath={VIEWER} planeId={PLANE} open onClose={() => {}} />);

	it("shows desktop's facts, the id and the key, read-only, then the pane menu's actions", () => {
		land(HEAD);
		open();
		// Asked for as it opened: the answer lands after.
		land({
			op: "set_plane_info",
			info: {
				plane_id: PLANE,
				label: "Jobs",
				cells: 3,
				children: 2,
				created_at: 10,
				run: { id: "" },
			},
		});
		expect(details(sheet).map((d) => d.split(":")[0])).toEqual([
			"Cells",
			"Planes",
			"Edited",
			"Created",
			"ID",
			"Key",
		]);
		expect(details(sheet)).toContain(`ID: ${PLANE}`);
		expect(details(sheet)).toContain("Key: @jobs");
		expect(document.querySelector(sheet)?.textContent).toContain("Not running in this pane");
		expect(actions(sheet)).toEqual([
			"Add plane inside",
			"Rename",
			"Change icon",
			"Restart plane",
			"Delete plane",
		]);
		expect(document.querySelector(`${sheet} input`)).toBeNull();
	});

	it("offers no delete on a system plane", () => {
		land({ ...HEAD, system: true, key: "" });
		open();
		expect(actions(sheet)).toEqual(["Add plane inside", "Rename", "Change icon", "Restart plane"]);
		expect(details(sheet).map((d) => d.split(":")[0])).toEqual(["ID"]);
	});

	it("restarts the plane on its own node and closes", () => {
		land(HEAD);
		const onClose = vi.fn();
		draw(<PlaneInfoSheet viewerPath={VIEWER} planeId={PLANE} open onClose={onClose} />);
		vi.mocked(notifyOp).mockClear();
		act(() => {
			(document.querySelector(`${sheet} [data-action=restart]`) as HTMLElement).click();
		});
		expect(notifyOp).toHaveBeenCalledWith(panePath(VIEWER, PLANE), "plane.restart", {});
		expect(onClose).toHaveBeenCalledOnce();
	});

	const tap = (action: string) =>
		act(() => {
			(document.querySelector(`${sheet} [data-action=${action}]`) as HTMLElement).click();
		});

	it("adds a plane inside this one, opened in this pane", () => {
		land(HEAD);
		const onClose = vi.fn();
		draw(<PlaneInfoSheet viewerPath={VIEWER} planeId={PLANE} open onClose={onClose} />);
		tap("inside");
		expect(openAddPlane).toHaveBeenCalledWith({ parent: PLANE, pane: PLANE });
		expect(onClose).toHaveBeenCalledOnce();
	});

	it("renames in a step of its own, the pane's title at once", () => {
		land(HEAD);
		const onClose = vi.fn();
		draw(<PlaneInfoSheet viewerPath={VIEWER} planeId={PLANE} open onClose={onClose} />);
		tap("rename");
		expect(document.querySelector(sheet)?.getAttribute("data-plane-info-sheet")).toBe("rename");
		const input = document.querySelector(`${sheet} input`) as HTMLInputElement;
		expect(input.value).toBe("Jobs");
		vi.mocked(notifyOp).mockClear();
		act(() => {
			const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
			set?.call(input, "  Chores ");
			input.dispatchEvent(new Event("input", { bubbles: true }));
		});
		act(() => {
			(document.querySelector(`${sheet} form`) as HTMLFormElement).requestSubmit();
		});
		expect(notifyOp).toHaveBeenCalledWith(panePath(VIEWER, PLANE), "plane.rename", {
			title: "Chores",
		});
		expect(onClose).toHaveBeenCalledOnce();
	});

	it("changes the icon in the kit picker, Remove putting the default back", () => {
		land(HEAD);
		const onClose = vi.fn();
		draw(<PlaneInfoSheet viewerPath={VIEWER} planeId={PLANE} open onClose={onClose} />);
		tap("icon");
		expect(document.querySelector(sheet)?.getAttribute("data-plane-info-sheet")).toBe("icon");
		vi.mocked(notifyOp).mockClear();
		const remove = [...document.querySelectorAll(`${sheet} button`)].find(
			(b) => b.textContent?.trim() === "Remove",
		) as HTMLElement;
		act(() => remove.click());
		expect(notifyOp).toHaveBeenCalledWith(panePath(VIEWER, PLANE), "plane.icon", {
			icon: "lucide:file-text",
		});
		expect(onClose).toHaveBeenCalledOnce();
	});
});

describe("the cell's facts", () => {
	const sheet = "[data-cell-sheet]";
	const cell: Cell = {
		id: "c1",
		name: "welcome",
		key: "",
		source: "",
		draws: true,
		classes: [],
		status: { state: "idle", error: null },
	} as unknown as Cell;

	it("shows desktop's facts and last run over the actions", () => {
		land(HEAD);
		land({
			op: "set_cell_info",
			info: {
				cell_id: "c1",
				name: "welcome",
				version: 2,
				created_at: 10,
				run: {
					id: "r1",
					version: 2,
					by: "nav",
					backend: "async",
					started_at: 20,
					ended_at: 21,
					exit: "ok",
				},
			},
		});
		draw(
			<CellSheet
				panePath={panePath(VIEWER, PLANE)}
				cell={cell}
				pressed={{ id: "c1", step: "actions" }}
				editable
				onPressed={() => {}}
				onRestart={() => {}}
				onSource={() => {}}
				onDelete={() => {}}
			/>,
		);
		const labels = details(sheet).map((d) => d.split(":")[0]);
		expect(labels.slice(0, 4)).toEqual(["Name", "Version", "Edited", "Created"]);
		expect(labels).toContain("Exit");
		expect(details(sheet)).toContain("By: nav on async");
		expect(actions(sheet)).toEqual(["Restart", "Copy id", "View source", "Delete"]);
		// The facts come first, and nothing edits the key.
		const el = document.querySelector(sheet);
		const dl = el?.querySelector("dl");
		const menu = el?.querySelector("[role=menu]");
		expect(
			dl && menu && dl.compareDocumentPosition(menu) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
		expect(el?.textContent).not.toContain("Key");
	});
});
