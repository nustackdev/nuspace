// A plane in jsdom with fake markdown editors: the harness the plane's tests share.
//
// An editor is a fake `MarkdownHandle` registered with the kit at the cell's
// address, as a MarkdownRef would: the plane never sees an editor's DOM,
// only the handle and the intents it reports, which a test says by hand
// (`say`). Everything else is the real plane: its local state, its
// input lines, its menu, the ops it sends (`notify`).
//
// Import it from a test file and the setup and teardown come with it.

import type { Path } from "@nustackdev/ui-core";
import {
	type IntentListener,
	type MarkdownHandle,
	type MarkdownIntent,
	pathKey,
	register,
	registerMarkdown,
	TooltipProvider,
	tree,
} from "@nustackdev/ui-kit";
import { act, useEffect } from "react";
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
/** The pane the plane under test is drawn in: its editor state lives here. */
export const PANE = ["viewer", "panes", "p1"];

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
		focused = false,
	}: {
		specs?: CellSpec[];
		editable?: boolean;
		sugars?: Sugar[];
		title?: boolean;
		focused?: boolean;
	} = {},
) {
	const plane: ActivePlane = {
		plane_id: "p1",
		title: "",
		meta: { editable, width: "page", key: "" },
		cells,
	};
	act(() => {
		root.render(
			<TooltipProvider>
				<Plane
					viewerPath={VIEWER}
					panePath={PANE}
					plane={plane}
					cellSpecs={specs}
					editable={editable}
					width="page"
					notify={notify}
					handleRef={handle}
					onTitle={title ? onTitle : undefined}
					focused={focused}
					sugars={sugars}
				/>
			</TooltipProvider>,
		);
	});
}

export function cell(id: string, classes: string[] = ["prose"], error: string | null = null): Cell {
	return {
		id,
		key: "",
		source: "",
		draws: null,
		classes,
		status: { cell_id: id, state: error ? "failed" : "running", error },
	};
}

/**
 * A markdown editor's handle as the kit hands one over: commands spied,
 * intents said by hand. The kit hands out a handle only while its editor is
 * editable, so a fake is always one that takes commands. `saved` answers at once, as the kit's
 * does with nothing unsaved; `hold()` makes it wait for `stored()`, the read
 * coming back from Nu, or `lose()`, the editor or its node gone first.
 */
export function fakeDoc(blank = true) {
	const listeners = new Set<IntentListener>();
	const waiting: { fn: () => void; lost?: () => void }[] = [];
	const store = { held: false };
	const doc: MarkdownHandle = {
		focus: vi.fn(),
		blank: vi.fn(() => blank),
		markdown: vi.fn(() => ""),
		tail: vi.fn(() => ""),
		split: vi.fn(() => ""),
		cut: vi.fn(() => ({ tail: "", keep: vi.fn(), undo: vi.fn() })),
		append: vi.fn(),
		type: vi.fn(),
		commit: vi.fn(),
		hint: vi.fn(),
		saved: vi.fn((fn: () => void, lost?: () => void) => {
			if (!store.held) {
				fn();
				return () => {};
			}
			const w = { fn, lost };
			waiting.push(w);
			return () => {
				const i = waiting.indexOf(w);
				if (i >= 0) waiting.splice(i, 1);
			};
		}),
		onIntent(fn) {
			listeners.add(fn);
			return () => {
				listeners.delete(fn);
			};
		},
	};
	/** Report an intent, as the editor's intents plugin would. True when the host acted. */
	const say = (i: MarkdownIntent) => {
		let acted = false;
		act(() => {
			for (const fn of listeners) if (fn(i)) acted = true;
		});
		return acted;
	};
	/** `saved` waits from here on, until the store answers. */
	const hold = () => {
		store.held = true;
	};
	/** The store read the latest text back: what waited for it runs. */
	const stored = () => {
		store.held = false;
		act(() => {
			for (const w of waiting.splice(0)) w.fn();
		});
	};
	/** Gone before the store answered: what waited hears `lost` instead. */
	const lose = () => {
		store.held = false;
		act(() => {
			for (const w of waiting.splice(0)) w.lost?.();
		});
	};
	return { doc, say, listeners, hold, stored, lose };
}

export const leaves: (() => void)[] = [];

/** An editable markdown editor at `path` with `handle`, as a MarkdownRef registers one. Returns the leave. */
export function registerEditable(path: Path, handle: MarkdownHandle): () => void {
	const reg = registerMarkdown(path);
	reg.editable(handle);
	return () => reg.leave();
}

/** Register `d` as cell `id`'s editor, at the path a MarkdownRef inside it would. */
export function mountDoc<D extends ReturnType<typeof fakeDoc>>(id: string, given?: D): D {
	const d = given ?? (fakeDoc() as D);
	act(() => {
		leaves.push(registerEditable([...VIEWER, "cells", id, "text"], d.doc));
	});
	return d;
}

/**
 * A markdown editor drawn the way a program opens one, in two frames:
 * mounted read-only first (there, no handle: it takes no commands yet),
 * then open for editing (`mountDoc` registers its handle, later).
 */
register("TestPresent", {
	component: ({ path }: { path: string[] }) => {
		// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value, as a MarkdownRef's.
		useEffect(() => {
			const reg = registerMarkdown(path);
			return () => reg.leave();
		}, [pathKey(path)]);
		return <div />;
	},
});

/** The first frame: cell `id` draws a markdown editor, read-only for now. */
export const drawReadOnly = (id: string) => draw(id, "TestPresent");

/** What cell `id` draws goes away, editor and all. */
export function undraw(id: string) {
	act(() => {
		tree.getState().remove([...VIEWER, "cells", id, "view"]);
	});
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
export const selected = () => readEditor(PANE).selected;
export const ops = () => notify.mock.calls.map(([op, args]) => [op, args.cell_id ?? args.cell_ids]);

export const title = (i: TitleIntent) => {
	let acted = false;
	act(() => {
		acted = handle.current?.title(i) ?? false;
	});
	return acted;
};

beforeEach(() => {
	tree.getState().write([["viewer"], ["panes"], ["p1", "PaneRef"]], {});
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
