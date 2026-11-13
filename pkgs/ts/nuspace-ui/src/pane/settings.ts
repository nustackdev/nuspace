// The plane settings a pane's `...` menu offers, in the order it lists them.
//
// Each one is a web flag of the Plane, shipped in its `meta` (see
// ../plane/types.ts). Changing one sends `plane.web` with just that flag,
// applied optimistically; the server's next `set_head` confirms it. Adding a
// setting is adding a row here, plus reading its key wherever it takes
// effect. A switch flips a boolean; a choice picks one of a few values, each
// drawn as a small picture of what it does (./PaneMenu.tsx).

import type { PlaneWidth } from "../design";

export type PlaneSetting =
	| {
			kind: "switch";
			/** The `meta` key. */
			key: string;
			label: string;
			/** One line under the label saying what "on" means. */
			hint: string;
	  }
	| {
			kind: "choice";
			/** The `meta` key. */
			key: string;
			label: string;
			/** The values, in the order they show, each with its name. */
			options: readonly { value: PlaneWidth; label: string; hint: string }[];
	  };

export const PLANE_SETTINGS: readonly PlaneSetting[] = [
	{
		kind: "switch",
		key: "editable",
		label: "Editable",
		hint: "Add, move and edit cells",
	},
	{
		kind: "choice",
		key: "width",
		label: "Width",
		options: [
			{ value: "page", label: "Page", hint: "The reading measure" },
			{ value: "board", label: "Board", hint: "Room for a dashboard" },
			{ value: "full", label: "Full", hint: "The whole pane" },
		],
	},
];
