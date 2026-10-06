"""A date cell: the date this cell keeps, edited in place."""

import nu
from nuverse.snippets.date import snippet


def out() -> nu.Nu:
    """The date snippet's input."""
    return snippet.out()
