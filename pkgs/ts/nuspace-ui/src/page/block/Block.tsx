// One block on a page: its row, its gutter, and the program inside.
//
// There is no block kind to branch on. Each block renders the subtree at its
// own address -- the ui refs its program mounted, which arrive as ordinary
// nodes -- through `NodeView`, inside the same `docBlock`, with the same
// gutter: add and drag, copy the section id, open the source. Every block
// compiles, runs, is supervised and reports status identically. See
// ./address.ts for where that address is.
//
// `editable` is the page's setting. Off, the block draws its output and
// nothing else: no gutter, and its source never opens.

import type { Path } from "@nustackdev/ui-core";
import type * as React from "react";
import { docBlock, docDropIndicator } from "../../design";
import type { FocusReq } from "../state";
import type { Block as BlockValue, ExitDir } from "../types";
import { Gutter } from "./Gutter";
import { ProgramBlock } from "./Program";

export function Block({
	block,
	uiPath,
	editable,
	selected,
	selectedStrong,
	focused,
	editing,
	focusReq,
	dragging,
	dropAbove,
	setEl,
	onPointerIn,
	onSetEditing,
	onDrag,
	onPlus,
	onSelect,
	onFocusConsumed,
	onCommit,
	onExit,
}: {
	block: BlockValue;
	/** Where this block's own refs live in the tree. */
	uiPath: Path;
	editable: boolean;
	selected: boolean;
	/** Part of a multi-block selection. */
	selectedStrong: boolean;
	/** The caret lives in here. */
	focused: boolean;
	/** Source open. */
	editing: boolean;
	focusReq: FocusReq | null;
	dragging: boolean;
	/** A drag would drop right above this block. */
	dropAbove: boolean;
	setEl: (el: HTMLElement | null) => void;
	/** A plain primary-button press landed inside the block. */
	onPointerIn: () => void;
	onSetEditing: (on: boolean) => void;
	onDrag: (e: React.PointerEvent) => void;
	/** Open a line below this block. Not a block: see ../Ghost.tsx. */
	onPlus: () => void;
	onSelect: () => void;
	onFocusConsumed: () => void;
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
}) {
	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: a mousedown anywhere in a block hands control to that block's own editor
		<div
			ref={setEl}
			data-block={block.id}
			className={docBlock({ selected, selectedStrong, focused, dragging })}
			onMouseDown={(e) => {
				// A plain click inside a block leaves block-selection mode;
				// the block's own editor takes over from here.
				if (e.button === 0) onPointerIn();
			}}
		>
			{dropAbove ? <span className={`${docDropIndicator} top-0`} /> : null}
			{editable ? (
				<Gutter
					blockId={block.id}
					state={block.status.state}
					pinned={editing || selected}
					editing={editing}
					onSetEditing={onSetEditing}
					onDrag={onDrag}
					onPlus={onPlus}
					onSelect={onSelect}
				/>
			) : null}
			<ProgramBlock
				source={block.source}
				uiPath={uiPath}
				status={block.status}
				editable={editable}
				editing={editing}
				focusReq={focusReq}
				onFocusConsumed={onFocusConsumed}
				onCommit={onCommit}
				onExit={onExit}
				onSelectSelf={onSelect}
				onSetEditing={onSetEditing}
			/>
		</div>
	);
}
