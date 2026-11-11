// The nav section: home, search and settings, the body's first rows. No
// title, shortcuts always shown. Each row is the plane its role points at
// (./nav.ts), a link like any tree row; before the roles land the rows are
// drawn with nowhere to go yet. Like a tree row, a nav row drags its plane
// onto the desk or a desk folder (./drag.ts `planeDragProps`): its link alone
// would carry only a url, which no drop target takes.

import { useRoles } from "../core/desks";
import { hrefFor } from "../core/router";
import { planeDragProps } from "./drag";
import { navKey } from "./focus";
import { NAV_ITEMS } from "./nav";
import { SidebarRow } from "./SidebarRow";
import { SidebarSection } from "./SidebarSection";

/** The nav rows' keys, the body's first. */
export const NAV_KEYS = NAV_ITEMS.map((item) => navKey(item.role));

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
		</SidebarSection>
	);
}

/** `["mod", "K"]` as `aria-keyshortcuts` spells it: both modifiers, since "mod" is either. */
function ariaKeys(keys: readonly string[]): string {
	const rest = keys.filter((k) => k !== "mod").join("+");
	return keys.includes("mod") ? `Meta+${rest} Control+${rest}` : rest;
}
