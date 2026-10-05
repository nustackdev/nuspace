"""A program cell: one key in its own state, then done."""

import nu
from nuverse.snippets.program import snippet


def out() -> nu.Nu:
    """The program snippet's run."""
    return snippet.out()
