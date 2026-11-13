// The nav section: home, search and settings, the body's first rows. No
// title, shortcuts always shown. Each row is the plane its role points at
// (./nav.ts), a link like any tree row; before the roles land the rows are
// drawn with nowhere to go yet. Like a tree row, a nav row drags its plane
// onto the desk or a desk folder (./drag.ts `planeDragProps`): its link alone
// would carry only a url, which no drop target takes.
//
// Under settings, New desk: a click makes an empty desk, a plane, item or
// pane dropped on it makes a desk of it (./newDesk.ts). Ringed while a drag
// aims at it, with no hint: its own label says what the drop does. It is
// always there, so nothing moves when a drag starts.

import { Plus } from "lucide-react";
import type * as React from "react";
import { useEffect, useState } from "react";
import { useRoles } from "../core/desks";
import { hrefFor } from "../core/router";
import { sidebarDropInto } from "../design";
import { dragKind, endDrag, readDrag } from "../desk/dnd";
import { planeDragProps } from "./drag";
import { navKey } from "./focus";
import { NAV_ITEMS } from "./nav";
import { newDesk } from "./newDesk";
import { SidebarRow } from "./SidebarRow";
import { SidebarSection } from "./SidebarSection";

/** The New desk row's key. */
export const NEW_DESK_KEY = navKey("new-desk");

/** The nav rows' keys, the body's first: the roles, then New desk. */
export const NAV_KEYS = [...NAV_ITEMS.map((item) => navKey(item.role)), NEW_DESK_KEY];

export function NavSection({ selKey }: { selKey: string }) {
	const roles = useRoles();
	return (
		<SidebarSection id="nav" label="Navigation">
			{NAV_ITEMS.map(({ role, label, icon: Icon, keys }) => {
				const plane = roles?.[role] ?? "";
				return (
					<SidebarRow
						key={role}
						rowKey={navKey(role)}
						planeId={plane || undefined}
						href={plane ? hrefFor(plane) : undefined}
						drag={plane ? planeDragProps(plane) : undefined}
						label={label}
						selected={!!plane && plane === selKey}
						icon={<Icon aria-hidden="true" />}
						trailing={{ shortcut: keys }}
						aria-keyshortcuts={ariaKeys(keys)}
					/>
				);
			})}
			<NewDeskRow />
		</SidebarSection>
	);
}

/** New desk: a click makes one, a drop makes one of what is dropped. */
function NewDeskRow() {
	const [aimed, setAimed] = useState(false);

	// A drag that ends anywhere clears the ring.
	useEffect(() => {
		const clear = () => setAimed(false);
		document.addEventListener("dragend", clear);
		document.addEventListener("drop", clear);
		return () => {
			document.removeEventListener("dragend", clear);
			document.removeEventListener("drop", clear);
		};
	}, []);

	const drop: Pick<
		React.HTMLAttributes<HTMLDivElement>,
		"onDragOver" | "onDragLeave" | "onDrop"
	> = {
		onDragOver: (e) => {
			if (!dragKind(e.dataTransfer)) return;
			e.preventDefault();
			e.stopPropagation();
			e.dataTransfer.dropEffect = "move";
			setAimed(true);
		},
		onDragLeave: (e) => {
			if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setAimed(false);
		},
		onDrop: (e) => {
			const payload = readDrag(e.dataTransfer);
			setAimed(false);
			if (!payload) return;
			e.preventDefault();
			e.stopPropagation();
			endDrag();
			newDesk(payload);
		},
	};

	return (
		<div role="none" data-new-desk="">
			<SidebarRow
				rowKey={NEW_DESK_KEY}
				label="New desk"
				icon={<Plus aria-hidden="true" />}
				onClick={() => newDesk()}
				drag={drop}
				className={aimed ? sidebarDropInto : undefined}
			/>
		</div>
	);
}

/** `["mod", "K"]` as `aria-keyshortcuts` spells it: both modifiers, since "mod" is either. */
function ariaKeys(keys: readonly string[]): string {
	const rest = keys.filter((k) => k !== "mod").join("+");
	return keys.includes("mod") ? `Meta+${rest} Control+${rest}` : rest;
}
