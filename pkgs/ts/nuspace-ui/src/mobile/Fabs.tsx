// The two floating buttons, the phone's only chrome: the sidebar bottom left,
// + bottom right, both under the thumb. No tab bar.
//
// The sidebar button stays over the sidebar screen and closes it again. The +
// adds a cell to the plane on screen (./addCell.ts); it is there only while a
// plane is, and not over the sidebar, which has its own +.

import { IconButton } from "@nustackdev/ui-kit";
import { PanelLeft, PanelLeftClose, Plus } from "lucide-react";
import { useRoute } from "../core/router";
import { mobileFab } from "../design";
import { openAddCell } from "./addCell";
import { toggleSidebar, useSidebarOpen } from "./sidebar/open";

export function Fabs() {
	const open = useSidebarOpen();
	const route = useRoute();
	const plane = route.kind === "solo" || (route.kind === "item" && !!route.focus);
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
