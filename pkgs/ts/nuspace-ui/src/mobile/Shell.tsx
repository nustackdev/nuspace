// The mobile shell's frame: one screen, the full visible height, and over it
// the sidebar screen (./sidebar/MobileSidebar.tsx), the dock at the bottom
// (./dock/Dock.tsx), the disconnect banner and the toaster. The screen is the
// plane the route shows (./Viewer.tsx).
//
// Like desktop, it draws before the tree lands: the viewer skeleton until the
// ViewerRef node arrives, a note once a boot runs long, a note for a real
// absence. Links go through the router's anchor rule, as on desktop, minus the
// desktop-only gestures (open to the side).

import { EmptyState, NodeView, Spinner, Toaster, useAnchorCatcher } from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { BOOTING_DELAY_MS, useAfter } from "../core/delay";
import { paneRule } from "../core/router";
import { useBooted, useTypePath } from "../core/surfaces";
import { mobileMain, mobileMissing, mobileRoot, mobileScreen, mobileToaster } from "../design";
import { ViewerSkeleton } from "../pane/ViewerSkeleton";
import { DisconnectBanner } from "./Banner";
import { Dock } from "./dock/Dock";
import { settleEditing } from "./plane/editing";
import { MobileSidebar } from "./sidebar/MobileSidebar";
import { settleSidebar } from "./sidebar/open";

export function MobileShell() {
	const viewer = useTypePath("ViewerRef");
	const rootRef = useRef<HTMLDivElement | null>(null);
	const booted = useBooted();
	const slow = useAfter(!booted, BOOTING_DELAY_MS);
	useAnchorCatcher(rootRef, paneRule);
	// A reload while the sidebar was open, or cells edited, lands on that
	// entry with nothing under it: the marks dropped in place.
	useEffect(() => {
		settleSidebar();
		settleEditing();
	}, []);

	return (
		<div ref={rootRef} className={mobileRoot} data-shell="mobile">
			<DisconnectBanner />
			<main className={mobileMain}>
				{viewer ? (
					<NodeView path={viewer} />
				) : booted ? (
					<EmptyState className={mobileMissing}>no Viewer on the tree</EmptyState>
				) : slow ? (
					<EmptyState
						className={mobileMissing}
						icon={<Spinner size="lg" tone="neutral" label="Booting" />}
						description="First boot takes a little longer while everything gets ready. Almost there!"
					>
						Booting your space
					</EmptyState>
				) : (
					<div className={mobileScreen}>
						<ViewerSkeleton />
					</div>
				)}
			</main>
			<MobileSidebar />
			<Dock />
			<Toaster className={mobileToaster} />
		</div>
	);
}
