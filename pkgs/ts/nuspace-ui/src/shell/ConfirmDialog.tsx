// The one confirm dialog: whatever ./confirm.ts was last asked, as a kit
// `Dialog` with the destructive action and a way back. Cancel has the focus
// when it opens, so a stray Enter keeps things as they were.

import {
	Button,
	Dialog,
	DialogClose,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@nustackdev/ui-kit";
import { useRef } from "react";
import { answer, type Question, useQuestion } from "./confirm";

export function ConfirmDialog() {
	const open = useQuestion();
	// The last question, so the words stay put while the dialog fades out.
	const last = useRef<Question | null>(null);
	if (open) last.current = open;
	const q = last.current;
	return (
		<Dialog open={open !== null} onOpenChange={(next) => next || answer(false)}>
			{q ? (
				<DialogContent size="sm" showClose={false}>
					<DialogHeader>
						<DialogTitle>{q.title}</DialogTitle>
						<DialogDescription>{q.description}</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<DialogClose asChild>
							<Button variant="ghost">Cancel</Button>
						</DialogClose>
						<Button variant="destructive" onClick={() => answer(true)}>
							{q.action}
						</Button>
					</DialogFooter>
				</DialogContent>
			) : null}
		</Dialog>
	);
}
