// Monaco, owning one app's whole source.
//
// Deliberately *not* `refs/pages/Code.tsx`, and the difference is the pillar
// rather than the effort. That wrapper's real job is the block boundary:
// ArrowUp on line 1 leaves the editor for the block above, ArrowDown on the
// last line leaves it for the block below, Escape hands control back to
// block selection. All three exist because a program block lives inside a
// document with prose on either side of it.
//
// An app has no document around it. There is no block above, nothing below,
// and nothing to hand selection back to, so importing that wrapper would
// mean importing three behaviours that have nowhere to go and then
// suppressing them.
//
// What IS reused is the part that is genuinely shared: `./pages/monaco`, the
// lazy gate that keeps ~4MB out of the initial chunk and restains the editor
// from the live design tokens on a theme flip. One Monaco, one theme, one
// subscription, for both surfaces.
//
// Keys: cmd+enter saves (and therefore restarts this app), blur with changes
// saves. Escape does nothing, because there is nothing to escape to.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
	type CodeEditor,
	type KeyboardEvt,
	loadMonaco,
	type MonacoApi,
	NU_THEME,
} from "../pages/monaco";

export type SourceBoxProps = {
	/** Remounts the editor when it changes: a different app is a different file. */
	appId: string;
	source: string;
	/** cmd+enter, or blur with changes. Saving an app restarts it. */
	onCommit: (source: string) => void;
	/** Live read of the buffer, for the bar's unsaved marker. */
	onDirty: (dirty: boolean) => void;
};

export function SourceBox({ appId, source, onCommit, onDirty }: SourceBoxProps) {
	const hostRef = useRef<HTMLDivElement | null>(null);
	const editorRef = useRef<CodeEditor | null>(null);
	const [, setReady] = useState(false);
	// Callbacks change identity every render; monaco listeners bind once.
	const cb = useRef({ onCommit, onDirty });
	cb.current = { onCommit, onDirty };
	const sourceRef = useRef(source);
	sourceRef.current = source;

	// biome-ignore lint/correctness/useExhaustiveDependencies: appId is the identity of the file this editor owns; switching apps must build a fresh model, not mutate the old one
	useLayoutEffect(() => {
		let disposed = false;
		let teardown: (() => void) | null = null;

		loadMonaco().then((monaco: MonacoApi) => {
			const host = hostRef.current;
			if (disposed || !host) return;

			const editor = monaco.editor.create(host, {
				value: sourceRef.current,
				language: "python",
				// One theme name; `pages/monaco.ts` restains it in place on a flip.
				theme: NU_THEME,
				automaticLayout: true,
				minimap: { enabled: false },
				lineNumbers: "on",
				lineNumbersMinChars: 3,
				glyphMargin: false,
				folding: true,
				scrollBeyondLastLine: false,
				renderLineHighlight: "line",
				overviewRulerLanes: 0,
				hideCursorInOverviewRuler: true,
				scrollbar: { vertical: "auto", horizontal: "auto" },
				padding: { top: 8, bottom: 8 },
				// Editor tier, per typography.md §2.
				fontSize: 13,
				fontFamily:
					getComputedStyle(document.documentElement).getPropertyValue("--font-mono") || "monospace",
				tabSize: 4,
				insertSpaces: true,
				wordWrap: "on",
				contextmenu: false,
				fixedOverflowWidgets: true,
				// No completion providers are wired, so the only thing on offer
				// is word-based noise.
				quickSuggestions: false,
				suggestOnTriggerCharacters: false,
				wordBasedSuggestions: "off",
				parameterHints: { enabled: false },
			});
			editorRef.current = editor;

			const subs = [
				editor.onDidChangeModelContent(() => {
					cb.current.onDirty(editor.getValue() !== sourceRef.current);
				}),
				editor.onKeyDown((e: KeyboardEvt) => {
					if (e.keyCode === monaco.KeyCode.Enter && (e.metaKey || e.ctrlKey)) {
						e.preventDefault();
						e.stopPropagation();
						cb.current.onCommit(editor.getValue());
					}
				}),
				editor.onDidBlurEditorText(() => {
					if (editor.getValue() !== sourceRef.current) {
						cb.current.onCommit(editor.getValue());
					}
				}),
			];

			teardown = () => {
				for (const s of subs) s.dispose();
				editor.getModel()?.dispose();
				editor.dispose();
				editorRef.current = null;
			};
			setReady(true);
		});

		return () => {
			disposed = true;
			teardown?.();
		};
	}, [appId]);

	// Server-side source changed (our own save round-tripped, or another
	// browser wrote it). Only overwrite when the buffer is not being edited --
	// two tabs on one app must not fight over the caret.
	useEffect(() => {
		const editor = editorRef.current;
		if (!editor) return;
		if (editor.getValue() !== source && !editor.hasTextFocus()) {
			editor.setValue(source);
			cb.current.onDirty(false);
		}
	}, [source]);

	return <div ref={hostRef} className="size-full" />;
}
