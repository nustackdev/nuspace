// The apps rail: a flat list of apps.
//
// Single depth, so everything the page rail needs a tree for is gone: no
// twisty, no indent guides, no expansion, no ancestor reveal, no ArrowLeft /
// ArrowRight. What survives is the *feel*, because both rails are the same
// furniture on two surfaces:
//
//   * the row navigates. Selection is router-owned (/apps/<id>), the row is
//     a real anchor, and the row shell paints hover and selection so the
//     wash spans the whole line including the controls sitting on it.
//   * hover and selection are two tiers, not one. Neutral wash on hover,
//     accent wash on the open app.
//   * actions live in flow at a fixed width, so a name truncates against a
//     stable edge and only opacity moves on hover.
//   * rename is a kit `Input` in the row. `window.prompt` blocks the tab,
//     cannot be themed, and is not so much a dialog as the absence of one.
//   * `role="tree"` with a roving tabindex. A flat list would be a listbox
//     if it were only ever a list, but it is the same navigation furniture
//     as the page rail and a user should not have to learn it twice.
//
// The one thing this rail has that the page rail does not: a status dot per
// row, in the lane the twisty occupies over there. An app is a running
// program and the list of apps IS the list of what is running, so the state
// belongs in the list rather than only on the open one.
//
// Every class string lives in `design/apps.ts`.

import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuSeparator,
	ContextMenuTrigger,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Input,
	NavLink,
	Skeleton,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Ellipsis, PenLine, Plus, RotateCw, Trash2 } from "lucide-react";
import type * as React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
	appsAction,
	appsActions,
	appsAside,
	appsEmpty,
	appsHeader,
	appsHeaderLabel,
	appsInput,
	appsInputBox,
	appsLabel,
	appsLane,
	appsLaneStyle,
	appsRow,
	appsScroll,
	appsSkeletonRow,
	appsTitle,
	appsTitleEmpty,
} from "../../design/apps";
import { SectionStatusDot } from "../../design/section-status-dot";
import { hrefFor, navigate, onNavClick } from "../../router";
import { type AppRow, appLabel, DETACHED_STATE } from "./types";

type Notify = (payload: Record<string, unknown>) => void;

export function Rail({
	apps,
	loaded,
	attached,
	selectedId,
	renaming,
	onRenameStart,
	onRenameEnd,
	notify,
}: {
	apps: AppRow[];
	loaded: boolean;
	attached: boolean;
	selectedId: string | null;
	renaming: string | null;
	onRenameStart: (id: string) => void;
	onRenameEnd: () => void;
	notify: Notify;
}) {
	// -- focus ----------------------------------------------------------------
	//
	// Roving tabindex: the list is one tab stop and the arrows move inside it.
	const [activeId, setActiveId] = useState<string | null>(selectedId);
	const listRef = useRef<HTMLDivElement | null>(null);

	const tabId = apps.some((a) => a.id === activeId)
		? activeId
		: apps.some((a) => a.id === selectedId)
			? selectedId
			: (apps[0]?.id ?? null);

	// Rows are addressed by data attribute rather than a ref map: `NavLink` is
	// a plain function component and does not take one.
	const focusRow = useCallback((id: string) => {
		setActiveId(id);
		listRef.current?.querySelector<HTMLElement>(`[data-app-id="${CSS.escape(id)}"]`)?.focus();
	}, []);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent, app: AppRow, index: number) => {
			const go = (j: number) => {
				const target = apps[Math.max(0, Math.min(apps.length - 1, j))];
				if (target) focusRow(target.id);
			};
			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					go(index + 1);
					break;
				case "ArrowUp":
					e.preventDefault();
					go(index - 1);
					break;
				case "Home":
					e.preventDefault();
					go(0);
					break;
				case "End":
					e.preventDefault();
					go(apps.length - 1);
					break;
				case "Enter":
				case " ":
					e.preventDefault();
					navigate({ top: "apps", path: [app.id] });
					break;
				case "F2":
					e.preventDefault();
					onRenameStart(app.id);
					break;
				default:
					break;
			}
		},
		[apps, focusRow, onRenameStart],
	);

	const commitRename = useCallback(
		(app: AppRow, name: string) => {
			onRenameEnd();
			const next = name.trim();
			if (!next || next === appLabel(app)) return;
			notify({ op: "on_app_rename", app_id: app.id, name: next });
		},
		[notify, onRenameEnd],
	);

	return (
		<aside className={appsAside}>
			<div className={appsHeader}>
				<span className={appsHeaderLabel}>apps</span>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="New app"
							disabled={!loaded}
							onClick={() => notify({ op: "on_app_create", name: "app" })}
						>
							<Plus />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="bottom">new app</TooltipContent>
				</Tooltip>
			</div>
			<nav aria-label="Apps" className={appsScroll}>
				{!loaded ? (
					<div aria-busy="true">
						{[0, 1, 2].map((i) => (
							<div key={i} className={appsSkeletonRow}>
								<Skeleton className="h-3 w-full rounded-sm" />
							</div>
						))}
					</div>
				) : apps.length === 0 ? (
					<p className={appsEmpty}>no apps yet</p>
				) : (
					<div role="tree" aria-label="Apps" ref={listRef}>
						{apps.map((app, index) => (
							<Row
								key={app.id}
								app={app}
								index={index}
								total={apps.length}
								attached={attached}
								selected={app.id === selectedId}
								tabbable={app.id === tabId}
								renaming={renaming === app.id}
								onFocus={setActiveId}
								onKeyDown={onKeyDown}
								onRenameStart={onRenameStart}
								onRenameCommit={commitRename}
								onRenameCancel={() => {
									onRenameEnd();
									focusRow(app.id);
								}}
								notify={notify}
							/>
						))}
					</div>
				)}
			</nav>
		</aside>
	);
}

function Row({
	app,
	index,
	total,
	attached,
	selected,
	tabbable,
	renaming,
	onFocus,
	onKeyDown,
	onRenameStart,
	onRenameCommit,
	onRenameCancel,
	notify,
}: {
	app: AppRow;
	index: number;
	total: number;
	attached: boolean;
	selected: boolean;
	tabbable: boolean;
	renaming: boolean;
	onFocus: (id: string) => void;
	onKeyDown: (e: React.KeyboardEvent, app: AppRow, index: number) => void;
	onRenameStart: (id: string) => void;
	onRenameCommit: (app: AppRow, name: string) => void;
	onRenameCancel: () => void;
	notify: Notify;
}) {
	const label = appLabel(app);
	const named = app.name.trim().length > 0;
	const state = attached ? (app.status?.state ?? DETACHED_STATE) : DETACHED_STATE;

	const remove = useCallback(() => {
		if (!window.confirm(`delete "${label}"?`)) return;
		notify({ op: "on_app_delete", app_id: app.id });
	}, [app.id, label, notify]);

	const restart = useCallback(() => {
		notify({ op: "on_app_restart", app_id: app.id });
	}, [app.id, notify]);

	const body = (
		// The row, not the anchor, is the tree item: an ARIA tree wants focus
		// on the item and the roving tabindex has to land somewhere that owns
		// aria-level. The anchor stays a real anchor but drops out of the tab
		// order.
		<div
			className={appsRow(selected)}
			role="treeitem"
			tabIndex={tabbable ? 0 : -1}
			data-app-id={app.id}
			aria-selected={selected}
			aria-level={1}
			aria-posinset={index + 1}
			aria-setsize={total}
			onFocus={() => onFocus(app.id)}
			onKeyDown={(e) => onKeyDown(e, app, index)}
		>
			<span className={appsLane} style={appsLaneStyle}>
				<SectionStatusDot status={state} />
			</span>
			{renaming ? (
				<RowInput
					initial={label}
					label={`Rename ${label}`}
					onCommit={(name) => onRenameCommit(app, name)}
					onCancel={onRenameCancel}
				/>
			) : (
				<NavLink
					size="sm"
					active={selected}
					href={hrefFor("apps", [app.id])}
					title={label}
					tabIndex={-1}
					onClick={onNavClick({ top: "apps", path: [app.id] })}
					onDoubleClick={() => onRenameStart(app.id)}
					className={appsLabel}
				>
					<span className={named ? appsTitle : appsTitleEmpty}>{label}</span>
				</NavLink>
			)}
			<div className={appsActions}>
				<IconButton
					variant="ghost"
					size="sm"
					tabIndex={tabbable ? 0 : -1}
					aria-label={`Restart ${label}`}
					disabled={!attached}
					onClick={restart}
					className={appsAction}
				>
					<RotateCw />
				</IconButton>
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							tabIndex={tabbable ? 0 : -1}
							aria-label={`Actions for ${label}`}
							className={appsAction}
						>
							<Ellipsis />
						</IconButton>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="start" className="min-w-40">
						<DropdownMenuItem onSelect={() => onRenameStart(app.id)}>
							<PenLine />
							Rename
						</DropdownMenuItem>
						<DropdownMenuItem disabled={!attached} onSelect={restart}>
							<RotateCw />
							Restart
						</DropdownMenuItem>
						<DropdownMenuSeparator />
						<DropdownMenuItem variant="danger" onSelect={remove}>
							<Trash2 />
							Delete
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		</div>
	);

	return (
		<ContextMenu>
			<ContextMenuTrigger asChild>{body}</ContextMenuTrigger>
			<ContextMenuContent className="min-w-40">
				<ContextMenuItem onSelect={() => navigate({ top: "apps", path: [app.id] })}>
					<PenLine />
					Open
				</ContextMenuItem>
				<ContextMenuSeparator />
				<ContextMenuItem onSelect={() => onRenameStart(app.id)}>
					<PenLine />
					Rename
				</ContextMenuItem>
				<ContextMenuItem disabled={!attached} onSelect={restart}>
					<RotateCw />
					Restart
				</ContextMenuItem>
				<ContextMenuSeparator />
				<ContextMenuItem variant="danger" onSelect={remove}>
					<Trash2 />
					Delete
				</ContextMenuItem>
			</ContextMenuContent>
		</ContextMenu>
	);
}

/**
 * The in-row rename editor. Commits on Enter and on blur (you clicked away,
 * you meant it), cancels on Escape, and selects the initial text so the first
 * keystroke replaces it.
 */
function RowInput({
	initial,
	label,
	onCommit,
	onCancel,
}: {
	initial: string;
	label: string;
	onCommit: (name: string) => void;
	onCancel: () => void;
}) {
	const done = useRef(false);
	// `Input` is a plain function component and takes no ref, so the caret is
	// placed through the wrapper.
	const box = useRef<HTMLSpanElement | null>(null);
	useEffect(() => {
		const el = box.current?.querySelector("input");
		el?.focus();
		el?.select();
	}, []);
	return (
		<span ref={box} className={appsInputBox}>
			<Input
				size="sm"
				aria-label={label}
				defaultValue={initial}
				className={appsInput}
				onBlur={(e) => {
					if (done.current) return;
					done.current = true;
					onCommit(e.currentTarget.value);
				}}
				onKeyDown={(e) => {
					// The list's arrow handling must not see these.
					e.stopPropagation();
					if (e.key === "Enter") {
						e.preventDefault();
						done.current = true;
						onCommit(e.currentTarget.value);
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
