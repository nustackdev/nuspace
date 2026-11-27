// The one header every mobile screen wears: the sidebar, a plane, a desk.
// Same height, same place, same lanes, so moving between screens never moves
// the top of the screen.
//
//   | lead | title ............................ | actions |
//
//   lead     the sidebar rows' 32px lane, its icon 20px, so the icon sits
//            over the rows' icons. Left out, the title starts at the icons'
//            edge, as the sidebar's wordmark does
//   title    18px, one line, truncating
//   actions  44px tap targets with 20px glyphs at the right edge, the last
//            one in the rows' trail lane
//
// It is out of the screen's scroller, a sibling above it: what scrolls goes
// under it, and it never scrolls away. The top safe area is the screen's own
// padding, so every header starts at the same y.

import { IconButton } from "@nustackdev/ui-kit";
import type * as React from "react";
import {
	mobileHeader,
	mobileHeaderActions,
	mobileHeaderButton,
	mobileHeaderCount,
	mobileHeaderLead,
	mobileHeaderTitle,
} from "../design";

export function MobileHeader({
	icon,
	title,
	label,
	actions,
}: {
	/** The leading icon, in the rows' lead lane. */
	icon?: React.ReactNode;
	title: React.ReactNode;
	/** The title's text when `title` is not plain text, for the heading's name. */
	label?: string;
	/** The buttons at the right edge, left to right. */
	actions?: React.ReactNode;
}) {
	return (
		<header className={mobileHeader} data-mobile-header="">
			{icon ? (
				<span aria-hidden="true" className={mobileHeaderLead} data-header-lead="">
					{icon}
				</span>
			) : null}
			<h1 className={mobileHeaderTitle} aria-label={label} data-header-title="">
				{title}
			</h1>
			{actions ? <div className={mobileHeaderActions}>{actions}</div> : null}
		</header>
	);
}

/** One of the header's actions: a 44px tap target around a 20px glyph. */
export function HeaderButton({
	label,
	onClick,
	disabled,
	children,
	...rest
}: {
	label: string;
	onClick: () => void;
	disabled?: boolean;
	children: React.ReactNode;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "children">) {
	return (
		<IconButton
			variant="ghost"
			ring="inset"
			{...rest}
			aria-label={label}
			disabled={disabled}
			onClick={onClick}
			className={mobileHeaderButton}
			data-header-action=""
		>
			{children}
		</IconButton>
	);
}

/** A figure between the actions, eg the pager's n/m. */
export function HeaderCount({ children }: { children: React.ReactNode }) {
	return (
		<span className={mobileHeaderCount} data-header-count="">
			{children}
		</span>
	);
}
