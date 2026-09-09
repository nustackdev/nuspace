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
import { onThemeChange } from "../../theme";

export type { MonacoNS };

/**
 * The single Monaco theme name. One theme, redefined from the live tokens on
 * every flip, rather than two defined once - see `monaco-impl.applyNuTheme`.
 */
export const NU_THEME = "nu";
export type MonacoApi = typeof MonacoNS;
export type CodeEditor = MonacoNS.editor.IStandaloneCodeEditor;
export type KeyboardEvt = MonacoNS.IKeyboardEvent;

let pending: Promise<MonacoApi> | null = null;
let impl: typeof import("./monaco-impl") | null = null;

/** Load Monaco (once), stained with the live design tokens. */
export function loadMonaco(): Promise<MonacoApi> {
	if (!pending) {
		pending = import("./monaco-impl").then((m) => {
			impl = m;
			m.applyNuTheme();
			return m.monaco;
		});
	}
	return pending;
}

/**
 * Restain Monaco after a theme flip. A no-op until something has actually
 * opened a code box, so flipping the theme on a page with no open editor does
 * not drag 3MB of editor into the bundle's execution path.
 */
function refreshMonacoTheme(): void {
	impl?.applyNuTheme();
}

// One subscription for the whole app, not one per open code box.
onThemeChange(refreshMonacoTheme);
