"""This demo space's own shape.

A space that needs storage nuspace core does not ship subclasses ``Space``
rather than growing core. ``ShapeMeta`` rebinds ``_root_shape`` on every
slot including the inherited ones, so ``DemoSpace`` is the root for all of
them and the whole shape resolves against one navigator.

Its own module, not ``demo.py``, on purpose. ``demo.py`` runs as a script,
so it is ``__main__``; a block doing ``from demo import DemoSpace`` would
re-import it under a second module name and get a *different* class object
than the one the navigator is tagged with. Blocks and the host have to name
the same class, so it lives somewhere both import the same way.
"""

from __future__ import annotations

import nu
from nuspace.core.shapes import Space


__all__ = ["DemoSpace", "Movie", "Series", "Taste", "TasteRun"]


class Series(nu.Shape):
    """One named, append-only numeric series.

    ``Space.state`` is the scratch namespace for a value; this is the
    scratch namespace for a *sequence* of them. ``Kh57Ref`` is what makes
    it worth having: the map can hold billions of entries and a chart
    still asks for a bounded reservoir sample over a key range instead of
    reading it all back.

    ``cursor`` is the next key to write. A slot rather than a computed
    length, because the producer appends without reading the map back and
    the sampler needs the range's upper bound anyway.
    """

    points = nu.kv.Kh57Ref.slot(int)
    cursor = nu.kv.IntRef.slot()


class Movie(nu.Shape):
    """One logged movie.

    Keyed in a *dict*, not a list, because a movie owns a page and that
    page's block names the movie by id in its own source. A list index
    would be reassigned the moment anything ahead of it is deleted and
    every page after the hole would render the wrong film.
    """

    title = nu.kv.StrRef.slot()
    year = nu.kv.IntRef.slot()
    genre = nu.kv.StrRef.slot()
    rating = nu.kv.FloatRef.slot()
    watched = nu.kv.BoolRef.slot()
    notes = nu.kv.StrRef.slot()


class Taste(nu.Shape):
    """What the shelf says about the person who filled it.

    This is the agent's answer and nothing else -- no scheduling, no error
    channel, no cursor. Those live on ``TasteRun``, so the model can be
    handed *this* Shape as its whole write surface and cannot reach the
    machinery that runs it.

    Notes:
        - `genres` is the favoured genres, strongest first, comma
          separated. A string rather than a list because it is a reading,
          not an index: nothing joins on it.
        - `tendency` is one short phrase on how this person rates -- are
          they generous, are they harsh, do they only log what they
          already like.
        - `prose` is one markdown paragraph. The part a person actually
          reads.
        - `sample` and `computed_at` are stamped by the app when a run
          lands, not written by the model. They say what the reading was
          made from -- how many films were on the shelf, and when -- which
          is the difference between a stale profile and a current one.
    """

    genres = nu.kv.StrRef.slot()
    tendency = nu.kv.StrRef.slot()
    prose = nu.kv.StrRef.slot()
    sample = nu.kv.IntRef.slot()
    computed_at = nu.kv.FloatRef.slot()


class TasteRun(nu.Shape):
    """Bookkeeping for the app that fills ``Taste``. The app writes it, never the model.

    Notes:
        - `state` is one of `idle`, `working`, `ok`, `failed`. A run that
          cannot reach the model, or that burns its whole turn budget
          without finishing, lands on `failed` with a sentence in `note`.
          The block failing is not an acceptable way to say that.
        - `shelf` is a fingerprint of the shelf the last run was started
          for. It is written *before* the run, which is what stops the
          agent's own writes -- or a duplicate change event -- from
          starting a second run over the same films.
        - `turns` and `runs` are the meter: how many turns the last run
          took, and how many runs have landed since the store was made.
    """

    state = nu.kv.StrRef.slot()
    note = nu.kv.StrRef.slot()
    shelf = nu.kv.StrRef.slot()
    turns = nu.kv.IntRef.slot()
    runs = nu.kv.IntRef.slot()


class DemoSpace(Space):
    """Space plus this demo's own series, movie and taste storage."""

    series = nu.kv.ShapesDictRef.slot(Series)
    movies = nu.kv.ShapesDictRef.slot(Movie)

    # The agent's output, and the app's own record of producing it. Two
    # slots rather than one shape with nine, because the model is handed
    # `Taste` as its surface and `TasteRun` is deliberately not on it.
    taste = nu.kv.ShapeRef.slot(Taste)
    taste_run = nu.kv.ShapeRef.slot(TasteRun)

    # The id minter for `movies`. `nuspace.core.refs.mint_ordered_id` is
    # python and a block is source that constructs *once*, so calling it
    # in a block would freeze one id into the tree and every submit would
    # overwrite the same movie. An id has to be minted by the term, at
    # click time, which means a kv counter.
    movie_seq = nu.kv.IntRef.slot()


# Where the worker resolves its scope from. The worker takes this as
# config precisely so a subclassed root works out of process too: a worker
# that assumed ``Space`` would address the parent's slots and silently
# read an empty store.
SCOPE_SPEC = "demo_space:DemoSpace"
