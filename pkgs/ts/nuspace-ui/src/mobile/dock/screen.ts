// The plane the screen shows, read the way the screen reads it: the route
// says which (../Viewer.tsx `shownPlane`), its pane node says what it is
// (../../pane/state.ts). The dock sits in the frame, outside the plane, so
// it reads the same stores rather than being handed anything.

import { useRoute } from "../../core/router";
import { useTypePath } from "../../core/surfaces";
import { panePath, usePaneCells, usePaneHead } from "../../pane/state";
import { shownPlane } from "../Viewer";
import type { Screen } from "./model";

const NO_PATH: string[] = [];

/** The plane on screen, re-rendering as it, its head or its cells change. */
export function useScreen(): Screen {
	const route = useRoute();
	const viewer = useTypePath("ViewerRef");
	const shown = shownPlane(route);
	const path = viewer && shown ? panePath(viewer, shown.plane) : NO_PATH;
	const head = usePaneHead(path);
	const cells = usePaneCells(path);
	if (!shown || !head) return null;
	return { plane: shown.plane, editable: !!head.meta.editable, cells: cells?.length ?? null };
}
