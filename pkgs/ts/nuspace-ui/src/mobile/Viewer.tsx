// The mobile ViewerRef component: the one plane the route shows, full width.
//
// A solo plane shows as itself, flattened for the phone (./plane/MobilePlane.tsx).
// A desk item shows its panes as pages you swipe through (./desk/MobileDesk.tsx),
// and an empty desk says so.
//
// Like desktop's desk (../main/Desk.tsx) it ships `planes.open` with every
// plane the route shows and their params, whenever either changes and once
// on load, so the server ships exactly those panes.

import { EmptyState, type NodeProps, pathKey, Spinner } from "@nustackdev/ui-kit";
import { useCallback, useEffect } from "react";
import { currentRoutes, paramsOf, type Route, useRoute, useRoutes } from "../core/router";
import { notifyOp } from "../core/wire";
import { mobileMissing, mobileScreen } from "../design";
import type { PaneAt } from "../desk/drag";
import { settlePanes, useCellSpecs } from "../main/state";
import { NotFound } from "../pane/NotFound";
import type { ViewerOps } from "../plane/ops";
import { MobileDesk } from "./desk/MobileDesk";
import { MobilePlane } from "./plane/MobilePlane";

/** The plane the screen shows for a route, and where it sits; null for none. */
export function shownPlane(route: Route): { plane: string; at: PaneAt } | null {
	if (route.kind === "solo") return { plane: route.plane, at: { kind: "solo" } };
	if (route.kind === "item" && route.focus)
		return {
			plane: route.focus,
			at: { kind: route.item.kind, desk: route.desk, item: route.item.id },
		};
	return null;
}

export function MobileViewer({ path }: NodeProps) {
	const cellSpecs = useCellSpecs(path);
	const route = useRoute();
	const routes = useRoutes();
	const key = pathKey(path);
	const panesKey = JSON.stringify(routes.map((id) => [id, paramsOf(id)]));

	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const open = useCallback(
		(args: ViewerOps["planes.open"]) =>
			notifyOp<ViewerOps, "planes.open">(path, "planes.open", args),
		[key],
	);

	// biome-ignore lint/correctness/useExhaustiveDependencies: the panes are compared by their key; path by value.
	useEffect(() => {
		const shown = currentRoutes();
		settlePanes(path, shown);
		const params = Object.fromEntries(shown.map((id) => [id, paramsOf(id)]));
		open({ plane_ids: shown, params });
	}, [panesKey, open]);

	if (route.kind === "missing") {
		return (
			<div className={mobileScreen}>
				<NotFound what={route.what} />
			</div>
		);
	}
	if (route.kind === "desk") {
		return (
			<div className={mobileScreen}>
				<EmptyState className={mobileMissing} description="Add planes to it on desktop.">
					{route.name} is empty
				</EmptyState>
			</div>
		);
	}
	if (route.kind === "item") {
		return (
			<div className={mobileScreen}>
				<MobileDesk viewerPath={path} route={route} cellSpecs={cellSpecs} />
			</div>
		);
	}
	const shown = shownPlane(route);
	if (!shown) {
		return (
			<div className={mobileScreen}>
				<EmptyState className={mobileMissing} icon={<Spinner size="lg" tone="neutral" />} />
			</div>
		);
	}
	return (
		<div className={mobileScreen}>
			<MobilePlane
				key={shown.plane}
				viewerPath={path}
				planeId={shown.plane}
				cellSpecs={cellSpecs}
			/>
		</div>
	);
}
