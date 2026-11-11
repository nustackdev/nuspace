// The sidebar header, the fixed top bar: collapse, the wordmark, and a `+` on
// the right, a menu of what can be made: New plane (the Add plane popup for a
// top-level plane, the same as the New plane row and cmd/ctrl+alt+N) and New
// desk (./newDesk.ts).

import {
	cn,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuShortcut,
	DropdownMenuTrigger,
	IconButton,
	Shortcut,
} from "@nustackdev/ui-kit";
import { Columns3, FilePlus, PanelLeft, Plus } from "lucide-react";
import {
	sidebarChromeButton,
	sidebarHeader,
	sidebarHeaderEnd,
	sidebarTooltipHint,
	sidebarWordmark,
	sidebarWordmarkNu,
} from "../design";
import { NEW_PLANE_KEYS, openAddPlane } from "./add";
import { focusSidebarToggle, SIDEBAR_KEYS, setSidebarCollapsed } from "./collapse";
import { newDesk } from "./newDesk";
import { ROOT_ID } from "./types";

export function SidebarHeader() {
	return (
		<div className={sidebarHeader}>
			<SidebarToggle
				label="Hide sidebar"
				onClick={() => {
					setSidebarCollapsed(true);
					focusSidebarToggle();
				}}
			/>
			<span className={sidebarWordmark}>
				<span className={sidebarWordmarkNu}>nu</span>space
			</span>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<IconButton
						variant="ghost"
						size="sm"
						ring="inset"
						aria-label="New"
						tip="New"
						className={cn(sidebarChromeButton, sidebarHeaderEnd)}
					>
						<Plus />
					</IconButton>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuItem onSelect={() => openAddPlane({ parent: ROOT_ID })}>
						<FilePlus />
						New plane
						<DropdownMenuShortcut keys={NEW_PLANE_KEYS} />
					</DropdownMenuItem>
					<DropdownMenuItem onSelect={() => newDesk()}>
						<Columns3 />
						New desk
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}

/**
 * The `panel-left` button, in the header and, while the sidebar is
 * collapsed, over the desk area's top left corner (../shell/Shell.tsx).
 */
export function SidebarToggle({ label, onClick }: { label: string; onClick: () => void }) {
	return (
		<IconButton
			variant="ghost"
			size="sm"
			ring="inset"
			aria-label={label}
			tip={
				<>
					{label}
					<Shortcut keys={SIDEBAR_KEYS} size="sm" className={sidebarTooltipHint} />
				</>
			}
			data-sidebar-toggle=""
			onClick={onClick}
			className={sidebarChromeButton}
		>
			<PanelLeft />
		</IconButton>
	);
}
