// The keyboard shortcuts sheet: ./keys.ts's list as a kit `Dialog`, one
// group per place the focus can be, each line its action and its keys. Read
// only; Esc or a click outside puts it away.

import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	Shortcut,
} from "@nustackdev/ui-kit";
import { Fragment } from "react";
import {
	keysBody,
	keysDialog,
	keysDoes,
	keysGroup,
	keysGroupTitle,
	keysKeys,
	keysOr,
	keysRow,
} from "../design";
import { BINDINGS, setKeysOpen, useKeysOpen, useKeysShortcut } from "./keys";

export function KeysDialog() {
	const open = useKeysOpen();
	useKeysShortcut();
	return (
		<Dialog open={open} onOpenChange={setKeysOpen}>
			<DialogContent size="lg" className={keysDialog}>
				<DialogHeader>
					<DialogTitle>Keyboard shortcuts</DialogTitle>
					<DialogDescription>Grouped by where the focus is.</DialogDescription>
				</DialogHeader>
				<div className={keysBody}>
					{BINDINGS.map((group) => (
						<section key={group.title} className={keysGroup}>
							<h3 className={keysGroupTitle}>{group.title}</h3>
							{group.bindings.map((b) => (
								<div key={b.does} className={keysRow}>
									<span className={keysDoes}>{b.does}</span>
									<span className={keysKeys}>
										{b.keys.map((keys, i) => (
											<Fragment key={keys.join("+")}>
												{i > 0 ? <span className={keysOr}>or</span> : null}
												<Shortcut keys={keys} size="sm" />
											</Fragment>
										))}
									</span>
								</div>
							))}
						</section>
					))}
				</div>
			</DialogContent>
		</Dialog>
	);
}
