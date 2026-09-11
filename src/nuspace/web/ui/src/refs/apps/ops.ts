// The Apps op table, browser side. Mirrors `refs/apps/ops.py`.
//
// One ref per op: a notify goes to `<apps ref>.ops.<name>` and the payload
// carries that op's arguments and nothing else. There is no `op` key, because
// the path already answered that question, and the server subscribes one
// handler per path rather than branching on a string.
//
// Server bodies take named arguments, so a typo here is a TypeError over
// there rather than a silently empty string. `Ops` is what keeps the two
// sides in step: add an op on one side and this file is where the other side
// fails to compile.
//
// There is no `app.select`. Selection is the URL (/apps/<id>), so the server
// stays stateless between notifies.

/** Every op the Apps surface accepts, with its argument shape. */
export type Ops = {
	/** `source` omitted means "template a starter program at this space's root". */
	"app.create": { name: string; source?: string };
	"app.rename": { app_id: string; name: string };
	"app.delete": { app_id: string };
	"app.update": { app_id: string; source: string };
	"app.restart": { app_id: string };
};

/** Send one op. Threaded down from `apps.tsx` into the rail and the canvas. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
