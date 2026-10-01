// One menu, two triggers. A `...` opens a kit dropdown and a right-click opens
// a kit context menu, and the two must hold the same items, so a menu's items
// are written once against these parts and rendered with whichever set its
// trigger needs. The kit's two families take the same props, so swapping the
// set is all it takes.

import {
	ContextMenuItem,
	ContextMenuSeparator,
	ContextMenuShortcut,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuShortcut,
} from "@nustackdev/ui-kit";
import type * as React from "react";

type ItemProps = {
	onSelect?: (e: Event) => void;
	variant?: "default" | "danger";
	className?: string;
	role?: string;
	"aria-checked"?: boolean;
	children?: React.ReactNode;
};

export type MenuParts = {
	Item: React.ComponentType<ItemProps>;
	Separator: React.ComponentType;
	/** An item's shortcut, on its right, by key name. */
	Shortcut: React.ComponentType<{ keys: readonly string[] }>;
};

export const dropdownParts: MenuParts = {
	Item: DropdownMenuItem,
	Separator: DropdownMenuSeparator,
	Shortcut: DropdownMenuShortcut,
};

export const contextParts: MenuParts = {
	Item: ContextMenuItem,
	Separator: ContextMenuSeparator,
	Shortcut: ContextMenuShortcut,
};
