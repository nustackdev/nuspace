// A plane in jsdom with fake documents: the harness the plane's tests share.
//
// A document is a fake `DocumentHandle` registered through the kit registry
// at the cell's address, as a MarkdownRef would: the plane never sees an
// editor, only the handle and the intents it reports, which a test says by
// hand (`say`). Everything else is the real plane: its local state, its
// input lines, its menu, the ops it sends (`notify`).
//
// Import it from a test file and the setup and teardown come with it.

import {
	type DocIntent,
	type DocumentHandle,
	type IntentListener,
	registerDocument,
	TooltipProvider,
	tree,
} from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, vi } from "vitest";
import type { PlaneHandle } from "./api";
import type { TitleIntent } from "./intents";
import { Plane } from "./Plane";
import { readEditor } from "./state";
import type { Sugar } from "./sugar";
import type { ActivePlane, Cell, CellSpec } from "./types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
// The slash menu's popover sizes itself with a ResizeObserver, which jsdom
// lacks, and jsdom lays nothing out.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
} as unknown as typeof ResizeObserver;
Element.prototype.scrollIntoView = () => {};
Range.prototype.getClientRects = () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect = () => new DOMRect();

export const VIEWER = ["viewer"];

/** A prose spec, installed but no class default. */
export const PLAIN: CellSpec[] = [
	{ name: "program", label: "Program" },
	{ name: "text", label: "Text", classes: ["prose"] },
];
/** The same, with the text spec the prose default. */
export const WITH_DEFAULT: CellSpec[] = [
	{ name: "program", label: "Program" },
	{ name: "text", label: "Text", classes: ["prose"], default_for: ["prose"] },
];

export let host: HTMLDivElement;
export let root: Root;
export const notify = vi.fn();
export const onTitle = vi.fn();
export const handle: { current: PlaneHandle | null } = { current: null };

export function render(
	cells: Cell[],
	{
		specs = PLAIN,
		editable = true,
		sugars = [],
		title = true,
	}: { specs?: CellSpec[]; editable?: boolean; sugars?: Sugar[]; title?: boolean } = {},
) {
	const plane: ActivePlane = {
		plane_id: "p1",
		title: "",
		meta: { editable, full_width: false, compact: false },
		cells,
	};
	act(() => {
		root.render(
			<TooltipProvider>
				<Plane
					viewerPath={VIEWER}
					plane={plane}
					cellSpecs={specs}
					editable={editable}
					wide={false}
					compact={false}
					notify={notify}
					handleRef={handle}
					onTitle={title ? onTitle : undefined}
					sugars={sugars}
				/>
			</TooltipProvider>,
		);
	});
}

export function cell(id: string, classes: string[] = ["prose"], error: string | null = null): Cell {
	return {
		id,
		name: id,
		source: "",
		has_ui: null,
		classes,
		status: { cell_id: id, state: error ? "failed" : "running", error, started_at: null },
	};
}

/** A document as the kit hands one over: commands spied, intents said by hand. */
export function fakeDoc(blank = true) {
	const listeners = new Set<IntentListener>();
	const doc: DocumentHandle = {
		focus: vi.fn(),
		blank: vi.fn(() => blank),
		markdown: vi.fn(() => ""),
		tail: vi.fn(() => ""),
		split: vi.fn(() => ""),
		append: vi.fn(),
		type: vi.fn(),
		commit: vi.fn(),
		hint: vi.fn(),
		onIntent(fn) {
			listeners.add(fn);
			return () => {
				listeners.delete(fn);
			};
		},
	};
	/** Report an intent, as the editor's intents plugin would. True when the host acted. */
	const say = (i: DocIntent) => {
		let acted = false;
		act(() => {
			for (const fn of listeners) if (fn(i)) acted = true;
		});
		return acted;
	};
	return { doc, say, listeners };
}

export const leaves: (() => void)[] = [];

/** Register `d` as cell `id`'s document, at the path a MarkdownRef inside it would. */
export function mountDoc(id: string, d = fakeDoc()) {
	act(() => {
		leaves.push(registerDocument([...VIEWER, "cells", id, "text"], d.doc));
	});
	return d;
}

/** The program's first write: a view node of `type` under the cell. */
export async function draw(id: string, type: string) {
	await act(async () => {
		tree.getState().write([["viewer"], ["cells"], [id], ["view", type]], {});
	});
}

export function press(el: Element, key: string, init: KeyboardEventInit = {}) {
	act(() => {
		el.dispatchEvent(
			new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init }),
		);
	});
}

/** Type into a field the way React hears it: native setter, then `input`. */
export function typeInto(el: HTMLInputElement, value: string) {
	const proto = Object.getPrototypeOf(el);
	act(() => {
		Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(el, value);
		el.dispatchEvent(new Event("input", { bubbles: true }));
	});
}

export const lines = () => [
	...host.querySelectorAll<HTMLInputElement>("input[aria-label='New cell']"),
];
export const endLine = () => lines().at(-1) as HTMLInputElement;
export const planeRoot = () => endLine().parentElement?.parentElement as HTMLElement;
export const row = (id: string) =>
	host.querySelector<HTMLElement>(`[data-cell="${id}"]`) as HTMLElement;
export const menu = () => document.querySelector("[role='listbox'][aria-label='Insert a cell']");
export const selected = () => readEditor(VIEWER, "p1").selected;
export const ops = () => notify.mock.calls.map(([op, args]) => [op, args.cell_id ?? args.cell_ids]);

export const title = (i: TitleIntent) => {
	let acted = false;
	act(() => {
		acted = handle.current?.title(i) ?? false;
	});
	return acted;
};

beforeEach(() => {
	tree.getState().write([["viewer"]], {});
	host = document.createElement("div");
	document.body.appendChild(host);
	root = createRoot(host);
	notify.mockClear();
	onTitle.mockClear();
});

afterEach(() => {
	act(() => {
		for (const leave of leaves.splice(0)) leave();
		root.unmount();
	});
	host.remove();
	tree.getState().remove(VIEWER);
});
