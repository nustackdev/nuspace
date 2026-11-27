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
import { applyPaneWrite, panePath } from "../../pane/state";
import type { Cell } from "../../plane/types";
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

	it("shows desktop's facts, the id and the key, read-only, then Delete", () => {
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
		expect(actions(sheet)).toEqual(["Delete plane"]);
		expect(document.querySelector(`${sheet} input`)).toBeNull();
	});

	it("offers no delete on a system plane", () => {
		land({ ...HEAD, system: true, key: "" });
		open();
		expect(actions(sheet)).toEqual([]);
		expect(details(sheet).map((d) => d.split(":")[0])).toEqual(["ID"]);
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
