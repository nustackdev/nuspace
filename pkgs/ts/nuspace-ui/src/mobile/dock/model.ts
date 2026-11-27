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
export type Control = "cell" | "plane" | "edit";

/**
 * The + sheet's rows, in order: Add cell where the plane on screen can be
 * written, Add plane always, Edit cells where the plane on screen has cells
 * to edit (a plane that cannot be written still has options per cell:
 * restart, copy, source).
 */
export function controlsFor(screen: Screen): Control[] {
	const out: Control[] = [];
	if (screen?.editable) out.push("cell");
	out.push("plane");
	if (screen && (screen.cells ?? 0) > 0) out.push("edit");
	return out;
}
