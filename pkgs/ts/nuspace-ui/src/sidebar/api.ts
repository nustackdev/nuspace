// The sidebar's public surface: what the shell and the desk (../main) use of
// the rail. They import from here and never from the rail's own files, so
// those can move and split without the frame noticing.
//
// The folders sit in layers, each importing only from the ones under it:
//
//   shell, refs     the app frame; the refs that register main and sidebar
//   main            the desk: the pane strip and the dock
//   pane            one pane: bar, title, menu, then the plane
//   plane, sidebar  the document; the rail
//   menu, icon      menu parts and ranking; icon packs
//   core, design    state, router, wire, stores; tokens and class recipes
//
// So nothing here may reach up: a store or a constant the rail shares with
// the shell goes down into core (../core/keys.ts, ../core/confirm.ts).

// -- For the shell -----------------------------------------------------------

export { NEW_INSIDE_KEYS, NEW_PLANE_KEYS, useNewPlaneShortcut } from "./add";
export {
	bindRail,
	focusRailToggle,
	migrateRail,
	publishRail,
	RAIL_KEYS,
	RAIL_LAYOUT_KEY,
	setRailCollapsed,
	useRailCollapsed,
	useRailShortcut,
} from "./collapse";
export { DESK_CLICK, DESK_KEYS, OPEN_KEYS } from "./keys";
export { HOME_KEYS, SETTINGS_KEYS } from "./nav";
export { RailPlaceholder } from "./Rail";
export { RailToggle } from "./RailHeader";
export { SEARCH_KEYS } from "./search";

// -- For the desk ------------------------------------------------------------

export type { Notify, Ops } from "./ops";
export { PIN_MIME } from "./Pinned";
export { pinDropIndex } from "./pin";
export { canDelete, deletePlane } from "./remove";
export { usePlaneTree } from "./state";
export { PLANE_MIME } from "./useRailDrag";
