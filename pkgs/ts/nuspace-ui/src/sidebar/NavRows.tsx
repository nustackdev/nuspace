// The nav rows, the body's first rows: Home, Search and Settings, the planes
// that always exist (./nav.ts). They scroll with the rest; only the top bar
// stays put.
//
// Each is a real link, so it opens the way a tree row does, through the
// shell's anchor catcher: plain in the focused pane, Option beside the others,
// cmd/ctrl-click in a browser tab.
// The open plane's row is washed like a tree row. No menu, no drag: there is
// nothing to do to them but open them. They are the first rows of the body's
// one tab stop (./useRailFocus.ts); Enter on one is its link's own.

import { Shortcut } from "@nustackdev/ui-kit";
import type { LucideIcon } from "lucide-react";
import { House, Search, Settings } from "lucide-react";
import { hrefFor } from "../core/router";
import { railNav, railNavIcon, railNavKeys, railNavLabel, railNavRow } from "../design";
import { HOME_PLANE, SETTINGS_KEYS, SETTINGS_PLANE } from "./nav";
import { SEARCH_KEYS, SEARCH_PLANE } from "./search";
import { navKey, useRailNav } from "./useRailFocus";

type NavItem = {
	id: string;
	label: string;
	icon: LucideIcon;
	keys?: readonly string[];
};

export const NAV_ITEMS: NavItem[] = [
	{ id: HOME_PLANE, label: "Home", icon: House },
	{ id: SEARCH_PLANE, label: "Search", icon: Search, keys: SEARCH_KEYS },
	{ id: SETTINGS_PLANE, label: "Settings", icon: Settings, keys: SETTINGS_KEYS },
];

export function NavRows({ routes, selKey }: { routes: string[]; selKey: string }) {
	const { tabKey, setActiveKey, arrows } = useRailNav();
	return (
		<nav aria-label="Space" className={railNav}>
			{NAV_ITEMS.map(({ id, label, icon: Icon, keys }) => {
				const selected = id === selKey;
				return (
					<a
						key={id}
						href={hrefFor(id)}
						data-plane-id={id}
						data-rail-key={navKey(id)}
						tabIndex={tabKey === navKey(id) ? 0 : -1}
						onFocus={() => setActiveKey(navKey(id))}
						onKeyDown={(e) => arrows(e, navKey(id))}
						aria-current={selected ? "page" : undefined}
						aria-keyshortcuts={keys ? ariaKeys(keys) : undefined}
						className={railNavRow(selected, !selected && routes.includes(id))}
					>
						<span className={railNavIcon} aria-hidden="true">
							<Icon />
						</span>
						<span className={railNavLabel}>{label}</span>
						{keys ? (
							<Shortcut
								keys={keys}
								variant="ghost"
								size="sm"
								className={railNavKeys}
								aria-hidden="true"
							/>
						) : null}
					</a>
				);
			})}
		</nav>
	);
}

/** `["mod", "K"]` as `aria-keyshortcuts` spells it: both modifiers, since "mod" is either. */
function ariaKeys(keys: readonly string[]): string {
	const rest = keys.filter((k) => k !== "mod").join("+");
	return keys.includes("mod") ? `Meta+${rest} Control+${rest}` : rest;
}
