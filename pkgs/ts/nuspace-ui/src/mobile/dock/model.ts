// The dock's decisions, as plain functions: what the + sheet offers for the
// screen it is over. The dock (./Dock.tsx) and its sheet (./ControlSheet.tsx)
// only draw them.

/** The plane on screen, as far as the dock cares; null when the screen shows none. */
export type Screen = {
	plane: string;
	/** Its cells can be added and deleted. */
	editable: boolean;
	/** How many cells it has; null until they land. */
	cells: number | null;
} | null;

/** One row of the + sheet. */
export type Control = "cell" | "plane" | "inside" | "edit";

/**
 * The + sheet's rows, in order. Over the sidebar screen, Add plane alone:
 * the sidebar is about planes, not the plane under it. Over a plane: Add
 * cell where it can be written, Add plane (at the top) always, Add plane
 * inside it, Edit cells where it has cells to edit (a plane that cannot be
 * written still has options per cell: restart, copy, source). With no plane
 * on screen, Add plane alone.
 */
export function controlsFor(screen: Screen, sidebar = false): Control[] {
	if (sidebar) return ["plane"];
	const out: Control[] = [];
	if (screen?.editable) out.push("cell");
	out.push("plane");
	if (screen) out.push("inside");
	if (screen && (screen.cells ?? 0) > 0) out.push("edit");
	return out;
}
