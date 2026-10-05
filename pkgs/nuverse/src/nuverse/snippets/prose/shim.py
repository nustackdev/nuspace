"""A text cell: the editor over the text this cell keeps."""

import nu
from nuverse.snippets.prose import snippet


def out() -> nu.Nu:
    """The text snippet's editor."""
    return snippet.out()
