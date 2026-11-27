// The dock: the phone's controls, all at the bottom under the thumb, and the
// only chrome over a plane besides its header. No tab bar. What it holds
// follows what the screen is doing:
//
//   browsing   the sidebar button bottom left, the + bottom right. The +
//              opens the control sheet (./ControlSheet.tsx): add a cell, add
//              a plane, edit cells. Over the sidebar screen only the sidebar
//              button stays, to close it; the sidebar has its own +
//   editing    one bar across the bottom: what a tap does now, and Done
//              (../plane/editing.ts). The sidebar and the + wait until it
//              is done
//
// Every button is the same 48px floating round, on the same line, so moving
// between modes never moves the thumb's targets more than it has to.

import { Button, IconButton } from "@nustackdev/ui-kit";
import { PanelLeft, PanelLeftClose, Plus } from "lucide-react";
import { useState } from "react";
import { useBooted } from "../../core/surfaces";
import { mobileDockBar, mobileDockDone, mobileDockHint, mobileFab } from "../../design";
import { doneEditing, useEditing } from "../plane/editing";
import { toggleSidebar, useSidebarOpen } from "../sidebar/open";
import { ControlSheet } from "./ControlSheet";
import { useScreen } from "./screen";

export function Dock() {
	const sidebar = useSidebarOpen();
	const editing = useEditing();
	const screen = useScreen();
	const booted = useBooted();
	const [controls, setControls] = useState(false);

	if (editing) return <EditBar />;
	return (
		<>
			<IconButton
				variant="secondary"
				ring="inset"
				aria-label={sidebar ? "Close sidebar" : "Open sidebar"}
				aria-expanded={sidebar}
				data-fab="sidebar"
				onClick={toggleSidebar}
				className={mobileFab("left")}
			>
				{sidebar ? <PanelLeftClose /> : <PanelLeft />}
			</IconButton>
			{booted && !sidebar ? (
				<IconButton
					ring="inset"
					aria-label="Add or edit"
					aria-haspopup="menu"
					aria-expanded={controls}
					data-fab="controls"
					onClick={() => setControls(true)}
					className={mobileFab("right")}
				>
					<Plus />
				</IconButton>
			) : null}
			<ControlSheet screen={screen} open={controls} onClose={() => setControls(false)} />
		</>
	);
}

/** The bar while editing cells: the hint on the left, Done under the thumb on the right. */
function EditBar() {
	return (
		<div role="toolbar" aria-label="Editing cells" className={mobileDockBar} data-dock="editing">
			<span className={mobileDockHint}>Tap a cell for its options</span>
			<Button size="lg" className={mobileDockDone} onClick={doneEditing} data-dock-done="">
				Done
			</Button>
		</div>
	);
}
