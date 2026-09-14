// AppsRef -- the nuspace ops surface.
//
// Two columns: the flat app rail on the left, one app's source on the right.
//
// The canvas is Monaco and nothing else, and that is a consequence of apps
// being headless rather than a scope cut. An app produces; a page displays.
// An app runs whether or not a browser is looking, so it has nowhere to
// mount a ui ref and must not try -- which means there is no output to show
// and therefore no display mode to toggle into. What an app surface can
// honestly show is its source and its state, so that is what it shows.
//
// Selection is router-owned: the URL /apps/<id> is the cursor, so a click
// drives navigate() rather than moving a server-side cursor. /apps with no
// segment is "nothing open". Opening one does send `app.select`, but that is
// a pull -- "re-ship this batch, I am looking at it now" -- and the server
// keeps nothing after the arm finishes.
//
// We never remount the shell on navigation.

import {
	IconButton,
	type NodeEntry,
	type NodeProps,
	pathKey,
	Spinner,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { RotateCw } from "lucide-react";
import { useCallback, useEffect, useMemo } from "react";
import { useRoute } from "../../app/router";
import { notifyOp } from "../../app/wire";
import { SectionStatusPill } from "../../components";
import {
	appsBar,
	appsBarTitle,
	appsBody,
	appsCanvas,
	appsDirtyDot,
	appsEditor,
	appsPayload,
	appsPlaceholder,
	appsPolicy,
	SECTION_STATUS,
	shellSurface,
} from "../../design";
import type { Ops } from "./ops";
import { Rail } from "./Rail";
import { SourceBox } from "./Source";
import {
	applyAppsWrite,
	setDirty,
	setRenaming,
	useAppStarter,
	useAppsLocal,
	useAppsValue,
} from "./state";
import { type AppRow, appLabel, DETACHED_STATE } from "./types";

function AppsView({ path }: NodeProps) {
	const { apps, attached, loaded } = useAppsValue(path);
	const route = useRoute();
	const key = pathKey(path);

	const selectedId = route.path[0] ?? null;
	const app = useMemo(() => apps.find((a) => a.id === selectedId) ?? null, [apps, selectedId]);

	const starter = useAppStarter(path);
	const renaming = useAppsLocal(path, (l) => l.renaming);
	const dirty = useAppsLocal(path, (l) => (selectedId ? l.dirty.includes(selectedId) : false));

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[key],
	);

	// A pull, once per app opened. The status batch answers for every app, so
	// this is only ever "I am looking now, tell me again".
	useEffect(() => {
		if (selectedId) notify("app.select", { app_id: selectedId });
	}, [notify, selectedId]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const commit = useCallback(
		(source: string) => {
			if (!app) return;
			setDirty(path, app.id, false);
			if (source === app.source) return;
			notify("app.update", { app_id: app.id, source });
		},
		[app, notify, key],
	);

	const restart = useCallback(() => {
		if (app) notify("app.restart", { app_id: app.id });
	}, [app, notify]);

	return (
		<div className={shellSurface}>
			<Rail
				apps={apps}
				starter={starter}
				loaded={loaded}
				attached={attached}
				selectedId={selectedId}
				renaming={renaming}
				onRenameStart={(id: string) => setRenaming(path, id)}
				onRenameEnd={() => setRenaming(path, null)}
				notify={notify}
			/>
			<div className={appsCanvas}>
				{!loaded ? (
					<div className={appsPlaceholder}>
						<Spinner size="sm" tone="neutral" label="Loading apps" />
						loading apps...
					</div>
				) : (
					<>
						{app == null ? (
							<Empty hasApps={apps.length > 0} />
						) : (
							<Canvas
								app={app}
								attached={attached}
								dirty={dirty}
								onCommit={commit}
								onDirty={(d) => setDirty(path, app.id, d)}
								onRestart={restart}
							/>
						)}
					</>
				)}
			</div>
		</div>
	);
}

function Empty({ hasApps }: { hasApps: boolean }) {
	return (
		<div className={appsPlaceholder}>
			{hasApps ? "select an app" : "no apps yet - use + in the rail"}
		</div>
	);
}

function Canvas({
	app,
	attached,
	dirty,
	onCommit,
	onDirty,
	onRestart,
}: {
	app: AppRow;
	attached: boolean;
	dirty: boolean;
	onCommit: (source: string) => void;
	onDirty: (dirty: boolean) => void;
	onRestart: () => void;
}) {
	const state = attached ? (app.status?.state ?? DETACHED_STATE) : DETACHED_STATE;
	const token = SECTION_STATUS[state];
	const error = app.status?.error ?? null;
	// `invalid` carries a nu.prog diagnostic, `failed` carries a traceback.
	// Both are the app's own source attributed, both render verbatim.
	const payload = token.carries && error ? error : null;

	return (
		<>
			<div className={appsBar}>
				<span className={appsBarTitle}>{appLabel(app)}</span>
				{dirty ? (
					<Tooltip>
						<TooltipTrigger asChild>
							<span className={appsDirtyDot} role="img" aria-label="unsaved changes" />
						</TooltipTrigger>
						<TooltipContent side="bottom">unsaved - cmd+enter to save</TooltipContent>
					</Tooltip>
				) : null}
				<span className="flex-1" />
				<span className={appsPolicy}>{app.policy}</span>
				<Tooltip>
					<TooltipTrigger asChild>
						<span>
							<SectionStatusPill status={state} />
						</span>
					</TooltipTrigger>
					<TooltipContent side="bottom">{token.hint}</TooltipContent>
				</Tooltip>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label={`Restart ${appLabel(app)}`}
							disabled={!attached}
							onClick={onRestart}
						>
							<RotateCw />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="bottom">restart</TooltipContent>
				</Tooltip>
			</div>
			<div className={appsBody}>
				{payload ? (
					<pre className={`${appsPayload} ${token.wash} ${token.line} ${token.fg}`}>{payload}</pre>
				) : null}
				{/* Monaco is behind a dynamic import, so the rail and the bar
				    paint before ~4MB of editor does. */}
				<div className={appsEditor}>
					<SourceBox appId={app.id} source={app.source} onCommit={onCommit} onDirty={onDirty} />
				</div>
			</div>
		</>
	);
}

export const AppsRef: NodeEntry = {
	component: AppsView,
	handlers: { write: (ctx, payload) => ctx.update((props) => applyAppsWrite(props, payload)) },
};
