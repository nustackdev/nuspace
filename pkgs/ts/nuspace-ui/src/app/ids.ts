// Id minting, browser side.
//
// The browser mints plane and section ids, which is what makes a create a pure
// function of its event on the server -- re-running the arm rewrites one row
// instead of adding another -- and what lets a click route to what it just made
// without a round trip to learn its name.
//
// Here rather than with either ref because both mint, and two copies of a
// scheme the server also implements is one copy too many.

let _seq = 0;

/**
 * A time-ordered id, the same shape `nuspace.ops.mint_ordered_id` makes.
 *
 * Ids sort by the moment they were minted, so a container listed by key comes
 * out in creation order with nothing storing it.
 */
export function mintId(prefix: "p" | "s"): string {
	const stamp = Date.now().toString(16).padStart(12, "0");
	const seq = (_seq++ % 0x10000).toString(16).padStart(4, "0");
	const tail = Math.floor(Math.random() * 0x10000)
		.toString(16)
		.padStart(4, "0");
	return `${prefix}_${stamp}_${seq}_${tail}`;
}
