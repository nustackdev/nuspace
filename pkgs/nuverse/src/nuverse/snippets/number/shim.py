"""A number cell: one number this cell keeps, edited in place."""

import nu
from nuverse.snippets.number import snippet


def out() -> nu.Nu:
    """The number snippet's input."""
    return snippet.out()
