// The AppsRef slice: wire state + the little browser-owned state there is.
//
// Much smaller than the Pages slice, and the reason is the pillar, not the
// effort. A page is a document, so the browser owns caret intent, block
// selection, per-block mode, a slash menu and a drag. An app is one file, so
// the browser owns a dirty flag and a rename draft, and that is all of it.
//
// There are also no field slices to register. A section mounts ui refs and
// the slice builds a child slice per mount field; an app is headless and
// mounts nothing, so nothing here touches `refs`.
//
// Selection lives in the URL (/apps/<id>), so it is not here either.

import type { RefSlice, SliceCtx, SliceFactory } from "@nustackdev/ui-kit";
import { useStore } from "@nustackdev/ui-kit";
import { type AppsValue, coerceApps, coerceStatus, EMPTY_APPS, type SectionStatus } from "./types";

// -- browser-owned editor state ----------------------------------------------

export type AppsEditorState = {
	/** App ids whose Monaco buffer differs from the shipped source. */
	dirty: string[];
	/** App id being renamed in the rail, or null. */
	renaming: string | null;
};

export const EMPTY_EDITOR: AppsEditorState = { dirty: [], renaming: null };

type AppsSlice = RefSlice & {
	value: AppsValue;
	editor: AppsEditorState;
	/** What a new app starts life as, off the mount props. The one spelling of
	 *  it is `nuspace/core/tpl.py`; it rides the mount so the browser can fill
	 *  `source` on a create without owning a template. */
	starter: string;
};

// -- factory -----------------------------------------------------------------

export const appsSliceFactory: SliceFactory = (path, ctx: SliceCtx, props) =>
	({
		type: "AppsRef",
		value: { ...EMPTY_APPS } as AppsValue,
		editor: { ...EMPTY_EDITOR },
		starter: String((props as Record<string, unknown> | undefined)?.starter ?? ""),
		write: (v) =>
			ctx.set((refs) => {
				const slice = refs[path] as AppsSlice | undefined;
				if (!slice) return;
				const p = (v ?? {}) as Record<string, unknown>;
				const op = String(p.op ?? "");

				if (op === "set_apps") {
					const apps = coerceApps(p.apps);
					slice.value = { apps, attached: p.attached === true, loaded: true };
					// Drop editor state pointing at apps that no longer exist. A
					// reship means the list moved under it and guessing is worse
					// than nothing.
					const live = new Set(apps.map((a) => a.id));
					const ed = slice.editor;
					slice.editor = {
						dirty: ed.dirty.filter((id) => live.has(id)),
						renaming: ed.renaming && live.has(ed.renaming) ? ed.renaming : null,
					};
					return;
				}

				if (op !== "set_status") return;

				// A status batch patches in place. It must never resurrect an
				// app the last `set_apps` dropped, and it must never reorder.
				const byId = new Map<string, SectionStatus>();
				for (const raw of Array.isArray(p.statuses) ? p.statuses : []) {
					const st = coerceStatus(raw);
					if (st?.section_id) byId.set(st.section_id, st);
				}
				if (byId.size === 0) return;
				slice.value = {
					...slice.value,
					apps: slice.value.apps.map((a) =>
						byId.has(a.id) ? { ...a, status: byId.get(a.id) ?? a.status } : a,
					),
				};
			}),
	}) as AppsSlice;

// -- reads -------------------------------------------------------------------

export function useAppsValue(path: string): AppsValue {
	return useStore((s) => (s.refs[path]?.value as AppsValue | undefined) ?? EMPTY_APPS);
}

/** What a create fills `source` with. Empty until the mount lands. */
export function useAppStarter(path: string): string {
	return useStore((s) => (s.refs[path] as AppsSlice | undefined)?.starter ?? "");
}

/** Narrow subscription so a keystroke in the editor does not rerender the rail. */
export function useAppsEditorSlot<T>(path: string, pick: (e: AppsEditorState) => T): T {
	return useStore((s) => pick((s.refs[path] as AppsSlice | undefined)?.editor ?? EMPTY_EDITOR));
}

// -- writes ------------------------------------------------------------------

/**
 * Patch the browser-owned editor state. Module-level rather than a hook so
 * event handlers can call it without prop-drilling, and so it never
 * participates in a render.
 */
export function patchAppsEditor(
	path: string,
	patch: Partial<AppsEditorState> | ((e: AppsEditorState) => Partial<AppsEditorState>),
): void {
	useStore.setState((s) => {
		const slice = s.refs[path] as AppsSlice | undefined;
		if (!slice) return;
		const next = typeof patch === "function" ? patch(slice.editor) : patch;
		slice.editor = { ...slice.editor, ...next };
	});
}

/** Mark one app's buffer clean or dirty. */
export function setDirty(path: string, appId: string, dirty: boolean): void {
	patchAppsEditor(path, (e) => {
		const has = e.dirty.includes(appId);
		if (has === dirty) return {};
		return { dirty: dirty ? [...e.dirty, appId] : e.dirty.filter((id) => id !== appId) };
	});
}
