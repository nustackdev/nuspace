"""A text input cell: the text this cell keeps, edited in place."""

import nu
from nuverse.snippets.text_input import snippet


def out() -> nu.Nu:
    """The text input snippet's input."""
    return snippet.out()
