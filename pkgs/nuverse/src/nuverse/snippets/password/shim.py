"""A password generator: a fresh password whenever its options change."""

import nu
from nuverse.snippets.password import snippet


def out() -> nu.Nu:
    """The password snippet's generator."""
    return snippet.out()
