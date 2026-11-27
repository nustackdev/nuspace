// The disconnect banner: a small pill over the top of the screen while the
// connection is down, nothing at all otherwise. The phone has no footer and
// no connection dot, so this is the only place the socket shows.
//
// Down is a socket that had a go and lost it, or never got one: reconnecting
// or disconnected. The first connect is not down, it is the boot.

import { StatusPill } from "@nustackdev/ui-kit";
import { type Status, useConnectionStatus } from "../core/connection";
import { mobileBanner } from "../design";

/** What the banner says, per status; null where it is not shown. */
export function bannerText(status: Status): string | null {
	if (status === "reconnecting") return "Reconnecting";
	if (status === "disconnected") return "Disconnected";
	return null;
}

export function DisconnectBanner() {
	const status = useConnectionStatus();
	const text = bannerText(status);
	if (text === null) return null;
	return (
		<div className={mobileBanner} role="status" aria-live="polite">
			<StatusPill tone={status === "disconnected" ? "danger" : "warn"}>{text}</StatusPill>
		</div>
	);
}
