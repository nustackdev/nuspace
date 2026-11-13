// The sidebar's public surface: what the shell and the desk (../main) use of
// the sidebar. They import from here and never from the sidebar's own files,
// so those can move and split without the frame noticing.
//
// The folders sit in layers, each importing only from the ones under it:
//
//   shell, refs     the app frame; the refs that register main and sidebar
//   main            the desk
//   pane            one pane: header, title, menu, then the plane
//   plane, sidebar  the document; the sidebar
//   menu, icon      menu parts and ranking; icon packs
//   core, design    state, router, wire, stores; tokens and class recipes
//
// So nothing here may reach up: a store or a constant the sidebar shares with
// the shell goes down into core (../core/keys.ts, ../core/confirm.ts).

// -- For the shell -----------------------------------------------------------

export { NEW_INSIDE_KEYS, NEW_PLANE_KEYS, useNewPlaneShortcut } from "./add";
export {
	bindSidebar,
	focusSidebarToggle,
	publishSidebar,
	SIDEBAR_KEYS,
	SIDEBAR_LAYOUT_KEY,
	setSidebarCollapsed,
	useSidebarShortcut,
} from "./collapse";
export { OPEN_KEYS, SIDE_KEYS } from "./keys";
export { HOME_KEYS, SEARCH_KEYS, SETTINGS_KEYS, useNavShortcuts } from "./nav";
export { SidebarPlaceholder } from "./Sidebar";
export { SidebarRail } from "./SidebarRail";

// -- For the desk and the shell ------------------------------------------------

export { PLANE_MIME } from "./drag";
export { deskLabel, STRIP_TITLE } from "./folders";
export { usePlaneTree } from "./state";
export type { PlaneTree } from "./types";
