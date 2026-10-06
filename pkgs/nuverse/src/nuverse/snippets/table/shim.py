"""A table cell: the data table over the rows this cell keeps."""

import nu
from nuverse.snippets.table import snippet


def out() -> nu.Nu:
    """The table snippet's grid."""
    return snippet.out()
