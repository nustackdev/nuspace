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
// The furniture itself is `components/rail` and every class string is in
// `design/rail.ts`, both shared with the pages rail: this is the same row at
// depth zero. What is left here is what an app is.

import {
	ContextMenuItem,
	ContextMenuSeparator,
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
	IconButton,
	Skeleton,
} from "@nustackdev/ui-kit";
import { Ellipsis, PenLine, RotateCw, Trash2 } from "lucide-react";
import type * as React from "react";
import { useCallback, useMemo } from "react";
import { hrefFor, navigate, onNavClick } from "../../app/router";
import {
	RailHeader,
	RailRow,
	RailRowInput,
	RailRowLink,
	SectionStatusDot,
	useRailFocus,
} from "../../components";
import {
	railAction,
	railAside,
	railEmpty,
	railScroll,
	railSkeletonBar,
	railSkeletonRow,
	railTitle,
	railTitleEmpty,
} from "../../design";
import type { Notify } from "./ops";
import { type AppRow, appLabel, DETACHED_STATE } from "./types";

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
	const ids = useMemo(() => apps.map((a) => a.id), [apps]);
	const { containerRef, tabKey, setActiveKey, focusKey, handleArrows } = useRailFocus(
		ids,
		selectedId,
	);

	const onKeyDown = useCallback(
		(e: React.KeyboardEvent, app: AppRow, index: number) => {
			if (handleArrows(e, index)) return;
			switch (e.key) {
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
		[handleArrows, onRenameStart],
	);

	const commitRename = useCallback(
		(app: AppRow, name: string) => {
			onRenameEnd();
			const next = name.trim();
			if (!next || next === appLabel(app)) return;
			notify("app.rename", { app_id: app.id, name: next });
		},
		[notify, onRenameEnd],
	);

	return (
		<aside className={railAside}>
			<RailHeader
				label="apps"
				addLabel="New app"
				addTooltip="new app"
				addDisabled={!loaded}
				onAdd={() => notify("app.create", { name: "app" })}
			/>
			<nav aria-label="Apps" className={railScroll}>
				{!loaded ? (
					<div aria-busy="true">
						{[0, 1, 2].map((i) => (
							<div key={i} className={railSkeletonRow(true)}>
								<Skeleton className={railSkeletonBar} />
							</div>
						))}
					</div>
				) : apps.length === 0 ? (
					<p className={railEmpty}>no apps yet</p>
				) : (
					<div role="tree" aria-label="Apps" ref={containerRef}>
						{apps.map((app, index) => (
							<Row
								key={app.id}
								app={app}
								index={index}
								total={apps.length}
								attached={attached}
								selected={app.id === selectedId}
								tabbable={app.id === tabKey}
								renaming={renaming === app.id}
								onFocus={setActiveKey}
								onKeyDown={onKeyDown}
								onRenameStart={onRenameStart}
								onRenameCommit={commitRename}
								onRenameCancel={() => {
									onRenameEnd();
									focusKey(app.id);
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
		notify("app.delete", { app_id: app.id });
	}, [app.id, label, notify]);

	const restart = useCallback(() => {
		notify("app.restart", { app_id: app.id });
	}, [app.id, notify]);

	return (
		<RailRow
			rowKey={app.id}
			selected={selected}
			tabbable={tabbable}
			level={1}
			posinset={index + 1}
			setsize={total}
			onFocus={() => onFocus(app.id)}
			onKeyDown={(e) => onKeyDown(e, app, index)}
			lane={<SectionStatusDot status={state} />}
			label={
				renaming ? (
					<RailRowInput
						initial={label}
						label={`Rename ${label}`}
						onCommit={(name) => onRenameCommit(app, name)}
						onCancel={onRenameCancel}
					/>
				) : (
					<RailRowLink
						href={hrefFor("apps", [app.id])}
						label={label}
						selected={selected}
						titleClassName={named ? railTitle : railTitleEmpty}
						onClick={onNavClick({ top: "apps", path: [app.id] })}
						onDoubleClick={() => onRenameStart(app.id)}
					/>
				)
			}
			actions={
				<>
					<IconButton
						variant="ghost"
						size="sm"
						tabIndex={tabbable ? 0 : -1}
						aria-label={`Restart ${label}`}
						disabled={!attached}
						onClick={restart}
						className={railAction}
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
								className={railAction}
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
				</>
			}
			menu={
				<>
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
				</>
			}
		/>
	);
}
