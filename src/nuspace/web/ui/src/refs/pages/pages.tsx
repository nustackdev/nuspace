// PagesRef -- nested page tree + section canvas over Space.pages.
//
// Two-column layout, Notion-style: left rail is a nested tree of pages
// (~260px, expandable), right region is one page canvas.
//
// Sections are NOT in the sidebar. They are parts of a page, not
// navigable entities, so they only ever render inside the canvas.
//
// The slice owns all runtime state (per the lens lesson -- the server is
// stateless between notifies):
//   value.tree      -- last set_tree payload
//   value.page      -- last set_page payload {page_id, path, title, mode, sections}
//   mode            -- browser-owned code/display toggle
//   expanded        -- page-path keys currently open in the rail
//   drafts          -- per-section unsaved editor buffers
//   sectionPaths    -- wire paths of the section field slices we registered
//
// Selection is router-owned. URL /pages/<pid>/<pid> selects a page; the
// click handler drives navigate(), the route effect ships on_page_select.
// /pages with no segments is the root page, which is a real page and may
// carry sections of its own.
//
// Section field registration: `set_page` carries a MountField list per
// section. The kit's store.mount() only builds slices for the static
// mount envelope and has no post-mount registration action, so we build
// them here: ctx.set mutates draft.refs directly, and the kit publicly
// exports `factories` + `FieldView`. Inbound frames route to those
// slices normally (same refs map), outbound goes through ctx.send, and
// disposeAll cleans them up on unmount. We dispose stale ones ourselves
// whenever a new set_page lands.
//
// We never remount the shell on navigation -- that would wipe Apps and
// Lens state (the mvp did exactly that).

import type { MountField } from "@nustackdev/ui-core";
import { OP_NOTIFY } from "@nustackdev/ui-core";
import type { RefEntry, SliceFactory } from "@nustackdev/ui-kit";
import { factories, FieldView, useStore } from "@nustackdev/ui-kit";
import { useCallback, useEffect, useMemo } from "react";
import { navigate, useRoute } from "../../router";

type PageNode = { id: string | null; title: string; pages: PageNode[] };

type SectionEntry = {
	id: string;
	name: string;
	snippet: string;
	error: string | null;
	fields: MountField[];
};

type ActivePage = {
	page_id: string | null;
	path: string[];
	title: string;
	mode: Mode;
	sections: SectionEntry[];
};

type Mode = "code" | "display";

type PagesValue = {
	tree: PageNode;
	page: ActivePage | null;
};

const EMPTY_TREE: PageNode = { id: null, title: "", pages: [] };

const SNIPPET_PLACEHOLDER = `# python expression returning a Nu term.
# in scope: nu, Space, path  (path == "sections.<this section id>")
nu.ui.StatRef(path + ".echo").set_value(nu.Str("")) >> nu.ReactForever(
    nu.ui.InputRef(path + ".text").changed(),
    nu.ui.StatRef(path + ".echo").set_value(nu.Str(nu.ui.InputRef(path + ".text"))),
)`;

// -- Slice -------------------------------------------------------------------

const factory: SliceFactory = (path, ctx, _props) => ({
	type: "PagesRef",
	value: { tree: EMPTY_TREE, page: null } as PagesValue,
	mode: "display" as Mode,
	expanded: [] as string[],
	drafts: {} as Record<string, { name: string; snippet: string }>,
	sectionPaths: [] as string[],
	write: (v) =>
		ctx.set((refs) => {
			const slice = refs[path];
			if (!slice) return;
			const p = (v ?? {}) as Record<string, unknown>;
			const op = String(p.op ?? "");
			const value = slice.value as PagesValue;

			if (op === "set_tree") {
				slice.value = { ...value, tree: _coerceNode(p.tree, null) };
				return;
			}
			if (op !== "set_page") return;

			const sections = _coerceSections(p.sections);
			const page: ActivePage = {
				page_id: p.page_id == null ? null : String(p.page_id),
				path: _coerceStrs(p.path),
				title: String(p.title ?? ""),
				mode: p.mode === "display" ? "display" : "code",
				sections,
			};

			// Drop the section slices from the previous ship before
			// registering this one's -- switching pages or leaving display
			// mode must not leak slices into the refs map.
			for (const stale of (slice.sectionPaths as string[]) ?? []) {
				const s = refs[stale];
				if (s?.dispose) {
					try {
						s.dispose();
					} catch (err) {
						console.warn(`nuspace: dispose threw for ${stale}`, err);
					}
				}
				delete refs[stale];
			}

			const registered: string[] = [];
			for (const section of sections) {
				for (const f of section.fields) {
					const build = factories[f.type];
					if (!build) {
						console.warn(`nuspace: no factory for section field "${f.type}"`);
						continue;
					}
					const childPaths = (f.fields ?? []).map((c) => c.path);
					refs[f.path] = build(f.path, ctx, f.props, childPaths);
					registered.push(f.path);
				}
			}

			slice.value = { ...value, page };
			slice.sectionPaths = registered;
			// Drafts are deliberately left alone -- a re-ship (rename, a
			// sibling section save) must not discard unsaved editor text.
			// The component clears a draft when its own save lands.
		}),
	dispose: () => {
		// Section slices live in the same refs map, so the kit's disposeAll
		// already reaches them. Nothing extra to release here.
	},
});

// -- Coercion (msgpack payloads are untyped) ---------------------------------

function _coerceStrs(raw: unknown): string[] {
	if (!Array.isArray(raw)) return [];
	return raw.map((s) => String(s));
}

function _coerceNode(raw: unknown, fallbackId: string | null): PageNode {
	if (!raw || typeof raw !== "object") {
		return { id: fallbackId, title: "", pages: [] };
	}
	const r = raw as Record<string, unknown>;
	const kids = Array.isArray(r.pages) ? r.pages : [];
	return {
		id: r.id == null ? null : String(r.id),
		title: String(r.title ?? ""),
		pages: kids.map((k) => _coerceNode(k, null)),
	};
}

function _coerceSections(raw: unknown): SectionEntry[] {
	if (!Array.isArray(raw)) return [];
	const out: SectionEntry[] = [];
	for (const s of raw) {
		if (!s || typeof s !== "object") continue;
		const r = s as Record<string, unknown>;
		out.push({
			id: String(r.id ?? ""),
			name: String(r.name ?? ""),
			snippet: String(r.snippet ?? ""),
			error: r.error == null ? null : String(r.error),
			fields: _coerceFields(r.fields),
		});
	}
	return out;
}

function _coerceFields(raw: unknown): MountField[] {
	if (!Array.isArray(raw)) return [];
	const out: MountField[] = [];
	for (const f of raw) {
		if (!f || typeof f !== "object") continue;
		const r = f as Record<string, unknown>;
		const path = String(r.path ?? "");
		const type = String(r.type ?? "");
		if (!path || !type) continue;
		const entry: MountField = { path, type };
		if (r.props && typeof r.props === "object") {
			entry.props = r.props as Record<string, unknown>;
		}
		if (Array.isArray(r.fields)) entry.fields = _coerceFields(r.fields);
		out.push(entry);
	}
	return out;
}

// -- Slice mutation helpers --------------------------------------------------

function useSliceSetter(path: string) {
	const set = useStore.setState;
	return useCallback(
		(patch: Record<string, unknown>) => {
			set((s) => {
				const slice = s.refs[path];
				if (!slice) return s;
				return { ...s, refs: { ...s.refs, [path]: { ...slice, ...patch } } };
			});
		},
		[path, set],
	);
}

// -- Component ---------------------------------------------------------------

function PagesView({ path }: { path: string }) {
	const value = useStore(
		(s) => (s.refs[path]?.value as PagesValue | undefined) ?? null,
	);
	const mode = useStore(
		(s) => (s.refs[path]?.mode as Mode | undefined) ?? "display",
	);
	const expandedList = useStore(
		(s) => (s.refs[path]?.expanded as string[] | undefined) ?? [],
	);
	const drafts = useStore(
		(s) =>
			(s.refs[path]?.drafts as
				| Record<string, { name: string; snippet: string }>
				| undefined) ?? {},
	);
	const send = useStore((s) => s.send);
	const patch = useSliceSetter(path);
	const route = useRoute();

	const tree = value?.tree ?? EMPTY_TREE;
	const page = value?.page ?? null;
	const expanded = useMemo(() => new Set(expandedList), [expandedList]);

	const notify = useCallback(
		(payload: Record<string, unknown>) => {
			send({ op: OP_NOTIFY, ref: path, payload });
		},
		[path, send],
	);

	// The router path under /pages is [pid...]; empty = the root page.
	// Mode is browser-owned but the server must know it, because display
	// mode is what makes the server run the sections.
	const selectionKey = route.path.join("/");
	// biome-ignore lint/correctness/useExhaustiveDependencies: selectionKey captures route.path content; listing route.path itself refires every render.
	useEffect(() => {
		if (route.top !== "pages") return;
		send({
			op: OP_NOTIFY,
			ref: path,
			payload: { op: "on_page_select", path: route.path, mode },
		});
	}, [selectionKey, route.top, mode, path, send]);

	const toggleExpanded = useCallback(
		(key: string) => {
			const next = new Set(expandedList);
			if (next.has(key)) next.delete(key);
			else next.add(key);
			patch({ expanded: Array.from(next) });
		},
		[expandedList, patch],
	);

	const selectPage = useCallback((nodePath: string[]) => {
		navigate({ top: "pages", path: nodePath });
	}, []);

	const setDraft = useCallback(
		(sid: string, next: { name: string; snippet: string }) => {
			patch({ drafts: { ...drafts, [sid]: next } });
		},
		[drafts, patch],
	);

	const clearDraft = useCallback(
		(sid: string) => {
			const next = { ...drafts };
			delete next[sid];
			patch({ drafts: next });
		},
		[drafts, patch],
	);

	const pagePath = page?.path ?? route.path;
	// A set_page whose mode disagrees with ours is in flight; the fields it
	// carries are not the ones this mode wants.
	const live = page != null && page.mode === "display" && mode === "display";

	return (
		<div className="flex-1 min-h-0 min-w-0 flex">
			<TreeRail
				tree={tree}
				expanded={expanded}
				toggleExpanded={toggleExpanded}
				selectPage={selectPage}
				selectedPath={route.path}
				notify={notify}
			/>
			<div className="flex-1 min-w-0 flex flex-col bg-background overflow-y-auto">
				<div className="px-6 py-3 border-b border-border/60 flex items-center gap-3 sticky top-0 bg-background z-10">
					<h1 className="flex-1 min-w-0 truncate text-lg font-medium">
						{page ? page.title || "untitled" : "loading..."}
					</h1>
					<ModeToggle mode={mode} onMode={(m) => patch({ mode: m })} />
				</div>
				<div className="mx-auto w-full max-w-3xl px-6 py-6 flex flex-col gap-4">
					{page == null ? (
						<div className="text-sm text-muted-foreground font-mono">
							waiting for page...
						</div>
					) : (
						<>
							{page.sections.map((section) => (
								<SectionCard
									key={section.id}
									section={section}
									mode={mode}
									live={live}
									draft={drafts[section.id]}
									onDraft={(d) => setDraft(section.id, d)}
									onSave={(d) => {
										notify({
											op: "on_section_update",
											page_path: pagePath,
											section_id: section.id,
											name: d.name,
											snippet: d.snippet,
										});
										clearDraft(section.id);
									}}
									onDelete={() => {
										if (!window.confirm(`delete section "${section.name}"?`))
											return;
										notify({
											op: "on_section_delete",
											page_path: pagePath,
											section_id: section.id,
										});
										clearDraft(section.id);
									}}
								/>
							))}
							{mode === "code" ? (
								<button
									type="button"
									onClick={() => {
										const name = window.prompt("new section name", "section");
										if (!name) return;
										notify({
											op: "on_section_create",
											page_path: pagePath,
											name,
										});
									}}
									className="text-sm text-muted-foreground hover:text-text-primary border border-dashed border-border/60 rounded-md py-2 hover:bg-muted/40"
								>
									+ new section
								</button>
							) : page.sections.length === 0 ? (
								<div className="text-sm text-muted-foreground font-mono">
									no sections yet -- switch to code to add one
								</div>
							) : null}
						</>
					)}
				</div>
			</div>
		</div>
	);
}

function ModeToggle({
	mode,
	onMode,
}: {
	mode: Mode;
	onMode: (m: Mode) => void;
}) {
	return (
		<div className="flex items-center gap-1 text-xs font-mono rounded-md border border-border/60 p-0.5">
			{(["display", "code"] as Mode[]).map((m) => (
				<button
					key={m}
					type="button"
					onClick={() => onMode(m)}
					className={`px-2 py-0.5 rounded ${
						mode === m
							? "bg-primary text-primary-foreground"
							: "text-muted-foreground hover:text-text-primary"
					}`}
				>
					{m}
				</button>
			))}
		</div>
	);
}

// -- Section card ------------------------------------------------------------

function SectionCard({
	section,
	mode,
	live,
	draft,
	onDraft,
	onSave,
	onDelete,
}: {
	section: SectionEntry;
	mode: Mode;
	live: boolean;
	draft: { name: string; snippet: string } | undefined;
	onDraft: (d: { name: string; snippet: string }) => void;
	onSave: (d: { name: string; snippet: string }) => void;
	onDelete: () => void;
}) {
	const current = draft ?? { name: section.name, snippet: section.snippet };
	const dirty =
		current.name !== section.name || current.snippet !== section.snippet;

	if (mode === "display") {
		return (
			<section className="rounded-md border border-border/60 bg-card p-4">
				{section.error ? (
					<div className="text-xs font-mono text-destructive whitespace-pre-wrap">
						{section.name}: {section.error}
					</div>
				) : section.fields.length === 0 ? (
					<div className="text-xs text-muted-foreground font-mono">
						{section.name}
						{section.snippet.trim()
							? " -- renders nothing"
							: " -- empty, switch to code"}
					</div>
				) : (
					<div className="flex flex-col gap-3">
						{live
							? section.fields.map((f) => <FieldView key={f.path} field={f} />)
							: null}
					</div>
				)}
			</section>
		);
	}

	return (
		<section className="rounded-md border border-border/60 bg-card p-4 flex flex-col gap-2">
			<div className="flex items-center gap-2">
				<input
					type="text"
					value={current.name}
					onChange={(e) => onDraft({ ...current, name: e.target.value })}
					className="flex-1 min-w-0 bg-transparent border border-border/60 rounded-md px-2 py-1 text-sm font-mono focus:outline-none focus:border-primary"
				/>
				<span className="text-[10px] text-muted-foreground font-mono">
					{section.id}
				</span>
				<button
					type="button"
					onClick={onDelete}
					className="text-[10px] uppercase tracking-wide font-mono px-1.5 py-0.5 rounded text-destructive hover:bg-destructive/10"
				>
					del
				</button>
			</div>
			<textarea
				value={current.snippet}
				onChange={(e) => onDraft({ ...current, snippet: e.target.value })}
				onKeyDown={(e) => {
					if ((e.metaKey || e.ctrlKey) && (e.key === "Enter" || e.key === "s")) {
						e.preventDefault();
						if (dirty) onSave(current);
					}
				}}
				spellCheck={false}
				rows={Math.max(4, current.snippet.split("\n").length + 1)}
				placeholder={SNIPPET_PLACEHOLDER}
				className="w-full resize-y bg-background border border-border/60 rounded-md p-2 font-mono text-xs leading-5 focus:outline-none focus:border-primary"
			/>
			<div className="flex items-center justify-end gap-2 text-xs font-mono">
				{section.error ? (
					<span className="flex-1 min-w-0 truncate text-destructive">
						{section.error}
					</span>
				) : null}
				{dirty ? <span className="text-muted-foreground">unsaved</span> : null}
				<button
					type="button"
					onClick={() => onSave(current)}
					disabled={!dirty}
					className={`px-3 py-1 rounded-md uppercase tracking-wider ${
						dirty
							? "bg-primary text-primary-foreground hover:opacity-90"
							: "bg-muted/40 text-muted-foreground cursor-not-allowed"
					}`}
				>
					save
				</button>
			</div>
		</section>
	);
}

// -- Tree rail ---------------------------------------------------------------

function TreeRail({
	tree,
	expanded,
	toggleExpanded,
	selectPage,
	selectedPath,
	notify,
}: {
	tree: PageNode;
	expanded: Set<string>;
	toggleExpanded: (key: string) => void;
	selectPage: (path: string[]) => void;
	selectedPath: string[];
	notify: (payload: Record<string, unknown>) => void;
}) {
	const rootActive = selectedPath.length === 0;
	return (
		<aside className="w-64 shrink-0 border-r border-border/60 h-full flex flex-col bg-card">
			<div className="px-3 py-2 flex items-center justify-between border-b border-border/60">
				<span className="text-xs uppercase tracking-wider text-muted-foreground font-mono">
					pages
				</span>
				<button
					type="button"
					className="text-xs text-muted-foreground hover:text-text-primary font-mono px-2 py-0.5 rounded-md hover:bg-muted/40"
					onClick={() => {
						const title = window.prompt("new page title", "page");
						if (!title) return;
						notify({ op: "on_page_create", parent_path: [], title });
					}}
					title="add page at root"
				>
					+p
				</button>
			</div>
			<div className="flex-1 min-h-0 overflow-y-auto py-1">
				{/* The root page is a real page: it can hold sections too. */}
				<button
					type="button"
					onClick={() => selectPage([])}
					className={`w-full text-left px-2 py-1 text-sm font-mono ${
						rootActive
							? "bg-primary/10 text-text-primary"
							: "text-muted-foreground hover:bg-muted/40"
					}`}
				>
					{tree.title || "/"}
				</button>
				{tree.pages.map((node) => (
					<PageNodeRow
						key={node.id ?? ""}
						node={node}
						parentPath={[]}
						depth={0}
						expanded={expanded}
						toggleExpanded={toggleExpanded}
						selectPage={selectPage}
						selectedPath={selectedPath}
						notify={notify}
					/>
				))}
				{tree.pages.length === 0 ? (
					<div className="px-3 py-2 text-xs text-muted-foreground font-mono">
						empty. use +p to add.
					</div>
				) : null}
			</div>
		</aside>
	);
}

function PageNodeRow({
	node,
	parentPath,
	depth,
	expanded,
	toggleExpanded,
	selectPage,
	selectedPath,
	notify,
}: {
	node: PageNode;
	parentPath: string[];
	depth: number;
	expanded: Set<string>;
	toggleExpanded: (key: string) => void;
	selectPage: (path: string[]) => void;
	selectedPath: string[];
	notify: (payload: Record<string, unknown>) => void;
}) {
	const nodePath = [...parentPath, node.id ?? ""];
	const key = nodePath.join("/");
	const active = selectedPath.join("/") === key;
	// Notion-style: clicking a page navigates AND reveals its children.
	const isOpen =
		expanded.has(key) || selectedPath.slice(0, nodePath.length).join("/") === key;
	const hasKids = node.pages.length > 0;
	const indentStyle = { paddingLeft: `${8 + depth * 12}px` };

	return (
		<div>
			{/* biome-ignore lint/a11y/useSemanticElements: RowActions renders <button>s inside, so this row cannot itself be a <button>. */}
			<div
				className={`group/row flex items-center gap-1 text-sm font-mono py-1 pr-2 cursor-pointer ${
					active
						? "bg-primary/10 text-text-primary"
						: "text-text-primary hover:bg-muted/40"
				}`}
				style={indentStyle}
				onClick={() => selectPage(nodePath)}
				onKeyDown={(e) => {
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault();
						selectPage(nodePath);
					}
				}}
				role="button"
				tabIndex={0}
			>
				<button
					type="button"
					onClick={(e) => {
						e.stopPropagation();
						toggleExpanded(key);
					}}
					className="w-4 text-xs text-muted-foreground"
					aria-label={isOpen ? "collapse page" : "expand page"}
				>
					{hasKids ? (isOpen ? "v" : ">") : "·"}
				</button>
				<span className="flex-1 truncate">{node.title || node.id}</span>
				<RowActions
					items={[
						{
							label: "+p",
							onClick: () => {
								const title = window.prompt("new child page title", "page");
								if (!title) return;
								notify({
									op: "on_page_create",
									parent_path: nodePath,
									title,
								});
							},
						},
						{
							label: "ren",
							onClick: () => {
								const title = window.prompt("rename page", node.title);
								if (!title || title === node.title) return;
								notify({ op: "on_page_rename", path: nodePath, title });
							},
						},
						{
							label: "del",
							danger: true,
							onClick: () => {
								if (
									!window.confirm(
										`delete page "${node.title}" and everything under it?`,
									)
								)
									return;
								notify({ op: "on_page_delete", path: nodePath });
							},
						},
					]}
				/>
			</div>
			{isOpen && hasKids ? (
				<div>
					{node.pages.map((kid) => (
						<PageNodeRow
							key={kid.id ?? ""}
							node={kid}
							parentPath={nodePath}
							depth={depth + 1}
							expanded={expanded}
							toggleExpanded={toggleExpanded}
							selectPage={selectPage}
							selectedPath={selectedPath}
							notify={notify}
						/>
					))}
				</div>
			) : null}
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

export const PagesRef: RefEntry = { factory, component: PagesView };
