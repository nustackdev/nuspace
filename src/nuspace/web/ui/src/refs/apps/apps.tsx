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
// drives navigate() and there is no on_app_select on the wire. /apps with no
// segment is "nothing open".
//
// We never remount the shell on navigation.

import { OP_NOTIFY } from "@nustackdev/ui-core";
import type { RefEntry } from "@nustackdev/ui-kit";
import {
	Alert,
	AlertDescription,
	AlertIcon,
	AlertTitle,
	IconButton,
	Spinner,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
	useStore,
} from "@nustackdev/ui-kit";
import { RotateCw } from "lucide-react";
import { useCallback, useMemo } from "react";
import {
	appsBar,
	appsBarTitle,
	appsBody,
	appsCanvas,
	appsDetached,
	appsDirtyDot,
	appsEditor,
	appsPayload,
	appsPlaceholder,
	appsPolicy,
} from "../../design/apps";
import { SECTION_STATUS } from "../../design/section-status";
import { SectionStatusPill } from "../../design/section-status-dot";
import { useRoute } from "../../router";
import { Rail } from "./Rail";
import { SourceBox } from "./Source";
import {
	appsSliceFactory,
	patchAppsEditor,
	setDirty,
	useAppsEditorSlot,
	useAppsValue,
} from "./slice";
import { type AppRow, appLabel, DETACHED_STATE } from "./types";

function AppsView({ path }: { path: string }) {
	const { apps, attached, loaded } = useAppsValue(path);
	const send = useStore((s) => s.send);
	const route = useRoute();

	const selectedId = route.path[0] ?? null;
	const app = useMemo(() => apps.find((a) => a.id === selectedId) ?? null, [apps, selectedId]);

	const renaming = useAppsEditorSlot(path, (e) => e.renaming);
	const dirty = useAppsEditorSlot(path, (e) => (selectedId ? e.dirty.includes(selectedId) : false));

	const notify = useCallback(
		(payload: Record<string, unknown>) => {
			send({ op: OP_NOTIFY, ref: path, payload });
		},
		[path, send],
	);

	const commit = useCallback(
		(source: string) => {
			if (!app) return;
			setDirty(path, app.id, false);
			if (source === app.source) return;
			notify({ op: "on_app_update", app_id: app.id, source });
		},
		[app, notify, path],
	);

	const restart = useCallback(() => {
		if (app) notify({ op: "on_app_restart", app_id: app.id });
	}, [app, notify]);

	return (
		<div className="flex min-h-0 min-w-0 flex-1">
			<Rail
				apps={apps}
				loaded={loaded}
				attached={attached}
				selectedId={selectedId}
				renaming={renaming}
				onRenameStart={(id) => patchAppsEditor(path, { renaming: id })}
				onRenameEnd={() => patchAppsEditor(path, { renaming: null })}
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
						{attached ? null : <DetachedNotice />}
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

/**
 * No `AppsRunner` in the space tree.
 *
 * This is not an error and not a connection problem, so it is not danger and
 * not a spinner. The apps exist and are editable; nothing is running them.
 * Saying that plainly beats painting six idle dots that look like a system
 * at rest.
 */
function DetachedNotice() {
	return (
		<div className={appsDetached}>
			<Alert tone="warn">
				<AlertIcon />
				<div>
					<AlertTitle>no apps runner mounted</AlertTitle>
					<AlertDescription>
						These apps are stored and editable, but nothing is supervising them. A space runs its
						apps by composing <code>AppsRunner(SpaceRoot)</code> into its own tree, not into the
						per-connection ui tree.
					</AlertDescription>
				</div>
			</Alert>
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

export const AppsRef: RefEntry = {
	factory: appsSliceFactory,
	component: AppsView,
};
