// The page settings a pane's `...` menu offers, in the order it lists them.
//
// Each one is a key in the Plane's `meta` (see ../page/types.ts). Flipping one
// sends `page.meta` with just that key, applied optimistically; the server's
// next `set_page` confirms it. Adding a setting is adding a row here, plus
// reading its key wherever it takes effect. A `kind` other than a switch gets
// its own control in ./PaneMenu.tsx.

export type PageSetting = {
	kind: "switch";
	/** The `meta` key. */
	key: string;
	label: string;
	/** One line under the label saying what "on" means. */
	hint: string;
};

export const PAGE_SETTINGS: readonly PageSetting[] = [
	{
		kind: "switch",
		key: "editable",
		label: "Editable",
		hint: "Add, move and edit blocks",
	},
	{
		kind: "switch",
		key: "full_width",
		label: "Full width",
		hint: "Use the whole pane",
	},
	{
		kind: "switch",
		key: "compact",
		label: "Compact",
		hint: "Tight header, no space under the last block",
	},
];
