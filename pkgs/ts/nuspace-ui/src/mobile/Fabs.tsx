// The two floating buttons, the phone's only chrome: the sidebar bottom left,
// + bottom right, both under the thumb. No tab bar.
//
// The sidebar button stays over the sidebar screen and closes it again. The +
// adds a cell to the plane on screen (./addCell.ts); it is there only while a
// plane that can be written is on screen, and not over the sidebar, which has
// its own +.

import { IconButton } from "@nustackdev/ui-kit";
import { PanelLeft, PanelLeftClose, Plus } from "lucide-react";
import { useRoute } from "../core/router";
import { useTypePath } from "../core/surfaces";
import { mobileFab } from "../design";
import { panePath, usePaneHead } from "../pane/state";
import { openAddCell } from "./addCell";
import { toggleSidebar, useSidebarOpen } from "./sidebar/open";
import { shownPlane } from "./Viewer";

export function Fabs() {
	const open = useSidebarOpen();
	const plane = useWritablePlane();
	return (
		<>
			<IconButton
				variant="secondary"
				ring="inset"
				aria-label={open ? "Close sidebar" : "Open sidebar"}
				aria-expanded={open}
				data-fab="sidebar"
				onClick={toggleSidebar}
				className={mobileFab("left")}
			>
				{open ? <PanelLeftClose /> : <PanelLeft />}
			</IconButton>
			{plane && !open ? (
				<IconButton
					ring="inset"
					aria-label="Add cell"
					data-fab="add"
					onClick={openAddCell}
					className={mobileFab("right")}
				>
					<Plus />
				</IconButton>
			) : null}
		</>
	);
}

const NO_PATH: string[] = [];

/** Whether the screen shows a plane its cells can be added to. */
function useWritablePlane(): boolean {
	const route = useRoute();
	const viewer = useTypePath("ViewerRef");
	const shown = shownPlane(route);
	const head = usePaneHead(viewer && shown ? panePath(viewer, shown.plane) : NO_PATH);
	return !!shown && !!head?.meta.editable;
}
