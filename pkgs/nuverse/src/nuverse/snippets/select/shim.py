"""A select cell: the choice this cell keeps, edited in place."""

import nu
from nuverse.snippets.select import snippet


def out() -> nu.Nu:
    """The select snippet's input."""
    return snippet.out()
