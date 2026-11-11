// A plane's look: its title and its icon, for anything that names a plane
// it may not have open, a desk folder row first.
//
// The freshest source wins: the viewer's plane when this tab has it open
// (a rename shows at once), else the desks node's titles (every plane any
// desk links to, ./desks.ts), else what the caller knows (the Planes tree's
// row), else "Untitled".
//
// The browser tab names only the focused pane, which the viewer always has,
// so it reads the viewer alone (../shell/tab.ts).

import { getNode } from "@nustackdev/ui-core";
import { useTree } from "@nustackdev/ui-kit";
import { useMemo } from "react";
import type { ActivePlane } from "../plane/types";
import { type PlaneLook, useDeskTitles } from "./desks";
import { useTypePath } from "./surfaces";

export type { PlaneLook };

/** What a plane is called with no title anywhere. */
export const UNTITLED = "Untitled";

/** A look the caller knows of, by plane id: the Planes tree's rows. */
export type KnownLooks = Record<string, { title: string; icon?: string } | undefined>;

/**
 * The look of each of `planes`. Selects one string off the viewer, so a cell
 * edit re-renders nothing here.
 */
export function usePlaneLooks(planes: string[], known: KnownLooks): Record<string, PlaneLook> {
	const viewer = useTypePath("ViewerRef");
	const titles = useDeskTitles();
	const shipped = useTree((s) => {
		const props = viewer ? getNode(s.root, viewer)?.props : undefined;
		const open = props?.planes as Record<string, ActivePlane> | undefined;
		return JSON.stringify(
			planes.map((id) => {
				const plane = open?.[id];
				return plane ? [plane.title, plane.meta.icon ?? ""] : null;
			}),
		);
	});
	return useMemo(() => {
		const got = JSON.parse(shipped) as ([string, unknown] | null)[];
		return Object.fromEntries(
			planes.map((id, i) => {
				const row = known[id];
				const desk = titles[id];
				const title = got[i]?.[0] || desk?.title || row?.title || UNTITLED;
				const icon = got[i]?.[1] || desk?.icon || row?.icon || "";
				return [id, { title, icon: typeof icon === "string" ? icon : "" }];
			}),
		);
	}, [shipped, planes, known, titles]);
}

/** Plane `plane`'s look in `looks`, "Untitled" with no icon when it has none. */
export function lookOf(looks: Record<string, PlaneLook>, plane: string): PlaneLook {
	return looks[plane] ?? { title: UNTITLED, icon: "" };
}
