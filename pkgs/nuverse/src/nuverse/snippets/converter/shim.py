"""A unit converter: type on either side, the other follows."""

import nu
from nuverse.snippets.converter import snippet


def out() -> nu.Nu:
    """The converter snippet's two sides."""
    return snippet.out()
