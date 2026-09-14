// The Chat op table, browser side. Mirrors `nuspace/web/chat/ref.py`.
//
// One ref per op: a notify goes to `<chat ref>.ops.<name>` and the payload
// carries that op's arguments and nothing else. There is no `op` key, because
// the path already answered that question, and the server subscribes one arm
// per path rather than branching on a string.
//
// Two ops, and neither carries an id: there is one agent and one conversation,
// so there is nothing to address. That is also why there is no `chat.stop` --
// a nuagent run is a Nu term under a WhileDo and the host has no cancel to
// offer that would not leave the store describing a run that is not there.
// The turn budget is what ends a run nobody wants.
//
// Both are dropped server-side while a run is live. The browser disables the
// controls too, but that is an affordance and the guard is the store's.

/** Every op the Chat surface accepts, with its argument shape. */
export type Ops = {
	"chat.submit": { text: string };
	"chat.reset": Record<string, never>;
};

// There is no `Notify` alias here. The rail is one component and it calls
// `notifyOp` (app/wire.ts) directly; the pages and apps surfaces keep theirs
// because they thread the sender down into a rail and a canvas.
