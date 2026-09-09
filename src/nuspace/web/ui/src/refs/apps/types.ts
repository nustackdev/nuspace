// AppsRef wire types + coercion.
//
// msgpack payloads arrive untyped, so every field is narrowed here and
// nowhere else. Everything downstream can assume these shapes.
//
// `SectionState` / `SectionStatus` are re-exported from the pages types
// rather than redeclared. They are the supervisor's contract, not the Pages
// surface's, and apps and sections share one supervisor -- a second copy of
// the same six strings is how the two drift apart.

import { coerceStatus, type SectionState, type SectionStatus } from "../pages/types";

export type { SectionState, SectionStatus };
export { coerceStatus };

/** One app, as the server ships it. `status` is null when nothing supervises it. */
export type AppRow = {
	id: string;
	name: string;
	source: string;
	/** Stored, and for v1 nothing reads it: every app runs always. */
	policy: string;
	status: SectionStatus | null;
};

export type AppsValue = {
	apps: AppRow[];
	/**
	 * Whether an `AppsRunner` is mounted in the space tree.
	 *
	 * False is not an error and not "loading". It means the space is up and
	 * its apps are not being supervised, which the surface says out loud
	 * instead of painting a list of apps that look merely idle.
	 */
	attached: boolean;
	/** Nothing has landed yet. Distinct from "landed, and it was empty". */
	loaded: boolean;
};

export const EMPTY_APPS: AppsValue = { apps: [], attached: false, loaded: false };

// -- coercion ----------------------------------------------------------------

export function coerceApps(raw: unknown): AppRow[] {
	if (!Array.isArray(raw)) return [];
	const out: AppRow[] = [];
	for (const a of raw) {
		if (!a || typeof a !== "object") continue;
		const r = a as Record<string, unknown>;
		const id = String(r.id ?? "");
		if (!id) continue;
		out.push({
			id,
			name: String(r.name ?? ""),
			source: String(r.snippet ?? r.source ?? ""),
			policy: String(r.policy ?? "always"),
			status: coerceStatus(r.status),
		});
	}
	return out;
}

/** What the rail and the bar show for an app that was never named. */
export function appLabel(app: AppRow): string {
	return app.name.trim() || app.id;
}

/** The state an unsupervised app renders as. Not a lie: nothing is running it. */
export const DETACHED_STATE: SectionState = "idle";
