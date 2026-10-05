"""A ticker: the seconds this plane was open, counted in its own state."""

import nu
from nuverse.snippets.ticker import snippet


def out() -> nu.Nu:
    """The ticker snippet's run."""
    return snippet.out()
