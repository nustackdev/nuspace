// The AppsRef node: what the wire writes, and the little the browser owns.
//
// Much smaller than the Pages side, and the reason is the pillar, not the
// effort. A page is a document, so the browser owns caret intent, block
// selection, per-block mode, a slash menu and a drag. An app is one file, so
// the browser owns a dirty flag and a rename draft, and that is all of it.
//
// There are also no child nodes to look after. A section mounts ui refs and
// they arrive as children of the section's node; an app is headless and
// mounts nothing.
//
// Selection lives in the URL (/apps/<id>), so it is not here either.
//
// ## Why this type keeps a write handler
//
// Two ops ride one payload, told apart by an `op` key, and the store's
// default write has nothing to dispatch on. `set_apps` replaces the list;
// `set_status` patches statuses into it by id and must never resurrect an app
// the last `set_apps` dropped, never reorder, and never blank the status of
// an app it does not mention. A prop merge can do none of that.

import type { Path, Props } from "@nustackdev/ui-core";
import { useProps } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import { localOf, patchLocal, useLocalSlot } from "../../app/local";
import {
	type AppRow,
	type AppsValue,
	coerceApps,
	coerceStatus,
	EMPTY_APPS,
	type SectionStatus,
} from "./types";

// -- browser-owned state -----------------------------------------------------

export type AppsLocal = {
	/** App ids whose Monaco buffer differs from the shipped source. */
	dirty: string[];
	/** App id being renamed in the rail, or null. */
	renaming: string | null;
};

export const EMPTY_LOCAL: AppsLocal = { dirty: [], renaming: null };

// -- the write handler's body ------------------------------------------------

/** Apply one inbound payload to this node's props. Pure, so it is testable. */
export function applyAppsWrite(props: Props, payload: unknown): void {
	const p = (payload ?? {}) as Record<string, unknown>;
	const op = String(p.op ?? "");

	if (op === "set_apps") {
		const apps = coerceApps(p.apps);
		props.apps = apps;
		props.attached = p.attached === true;
		props.loaded = true;
		// Drop local state pointing at apps that no longer exist. A reship
		// means the list moved under it and guessing is worse than nothing.
		const live = new Set(apps.map((a) => a.id));
		const local = localOf(props, EMPTY_LOCAL);
		props.local = {
			dirty: local.dirty.filter((id) => live.has(id)),
			renaming: local.renaming && live.has(local.renaming) ? local.renaming : null,
		} satisfies AppsLocal;
		return;
	}

	if (op !== "set_status") return;

	const byId = new Map<string, SectionStatus>();
	for (const raw of Array.isArray(p.statuses) ? p.statuses : []) {
		const st = coerceStatus(raw);
		if (st?.section_id) byId.set(st.section_id, st);
	}
	if (byId.size === 0) return;
	const apps = (props.apps as AppRow[] | undefined) ?? [];
	props.apps = apps.map((a) => (byId.has(a.id) ? { ...a, status: byId.get(a.id) ?? a.status } : a));
}

// -- reads -------------------------------------------------------------------

// The props are already narrowed: `applyAppsWrite` coerces on arrival, which
// is where it belongs -- once per frame rather than once per render, and it
// keeps the array identity stable so the rail does not rebuild on every
// keystroke in the editor.
export function useAppsValue(path: Path): AppsValue {
	const props = useProps(path);
	const apps = (props.apps as AppRow[] | undefined) ?? EMPTY_APPS.apps;
	const attached = props.attached === true;
	const loaded = props.loaded === true;
	return useMemo(
		() => (loaded ? { apps, attached, loaded } : EMPTY_APPS),
		[apps, attached, loaded],
	);
}

/** What a create fills `source` with. Empty until the first write lands. */
export function useAppStarter(path: Path): string {
	return String(useProps(path).starter ?? "");
}

/** Narrow subscription so a keystroke in the editor does not rerender the rail. */
export function useAppsLocal<T>(path: Path, pick: (local: AppsLocal) => T): T {
	return useLocalSlot(path, EMPTY_LOCAL, pick);
}

// -- writes ------------------------------------------------------------------

/** Mark one app's buffer clean or dirty. */
export function setDirty(path: Path, appId: string, dirty: boolean): void {
	patchLocal(path, EMPTY_LOCAL, (local) => {
		const has = local.dirty.includes(appId);
		if (has === dirty) return {};
		return { dirty: dirty ? [...local.dirty, appId] : local.dirty.filter((id) => id !== appId) };
	});
}

/** Open or close the rail's rename box. */
export function setRenaming(path: Path, appId: string | null): void {
	patchLocal(path, EMPTY_LOCAL, { renaming: appId });
}
