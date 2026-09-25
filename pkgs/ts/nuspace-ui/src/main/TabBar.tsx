// The tab bar over a split: one tab per pane, in pane order.
//
// Only drawn with two or more panes, and then it stands in for every pane's
// own bar: the title, the `...` settings (the same PaneMenu) and close, per
// pane, in one strip.
//
// Focus runs both ways through the router's focus state. Focusing a pane marks
// its tab active and scrolls the tab into view; clicking a tab focuses its
// pane and scrolls the strip until that pane is on screen.
//
// Keyboard (a11y.md §3 Tabs): Tab enters on the active tab, arrows and
// Home / End move and activate (auto-activation: focusing a pane is cheap),
// Tab leaves. On a tab, F2 renames, Delete closes, and Shift+F10 or the menu
// key opens its settings. The `...` and close buttons stay out of the tab
// order: they are the mouse's way to the same three things.

import { IconButton, Input } from "@nustackdev/ui-kit";
import { X } from "lucide-react";
import type * as React from "react";
import { useEffect, useRef, useState } from "react";
import { closePane, focusPane } from "../core/router";
import {
	paneBarButton,
	tabActions,
	tabBar,
	tabCell,
	tabIcon,
	tabInput,
	tabInputBox,
	tabTitle,
	tabTrigger,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { parseIcon } from "../icon/parse";
import { TITLE_FALLBACK } from "../pane/Pane";
import { PaneMenu } from "../pane/PaneMenu";
import type { ActivePlane } from "../plane/types";
import { OverflowTooltip } from "../shell/OverflowTooltip";

/** Smooth, unless the user asked for less motion (motion.md). */
function scrollBehavior(): ScrollBehavior {
	return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

/** Bring the child of `host` tagged `attr=id` into view, only as far as needed. */
function reveal(host: HTMLElement | null, attr: string, id: string): void {
	host
		?.querySelector<HTMLElement>(`:scope > [${attr}="${CSS.escape(id)}"]`)
		?.scrollIntoView({ inline: "nearest", block: "nearest", behavior: scrollBehavior() });
}

export function TabBar({
	routes,
	planes,
	focused,
	stripRef,
	onMeta,
	onRename,
}: {
	routes: string[];
	planes: Record<string, ActivePlane>;
	focused: string;
	/** The strip of panes, to scroll a pane into view. */
	stripRef: React.RefObject<HTMLDivElement | null>;
	onMeta: (planeId: string, patch: Record<string, unknown>) => void;
	onRename: (planeId: string, title: string) => void;
}) {
	const barRef = useRef<HTMLDivElement | null>(null);
	const [editing, setEditing] = useState<string | null>(null);
	const [menuOf, setMenuOf] = useState<string | null>(null);

	// Pane focus moved (a click, a caret tabbed in, a close, a new pane):
	// bring its tab into view if the bar is scrolled away from it.
	// biome-ignore lint/correctness/useExhaustiveDependencies: routes is compared by its joined key.
	useEffect(() => {
		if (focused) reveal(barRef.current, "data-tab", focused);
	}, [focused, routes.join("+")]);

	/** Activate a tab: focus its pane and scroll the strip to it. */
	const activate = (id: string) => {
		focusPane(id);
		reveal(stripRef.current, "data-pane", id);
	};

	/** Put the caret on a tab, once it is drawn (it may be mid-rename). */
	const focusTab = (id: string) => {
		requestAnimationFrame(() => {
			barRef.current
				?.querySelector<HTMLElement>(`[data-tab="${CSS.escape(id)}"] [role="tab"]`)
				?.focus();
		});
	};

	/** Close a tab; a keyboard close keeps the caret in the bar. */
	const close = (id: string, fromKeyboard = false) => {
		closePane(id);
		if (!fromKeyboard) return;
		// After the router has moved focus to the neighbour and re-rendered.
		requestAnimationFrame(() => {
			const bar = barRef.current;
			const active = bar?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
			active?.focus();
		});
	};

	const onKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, i: number) => {
		const id = routes[i];
		let next = -1;
		if (e.key === "ArrowRight") next = (i + 1) % routes.length;
		else if (e.key === "ArrowLeft") next = (i - 1 + routes.length) % routes.length;
		else if (e.key === "Home") next = 0;
		else if (e.key === "End") next = routes.length - 1;
		else if (e.key === "F2") {
			e.preventDefault();
			if (planes[id]) setEditing(id);
			return;
		} else if (e.key === "Delete") {
			e.preventDefault();
			close(id, true);
			return;
		} else if (e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) {
			e.preventDefault();
			if (planes[id]) setMenuOf(id);
			return;
		} else return;
		e.preventDefault();
		activate(routes[next]);
		focusTab(routes[next]);
	};

	return (
		<div ref={barRef} role="tablist" aria-label="Open planes" className={tabBar}>
			{routes.map((id, i) => {
				const plane = planes[id] ?? null;
				const title = plane?.title || TITLE_FALLBACK;
				const active = id === focused;
				const icon = parseIcon(plane?.meta.icon);
				return (
					// biome-ignore lint/a11y/noStaticElementInteractions: middle-click close is a mouse shortcut on the whole cell; the keyboard closes with Delete on the tab
					<div
						key={id}
						role="presentation"
						data-tab={id}
						className={tabCell(active)}
						// Middle-click closes. Swallow the press too, or the
						// browser starts its autoscroll.
						onMouseDown={(e) => {
							if (e.button === 1) e.preventDefault();
						}}
						onAuxClick={(e) => {
							if (e.button !== 1) return;
							e.preventDefault();
							close(id);
						}}
					>
						{editing === id ? (
							<TabRenameInput
								initial={plane?.title ?? ""}
								label={`Rename ${title}`}
								onCommit={(value, byKey) => {
									setEditing(null);
									const next = value.trim();
									if (next && next !== (plane?.title ?? "").trim()) onRename(id, next);
									if (byKey) focusTab(id);
								}}
								onCancel={() => {
									setEditing(null);
									focusTab(id);
								}}
							/>
						) : (
							<OverflowTooltip label={title} side="bottom">
								<button
									type="button"
									role="tab"
									aria-selected={active}
									tabIndex={active ? 0 : -1}
									className={tabTrigger}
									onClick={() => activate(id)}
									onDoubleClick={() => {
										if (plane) setEditing(id);
									}}
									onKeyDown={(e) => onKeyDown(e, i)}
								>
									{icon ? <PlaneIcon icon={icon} className={tabIcon} /> : null}
									<span className={tabTitle}>{title}</span>
								</button>
							</OverflowTooltip>
						)}
						<span className={tabActions(active)}>
							<PaneMenu
								planeId={id}
								meta={plane?.meta ?? null}
								onChange={(patch) => onMeta(id, patch)}
								onRename={() => setEditing(id)}
								open={menuOf === id}
								onOpenChange={(open) => setMenuOf(open ? id : null)}
								className={paneBarButton}
								tabIndex={-1}
							/>
							<IconButton
								variant="ghost"
								size="sm"
								aria-label={`Close ${title}`}
								tabIndex={-1}
								onClick={() => close(id)}
								className={paneBarButton}
							>
								<X />
							</IconButton>
						</span>
					</div>
				);
			})}
		</div>
	);
}

/**
 * The inline title editor. Commits on Enter and on blur (you clicked away,
 * you meant it), cancels on Escape, and selects the text so the first
 * keystroke replaces it. Same contract as the rail's.
 */
function TabRenameInput({
	initial,
	label,
	onCommit,
	onCancel,
}: {
	initial: string;
	label: string;
	/** `byKey`: Enter, so the caret goes back to the tab. A blur leaves it be. */
	onCommit: (value: string, byKey: boolean) => void;
	onCancel: () => void;
}) {
	const done = useRef(false);
	// `Input` takes no ref, so the caret is placed through the wrapper.
	const box = useRef<HTMLSpanElement | null>(null);
	useEffect(() => {
		const el = box.current?.querySelector("input");
		el?.focus();
		el?.select();
	}, []);
	return (
		<span ref={box} className={tabInputBox}>
			<Input
				size="sm"
				aria-label={label}
				defaultValue={initial}
				className={tabInput}
				onBlur={(e) => {
					if (done.current) return;
					done.current = true;
					onCommit(e.currentTarget.value, false);
				}}
				onKeyDown={(e) => {
					e.stopPropagation();
					if (e.key === "Enter") {
						e.preventDefault();
						done.current = true;
						onCommit(e.currentTarget.value, true);
					} else if (e.key === "Escape") {
						e.preventDefault();
						done.current = true;
						onCancel();
					}
				}}
			/>
		</span>
	);
}
