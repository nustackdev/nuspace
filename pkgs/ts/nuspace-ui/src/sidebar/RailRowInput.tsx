// The in-row editor the rail renames through.

import { Input } from "@nustackdev/ui-kit";
import { useEffect, useRef } from "react";
import { railInput, railInputBox } from "../design";

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
	const input = useRef<HTMLInputElement | null>(null);
	useEffect(() => {
		input.current?.focus();
		input.current?.select();
	}, []);
	return (
		<span className={railInputBox}>
			<Input
				ref={input}
				size="sm"
				ring="inset"
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
