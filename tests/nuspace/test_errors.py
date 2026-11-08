"""nuspace.errors: five reasons an op refuses, one LookupError base to catch them all."""

from __future__ import annotations

import pytest

import nu
import nuspace
from nuspace.errors import Ended, Exists, Missing, NuspaceError, Refused, Removed


ERRORS = (Missing, Removed, Exists, Refused, Ended)


def test_every_error_is_a_nuspace_error_and_a_lookup_error():
    assert nuspace.errors.Missing is Missing
    for error in ERRORS:
        assert issubclass(error, NuspaceError)
        assert issubclass(error, LookupError)
    assert len(set(ERRORS)) == len(ERRORS)


@pytest.mark.parametrize("error", ERRORS)
def test_a_term_raises_it_at_run_time_and_one_except_catches_it(error):
    term = nu.IfDo(nu.Bool(True), nu.Raise("no such plane", exc_cls=error))
    with pytest.raises(error, match="no such plane"):
        nu.run(term)
    with pytest.raises(NuspaceError):
        nu.run(term)
