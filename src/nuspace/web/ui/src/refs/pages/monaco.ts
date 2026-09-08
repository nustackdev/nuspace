// Lazy gate in front of Monaco.
//
// Monaco is ~4MB of the bundle and most page views never open a code editor,
// so it lives behind a dynamic import and lands in its own chunk. The first
// program block that flips into code mode pays for it; the document itself
// paints immediately.
//
// Types come from a type-only import, which the compiler erases, so nothing
// here pulls Monaco into the initial graph.

import type * as MonacoNS from "monaco-editor/editor/editor.api.js";

export type { MonacoNS };
export type MonacoApi = typeof MonacoNS;
export type CodeEditor = MonacoNS.editor.IStandaloneCodeEditor;
export type KeyboardEvt = MonacoNS.IKeyboardEvent;

let pending: Promise<MonacoApi> | null = null;

/** Load Monaco (once), with the nu themes defined. */
export function loadMonaco(): Promise<MonacoApi> {
	if (!pending) {
		pending = import("./monaco-impl").then((m) => {
			m.defineNuThemes();
			return m.monaco;
		});
	}
	return pending;
}
