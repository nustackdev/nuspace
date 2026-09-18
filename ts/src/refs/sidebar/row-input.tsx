// The in-row editor the rail renames and creates through.

import { Input } from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { railInput, railInputBox } from "../../design";

/**
 * Commits on Enter and on blur (you clicked away, you meant it), cancels on
 * Escape, and selects the initial text so the first keystroke replaces it.
 */
export function RailRowInput({
	initial,
	label,
	onCommit,
	onCancel,
}: {
	initial: string;
	label: string;
	onCommit: (value: string) => void;
	onCancel: () => void;
}) {
	const done = useRef(false);
	// `Input` is a plain function component and takes no ref, so the caret is
	// placed through the wrapper.
	const box = useRef<HTMLSpanElement | null>(null);
	useEffect(() => {
		const el = box.current?.querySelector("input");
		el?.focus();
		el?.select();
	}, []);
	return (
		<span ref={box} className={railInputBox}>
			<Input
				size="sm"
				aria-label={label}
				defaultValue={initial}
				className={railInput}
				onBlur={(e) => {
					if (done.current) return;
					done.current = true;
					onCommit(e.currentTarget.value);
				}}
				onKeyDown={(e) => {
					// The rail's arrow handling must not see these.
					e.stopPropagation();
					if (e.key === "Enter") {
						e.preventDefault();
						done.current = true;
						onCommit(e.currentTarget.value);
					} else if (e.key === "Escape") {
						e.preventDefault();
						done.current = true;
						onCancel();
					}
				}}
			/>
		</span>
	);
}
