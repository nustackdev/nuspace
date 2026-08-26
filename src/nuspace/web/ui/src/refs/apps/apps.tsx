// AppsRef -- nested folder tree + code editor over Space.apps.
//
// Two-column layout: left rail is a nested tree of groups + apps
// (~260px, collapsible per group), right region is a name input + code
// textarea + Save row.
//
// The slice owns all runtime state (per the lens lesson):
//   value.tree           -- last set_tree payload from the server
//   value.selectedApp    -- last set_app payload {app_id, name, code}
//   dirtyCode / dirtyName -- editor buffers (unsaved edits)
//   expandedGroups       -- Set of group-path keys currently open
//
// Selection is router-owned. URL /apps/<gid>/<gid>/<aid> selects an
// app; the click handler drives navigate(), which fires the
// `on_route_change` effect that ships an `app_select` notify.
//
// All server writes flow through OP_NOTIFY frames with an `op` field
// -- one subscription driver on the server switches on it.

import { OP_NOTIFY } from "@nustackdev/ui-core";
import type { RefEntry, SliceFactory } from "@nustackdev/ui-kit";
import { useStore } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { navigate, useRoute } from "../../router";

type NodeApp = { id: string; name: string };
type NodeGroup = {
	id: string;
	name: string;
	groups: NodeGroup[];
	apps: NodeApp[];
};
type Tree = { groups: NodeGroup[]; apps: NodeApp[] };

type SelectedApp = { app_id: string; name: string; code: string } | null;

type AppsValue = {
	tree: Tree;
	selectedApp: SelectedApp;
};

const EMPTY_TREE: Tree = { groups: [], apps: [] };

const factory: SliceFactory = (path, ctx, _props) => ({
	type: "AppsRef",
	value: { tree: EMPTY_TREE, selectedApp: null } as AppsValue,
	dirtyCode: "",
	dirtyName: "",
	expandedGroups: [] as string[],
	write: (v) =>
		ctx.set((refs) => {
			const slice = refs[path];
			if (!slice) return;
			const p = (v ?? {}) as Record<string, unknown>;
			const op = String(p.op ?? "");
			const value = slice.value as AppsValue;
			if (op === "set_tree") {
				const tree = _coerceTree(p.tree);
				slice.value = { ...value, tree };
				// Auto-expand root ancestors of the current selection so the
				// tree scrolls to it on first paint.
				if (value.selectedApp) {
					const pathTo = _findAppPath(tree, value.selectedApp.app_id);
					if (pathTo) {
						const set = new Set<string>(
							(slice.expandedGroups as string[]) ?? [],
						);
						for (let i = 1; i <= pathTo.length - 1; i++) {
							set.add(pathTo.slice(0, i).join("/"));
						}
						slice.expandedGroups = Array.from(set);
					}
				}
			} else if (op === "set_app") {
				const sel: SelectedApp = {
					app_id: String(p.app_id ?? ""),
					name: String(p.name ?? ""),
					code: String(p.code ?? ""),
				};
				slice.value = { ...value, selectedApp: sel };
				slice.dirtyCode = sel.code;
				slice.dirtyName = sel.name;
			}
		}),
});

function _coerceTree(raw: unknown): Tree {
	if (!raw || typeof raw !== "object") return EMPTY_TREE;
	const r = raw as Record<string, unknown>;
	return {
		groups: _coerceGroups(r.groups),
		apps: _coerceApps(r.apps),
	};
}

function _coerceGroups(raw: unknown): NodeGroup[] {
	if (!Array.isArray(raw)) return [];
	return raw.map((g) => {
		const r = (g ?? {}) as Record<string, unknown>;
		return {
			id: String(r.id ?? ""),
			name: String(r.name ?? ""),
			groups: _coerceGroups(r.groups),
			apps: _coerceApps(r.apps),
		};
	});
}

function _coerceApps(raw: unknown): NodeApp[] {
	if (!Array.isArray(raw)) return [];
	return raw.map((a) => {
		const r = (a ?? {}) as Record<string, unknown>;
		return { id: String(r.id ?? ""), name: String(r.name ?? "") };
	});
}

function _findAppPath(tree: Tree, appId: string): string[] | null {
	for (const app of tree.apps) {
		if (app.id === appId) return [app.id];
	}
	for (const group of tree.groups) {
		const sub = _findInGroup(group, appId);
		if (sub) return [group.id, ...sub];
	}
	return null;
}

function _findInGroup(group: NodeGroup, appId: string): string[] | null {
	for (const app of group.apps) {
		if (app.id === appId) return [app.id];
	}
	for (const g of group.groups) {
		const sub = _findInGroup(g, appId);
		if (sub) return [g.id, ...sub];
	}
	return null;
}

// -- Component ---------------------------------------------------------------

function AppsView({ path }: { path: string }) {
	const value = useStore(
		(s) => (s.refs[path]?.value as AppsValue | undefined) ?? null,
	);
	const dirtyCode = useStore(
		(s) => (s.refs[path]?.dirtyCode as string | undefined) ?? "",
	);
	const dirtyName = useStore(
		(s) => (s.refs[path]?.dirtyName as string | undefined) ?? "",
	);
	const expandedList = useStore(
		(s) => (s.refs[path]?.expandedGroups as string[] | undefined) ?? [],
	);
	const set = useStore.setState;
	const send = useStore((s) => s.send);
	const route = useRoute();

	const tree = value?.tree ?? EMPTY_TREE;
	const selectedApp = value?.selectedApp ?? null;

	const expanded = useMemo(() => new Set(expandedList), [expandedList]);

	// The router path under /apps is [gid..., aid]. Whenever it changes,
	// notify the server so it ships the app payload.
	const selectionKey = route.path.join("/");
	// biome-ignore lint/correctness/useExhaustiveDependencies: selectionKey is the whole point -- it captures the array-content change; route.path is only used inside the effect and would trigger on every render if listed.
	useEffect(() => {
		if (route.top !== "apps") return;
		if (route.path.length === 0) return;
		send({
			op: OP_NOTIFY,
			ref: path,
			payload: { op: "app_select", path: route.path },
		});
	}, [selectionKey, route.top, path, send]);

	const toggleExpanded = useCallback(
		(groupKey: string) => {
			set((s) => {
				const slice = s.refs[path];
				if (!slice) return s;
				const next = new Set((slice.expandedGroups as string[]) ?? []);
				if (next.has(groupKey)) next.delete(groupKey);
				else next.add(groupKey);
				return {
					...s,
					refs: {
						...s.refs,
						[path]: { ...slice, expandedGroups: Array.from(next) },
					},
				};
			});
		},
		[path],
	);

	const selectApp = useCallback((nodePath: string[]) => {
		navigate({ top: "apps", path: nodePath });
	}, []);

	const setDirtyCode = useCallback(
		(code: string) => {
			set((s) => {
				const slice = s.refs[path];
				if (!slice) return s;
				return {
					...s,
					refs: { ...s.refs, [path]: { ...slice, dirtyCode: code } },
				};
			});
		},
		[path],
	);

	const setDirtyName = useCallback(
		(name: string) => {
			set((s) => {
				const slice = s.refs[path];
				if (!slice) return s;
				return {
					...s,
					refs: { ...s.refs, [path]: { ...slice, dirtyName: name } },
				};
			});
		},
		[path],
	);

	const notify = useCallback(
		(payload: Record<string, unknown>) => {
			send({ op: OP_NOTIFY, ref: path, payload });
		},
		[path, send],
	);

	const saveEdit = useCallback(() => {
		if (!selectedApp) return;
		if (route.path.length === 0) return;
		notify({
			op: "app_edit",
			path: route.path,
			name: dirtyName,
			code: dirtyCode,
		});
	}, [selectedApp, dirtyName, dirtyCode, notify, route.path]);

	// Editor: intercept Tab so it inserts a tab instead of shifting focus.
	const onEditorKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
			if (e.key === "Tab") {
				e.preventDefault();
				const el = e.currentTarget;
				const start = el.selectionStart;
				const end = el.selectionEnd;
				const next = `${el.value.slice(0, start)}\t${el.value.slice(end)}`;
				setDirtyCode(next);
				requestAnimationFrame(() => {
					el.selectionStart = start + 1;
					el.selectionEnd = start + 1;
				});
			} else if ((e.key === "s" || e.key === "S") && (e.metaKey || e.ctrlKey)) {
				e.preventDefault();
				saveEdit();
			}
		},
		[saveEdit, setDirtyCode],
	);

	const dirty = useMemo(() => {
		if (!selectedApp) return false;
		return dirtyCode !== selectedApp.code || dirtyName !== selectedApp.name;
	}, [selectedApp, dirtyCode, dirtyName]);

	return (
		<div className="flex-1 min-h-0 min-w-0 flex">
			<TreeRail
				tree={tree}
				expanded={expanded}
				toggleExpanded={toggleExpanded}
				selectApp={selectApp}
				selectedPath={route.path}
				notify={notify}
			/>
			<div className="flex-1 min-w-0 flex flex-col bg-background">
				{selectedApp ? (
					<Editor
						name={dirtyName}
						code={dirtyCode}
						dirty={dirty}
						onName={setDirtyName}
						onCode={setDirtyCode}
						onKeyDown={onEditorKeyDown}
						onSave={saveEdit}
					/>
				) : (
					<div className="flex-1 flex items-center justify-center text-sm text-muted-foreground font-mono">
						select an app on the left to edit
					</div>
				)}
			</div>
		</div>
	);
}

// -- Tree rail ---------------------------------------------------------------

function TreeRail({
	tree,
	expanded,
	toggleExpanded,
	selectApp,
	selectedPath,
	notify,
}: {
	tree: Tree;
	expanded: Set<string>;
	toggleExpanded: (key: string) => void;
	selectApp: (path: string[]) => void;
	selectedPath: string[];
	notify: (payload: Record<string, unknown>) => void;
}) {
	return (
		<aside className="w-64 shrink-0 border-r border-border/60 h-full flex flex-col bg-card">
			<div className="px-3 py-2 flex items-center justify-between border-b border-border/60">
				<span className="text-xs uppercase tracking-wider text-muted-foreground font-mono">
					apps
				</span>
				<div className="flex items-center gap-1">
					<RootMenuButton notify={notify} kind="group" />
					<RootMenuButton notify={notify} kind="app" />
				</div>
			</div>
			<div className="flex-1 min-h-0 overflow-y-auto py-1">
				{tree.groups.map((g) => (
					<GroupNode
						key={g.id}
						group={g}
						parentPath={[]}
						depth={0}
						expanded={expanded}
						toggleExpanded={toggleExpanded}
						selectApp={selectApp}
						selectedPath={selectedPath}
						notify={notify}
					/>
				))}
				{tree.apps.map((a) => (
					<AppNode
						key={a.id}
						app={a}
						parentPath={[]}
						depth={0}
						selectApp={selectApp}
						selectedPath={selectedPath}
						notify={notify}
					/>
				))}
				{tree.groups.length === 0 && tree.apps.length === 0 ? (
					<div className="px-3 py-2 text-xs text-muted-foreground font-mono">
						empty. use + to add.
					</div>
				) : null}
			</div>
		</aside>
	);
}

function RootMenuButton({
	notify,
	kind,
}: {
	notify: (payload: Record<string, unknown>) => void;
	kind: "app" | "group";
}) {
	return (
		<button
			type="button"
			className="text-xs text-muted-foreground hover:text-text-primary font-mono px-2 py-0.5 rounded-md hover:bg-muted/40"
			onClick={() => {
				const name = window.prompt(
					kind === "app" ? "new app name" : "new group name",
					kind === "app" ? "app" : "group",
				);
				if (!name) return;
				if (kind === "app") {
					notify({ op: "app_create", group_path: [], name });
				} else {
					notify({ op: "group_create", parent_path: [], name });
				}
			}}
			title={kind === "app" ? "add app at root" : "add group at root"}
		>
			+{kind[0]}
		</button>
	);
}

function GroupNode({
	group,
	parentPath,
	depth,
	expanded,
	toggleExpanded,
	selectApp,
	selectedPath,
	notify,
}: {
	group: NodeGroup;
	parentPath: string[];
	depth: number;
	expanded: Set<string>;
	toggleExpanded: (key: string) => void;
	selectApp: (path: string[]) => void;
	selectedPath: string[];
	notify: (payload: Record<string, unknown>) => void;
}) {
	const nodePath = [...parentPath, group.id];
	const key = nodePath.join("/");
	const isOpen = expanded.has(key);
	const indentStyle = { paddingLeft: `${8 + depth * 12}px` };

	const rename = () => {
		const name = window.prompt("rename group", group.name);
		if (!name || name === group.name) return;
		notify({ op: "group_rename", path: nodePath, name });
	};
	const remove = () => {
		if (!window.confirm(`delete group "${group.name}" and everything in it?`))
			return;
		notify({ op: "group_delete", path: nodePath });
	};
	const addApp = () => {
		const name = window.prompt("new app name", "app");
		if (!name) return;
		notify({ op: "app_create", group_path: nodePath, name });
	};
	const addGroup = () => {
		const name = window.prompt("new group name", "group");
		if (!name) return;
		notify({ op: "group_create", parent_path: nodePath, name });
	};

	return (
		<div>
			<div
				className="group/row flex items-center gap-1 text-sm font-mono hover:bg-muted/40 py-1 pr-2"
				style={indentStyle}
			>
				<button
					type="button"
					onClick={() => toggleExpanded(key)}
					className="w-4 text-xs text-muted-foreground"
					aria-label={isOpen ? "collapse group" : "expand group"}
				>
					{isOpen ? "v" : ">"}
				</button>
				<span className="flex-1 truncate">{group.name}</span>
				<RowActions
					items={[
						{ label: "+app", onClick: addApp },
						{ label: "+grp", onClick: addGroup },
						{ label: "ren", onClick: rename },
						{ label: "del", onClick: remove, danger: true },
					]}
				/>
			</div>
			{isOpen ? (
				<div>
					{group.groups.map((g) => (
						<GroupNode
							key={g.id}
							group={g}
							parentPath={nodePath}
							depth={depth + 1}
							expanded={expanded}
							toggleExpanded={toggleExpanded}
							selectApp={selectApp}
							selectedPath={selectedPath}
							notify={notify}
						/>
					))}
					{group.apps.map((a) => (
						<AppNode
							key={a.id}
							app={a}
							parentPath={nodePath}
							depth={depth + 1}
							selectApp={selectApp}
							selectedPath={selectedPath}
							notify={notify}
						/>
					))}
				</div>
			) : null}
		</div>
	);
}

function AppNode({
	app,
	parentPath,
	depth,
	selectApp,
	selectedPath,
	notify,
}: {
	app: NodeApp;
	parentPath: string[];
	depth: number;
	selectApp: (path: string[]) => void;
	selectedPath: string[];
	notify: (payload: Record<string, unknown>) => void;
}) {
	const nodePath = [...parentPath, app.id];
	const key = nodePath.join("/");
	const active = selectedPath.join("/") === key;
	const indentStyle = { paddingLeft: `${24 + depth * 12}px` };

	const rename = () => {
		const name = window.prompt("rename app", app.name);
		if (!name || name === app.name) return;
		notify({ op: "app_rename", path: nodePath, name });
	};
	const remove = () => {
		if (!window.confirm(`delete app "${app.name}"?`)) return;
		notify({ op: "app_delete", path: nodePath });
	};

	return (
		// biome-ignore lint/a11y/useSemanticElements: RowActions renders <button>s inside, so this outer node cannot itself be a <button> (nested buttons are invalid HTML). Div + role="button" is the standard workaround.
		<div
			className={`group/row flex items-center gap-1 text-sm font-mono py-1 pr-2 cursor-pointer ${
				active
					? "bg-primary/10 text-text-primary"
					: "text-text-primary hover:bg-muted/40"
			}`}
			style={indentStyle}
			onClick={() => selectApp(nodePath)}
			onKeyDown={(e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					selectApp(nodePath);
				}
			}}
			role="button"
			tabIndex={0}
		>
			<span className="w-3 text-xs text-muted-foreground">·</span>
			<span className="flex-1 truncate">{app.name}</span>
			<RowActions
				items={[
					{ label: "ren", onClick: rename },
					{ label: "del", onClick: remove, danger: true },
				]}
			/>
		</div>
	);
}

function RowActions({
	items,
}: {
	items: { label: string; onClick: () => void; danger?: boolean }[];
}) {
	return (
		<div className="opacity-0 group-hover/row:opacity-100 flex items-center gap-1 transition-opacity">
			{items.map((it) => (
				<button
					key={it.label}
					type="button"
					onClick={(e) => {
						e.stopPropagation();
						it.onClick();
					}}
					className={`text-[10px] uppercase tracking-wide font-mono px-1.5 py-0.5 rounded ${
						it.danger
							? "text-destructive hover:bg-destructive/10"
							: "text-muted-foreground hover:bg-muted/60 hover:text-text-primary"
					}`}
				>
					{it.label}
				</button>
			))}
		</div>
	);
}

// -- Editor ------------------------------------------------------------------

function Editor({
	name,
	code,
	dirty,
	onName,
	onCode,
	onKeyDown,
	onSave,
}: {
	name: string;
	code: string;
	dirty: boolean;
	onName: (v: string) => void;
	onCode: (v: string) => void;
	onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
	onSave: () => void;
}) {
	const areaRef = useRef<HTMLTextAreaElement | null>(null);
	const [saved, setSaved] = useState(false);

	useEffect(() => {
		if (dirty) setSaved(false);
	}, [dirty]);

	const doSave = () => {
		onSave();
		setSaved(true);
	};

	return (
		<div className="flex-1 min-h-0 min-w-0 flex flex-col">
			<div className="px-4 py-2 border-b border-border/60 flex items-center gap-2">
				<label
					htmlFor="apps-editor-name"
					className="text-xs uppercase tracking-wider text-muted-foreground font-mono"
				>
					name
				</label>
				<input
					id="apps-editor-name"
					type="text"
					value={name}
					onChange={(e) => onName(e.target.value)}
					className="flex-1 bg-transparent border border-border/60 rounded-md px-2 py-1 text-sm font-mono focus:outline-none focus:border-primary"
				/>
				<button
					type="button"
					onClick={doSave}
					disabled={!dirty}
					className={`text-xs uppercase tracking-wider font-mono px-3 py-1 rounded-md ${
						dirty
							? "bg-primary text-primary-foreground hover:opacity-90"
							: "bg-muted/40 text-muted-foreground cursor-not-allowed"
					}`}
				>
					{dirty ? "save" : saved ? "saved" : "clean"}
				</button>
			</div>
			<textarea
				ref={areaRef}
				value={code}
				onChange={(e) => onCode(e.target.value)}
				onKeyDown={onKeyDown}
				spellCheck={false}
				className="flex-1 min-h-0 w-full resize-none bg-background text-text-primary font-mono text-sm leading-6 p-4 focus:outline-none"
				placeholder="# python source (parsed on save)"
			/>
		</div>
	);
}

export const AppsRef: RefEntry = { factory, component: AppsView };
