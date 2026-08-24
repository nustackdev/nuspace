// nuspace-specific narrowing over the wire MOUNT payload.

import type { MountField } from "@nustackdev/ui-core";

export type NuspacePage = {
	slug: string;
	title: string;
};

export type NuspaceBlock = {
	id: string;
	kind: string;
	fields: MountField[];
};

export type NuspaceActivePage = NuspacePage & {
	blocks: NuspaceBlock[];
};

export type NuspaceMount = {
	pages: NuspacePage[];
	active_page: NuspaceActivePage | null;
};
