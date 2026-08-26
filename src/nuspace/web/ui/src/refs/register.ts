// Register an out-of-tree Ref with the ui-kit runtime dispatch maps.
//
// Nuspace ships its own refs (LensRef) on top of the published
// @nustackdev/ui-kit. The kit's `factories` map feeds the store's inbound
// dispatch; the `renderers` map feeds FieldView. Both are module-level
// mutable objects, so injecting an entry at boot is enough -- no fork of
// the kit's registry needed. If a future kit release exposes a first-class
// `registerRefEntry`, swap this for that.

import type { RefEntry } from "@nustackdev/ui-kit";
import { factories, renderers } from "@nustackdev/ui-kit";

export function registerRefEntry(name: string, entry: RefEntry): void {
	(factories as Record<string, unknown>)[name] = entry.factory;
	(renderers as Record<string, unknown>)[name] = entry.component;
}
