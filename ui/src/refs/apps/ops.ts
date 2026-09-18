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
// Selection is still the URL (/apps/<id>) and the server still keeps no copy
// of it. `app.select` is a pull, not a cursor: it asks the server to re-ship
// the status batch for the app just opened, and the server forgets it again
// the moment the arm finishes.
//
// `app_id` is minted here, by `mintId("a")`. That makes a create a pure
// function of its event -- re-running the arm rewrites one row instead of
// adding another -- and lets a click navigate to the app it just made without
// waiting to be told its name. Same rule as pages and sections.

/** Every op the Apps surface accepts, with its argument shape. */
export type Ops = {
	"app.create": { app_id: string; name: string; source: string };
	"app.rename": { app_id: string; name: string };
	"app.delete": { app_id: string };
	"app.update": { app_id: string; source: string };
	"app.restart": { app_id: string };
	"app.select": { app_id: string };
};

/** Send one op. Threaded down from `apps.tsx` into the rail and the canvas. */
export type Notify = <K extends keyof Ops>(op: K, args: Ops[K]) => void;
