"""Block sources for the Movies page tree.

This is nu's ``examples/movies.py`` ported onto nuspace. The domain is the
same -- title, year, genre, rating, watched, notes, plus stats, a table
and filters -- but the structure is not. nu's version is one
``nu.ui.Page`` with declarative Shape slots and a `/detail` route driven
by a `selected` cursor. Here it is a *page tree*:

    Movies/            the form, and nothing else
    Movies/Control     stats, table, filters
    Movies/<title>     one page per movie, created when you log it

The interesting one is ``Movies/``. Logging a movie writes the movie to
kv *and writes a page into* ``DemoSpace.pages``. That is model.md's
closed algebra: the page tree is ordinary kv, so a Nu tree can add
another Nu tree the same way it would add any other record. The created
page's section is a plain ``Section`` record whose ``snippet`` is source
text, built at click time by concatenating a template around the movie's
id.

Kept as its own module rather than inline in ``demo.py`` for the same
reason ``demo_space.py`` is: ``demo.py`` runs as ``__main__``, so a block
importing from it would get a second copy of the module. Blocks import
``movies_blocks`` and so does the seed, and both get the same object.

## What a block can and cannot do here

- A block is a ``nu.prog`` program: a module with ``out(path)`` returning
  a Nu term. ``path`` is the only bound scope value.
- Every ui ref it names under ``path`` mounts in that block. Bare refs,
  by path -- ``nu.ui.Field`` / ``Fieldset`` / ``Form`` are declarative
  Shape slots for a ``nu.ui.Page`` and mean nothing here.
- Bare refs carry no mount props, and for most ref types a runtime
  ``write`` is the *value*, not a prop bag -- ``InputRef.set(x)`` sets the
  text, there is no label kwarg. ``labeled()`` below is the way out:
  ``enumerate_ui_refs`` reads props off ``type(node)._mount_props()``,
  which is a classmethod, so a one-off subclass declared inside the block
  gets real mount props. ``wire_type`` still resolves to the nearest
  ``nu.ui.refs`` ancestor, so the browser sees a plain ``InputRef``.
"""

from __future__ import annotations

import textwrap


__all__ = [
    "CONTROL_INTRO_PROSE",
    "CONTROL_PAGE_ID",
    "CONTROL_SHELF_SOURCE",
    "CONTROL_STATS_SOURCE",
    "GENRES",
    "GENRES_WITH_ANY",
    "ID_BASE",
    "MOVIES_FORM_SOURCE",
    "MOVIES_INTRO_PROSE",
    "MOVIES_OUTRO_PROSE",
    "MOVIES_PAGE_ID",
    "MOVIES_RAIL_PROSE",
    "MOVIE_ID_PREFIX",
    "MOVIE_PAGE_PREFIX",
    "SEED_MOVIES",
    "detail_parts",
]


# Fixed ids, because blocks name them in their own source. A minted id
# would be fine for the movie pages (they are created by a term that also
# writes the id into the block it creates) but the two hand-seeded pages
# have to be addressable from a snippet written by hand.
MOVIES_PAGE_ID = "p_movies"
CONTROL_PAGE_ID = "p_00_control"

# Movie pages sort after Control in the rail: ``_`` < ``m`` in ascii and
# the rail sorts children by id.
MOVIE_PAGE_PREFIX = "pm_"
MOVIE_ID_PREFIX = "m_"

# Ids are `<prefix><seq + ID_BASE>`, so they are fixed width and sort in
# creation order the way `mint_ordered_id` does, without needing python
# at click time.
ID_BASE = 1000000

GENRES = [
    {"value": "action", "label": "Action"},
    {"value": "drama", "label": "Drama"},
    {"value": "scifi", "label": "Sci-fi"},
    {"value": "doc", "label": "Documentary"},
    {"value": "anim", "label": "Animation"},
]

GENRES_WITH_ANY = [{"value": "", "label": "Any genre"}, *GENRES]

# Same four films nu's movies.py seeds with.
SEED_MOVIES: list[dict] = [
    {
        "title": "Arrival",
        "year": 2016,
        "genre": "scifi",
        "rating": 8.5,
        "watched": True,
        "notes": "linguists save the world",
    },
    {
        "title": "Dune: Part Two",
        "year": 2024,
        "genre": "scifi",
        "rating": 9.0,
        "watched": True,
        "notes": "worm ride > sequel",
    },
    {
        "title": "The Menu",
        "year": 2022,
        "genre": "drama",
        "rating": 7.0,
        "watched": True,
        "notes": "eat the rich, literally",
    },
    {
        "title": "Perfect Days",
        "year": 2023,
        "genre": "drama",
        "rating": 8.0,
        "watched": False,
        "notes": "tokyo, tapes, toilets",
    },
]


# The one thing every block shares: a ref subclass carrying real mount
# props. Text and boolean refs treat a runtime write as their *value*, so
# this is the only way a snippet-authored input gets a label.
_LABELED = '''
    def labeled(base, **props):
        """A one-off Ref subclass whose class-level mount props are `props`.

        Bare refs cannot carry props: `enumerate_ui_refs` pulls them from
        `type(node)._mount_props()`, which is class-level. Declaring a
        subclass here is enough, and `wire_type` still walks the mro to
        the nearest `nu.ui.refs` ancestor, so the browser mounts a normal
        InputRef / SelectRef / SwitchRef.
        """
        return type(
            base.__name__,
            (base,),
            {"_mount_props": classmethod(lambda cls, _p=dict(props): dict(_p))},
        )
'''


# --- Movies/ : the form ------------------------------------------------------

# The block that creates a page. On submit it does three writes in one
# flow: the movie, the movie's page, and the counter bump. `movie_seq` is
# read *before* the bump by everything that needs the id, so the movie
# and its page agree on one key.
#
# The page's section carries source built at click time --
# `Str(head) + mid + Str(tail)` -- so the created block names its own
# movie by id. That is the whole closed-algebra claim in three lines:
# a page is a kv record, a section is a kv record, and source is a string.

MOVIES_FORM_SOURCE = f'''
    import nu
    import nu.ui
    from demo_space import DemoSpace
    from movies_blocks import (
        GENRES,
        ID_BASE,
        MOVIES_PAGE_ID,
        MOVIE_ID_PREFIX,
        MOVIE_PAGE_PREFIX,
        detail_parts,
    )

    MOVIE_PAGES = DemoSpace.pages.pages[MOVIES_PAGE_ID].pages
    HEAD, TAIL = detail_parts()

{_LABELED}

    def out(path):
        title = labeled(nu.ui.InputRef, label="Title", placeholder="e.g. Arrival")(
            path + ".title"
        )
        year = nu.ui.NumberInputRef(path + ".year")
        genre = labeled(
            nu.ui.SelectRef, label="Genre", options=GENRES, selected="drama"
        )(path + ".genre")
        rating = nu.ui.NumberInputRef(path + ".rating")
        watched = labeled(nu.ui.SwitchRef, label="Watched?", checked=True)(
            path + ".watched"
        )
        notes = labeled(
            nu.ui.TextAreaRef, label="Notes", placeholder="Quick thoughts...", rows=2
        )(path + ".notes")
        submit = nu.ui.ButtonRef(path + ".submit")
        feedback = nu.ui.AlertRef(path + ".feedback")

        # Minted per click, by the term. Everything below reads
        # `movie_seq` before the bump, so one submit is one key.
        key = nu.ToStr(DemoSpace.movie_seq + ID_BASE)
        mid = nu.Str(MOVIE_ID_PREFIX) + key
        pid = nu.Str(MOVIE_PAGE_PREFIX) + key
        name = nu.Str(title)

        record = nu.Dict.of(
            title=name,
            year=nu.ToInt(year),
            genre=nu.Str(genre),
            rating=nu.ToFloat(rating),
            watched=nu.Bool(watched),
            notes=nu.Str(notes),
        )
        page = nu.Dict.of(
            title=name,
            sections=nu.Dict.of(
                s_00_detail=nu.Dict.of(
                    name="detail",
                    tpl="program",
                    # Source, built at click time. The created block
                    # names its movie by id.
                    snippet=nu.Str(HEAD) + mid + nu.Str(TAIL),
                    order=0,
                    policy="on_navigate",
                ),
            ),
            pages=nu.Dict.of(),
        )

        # Field *order* on screen is first-mention order in the term:
        # `enumerate_ui_refs` walks the tree and the browser mounts what
        # it is handed. So the opening chain touches every input once, in
        # the order the form should read, and seeds it while it is there.
        return (
            DemoSpace.movie_seq.init(0)
            >> nu.ui.HeadingRef(path + ".h").set(label="Log a movie", level=3)
            >> title.set(nu.Str(""))
            >> year.set(2020.0, min=1900.0, max=2100.0, step=1.0, label="Year")
            >> genre.set(nu.Str("drama"))
            >> rating.set(7.0, min=1.0, max=10.0, step=0.5, label="Rating")
            >> watched.set(nu.Bool(True))
            >> notes.set(nu.Str(""))
            >> submit.set(label="Log it", variant="primary")
            >> feedback.set(
                title="",
                body=(
                    "Logging a movie also writes a page for it under Movies. "
                    "The rail is shipped by the driver, and nu has no "
                    "deep-wildcard subscription, so a page written by a block "
                    "shows up on the next reload."
                ),
                variant="info",
                dismissible=True,
            )
            >> nu.ReactForever(
                submit.clicked(),
                nu.IfDo(
                    nu.NotEmpty(name),
                    DemoSpace.movies.set_item(mid, record)
                    >> MOVIE_PAGES.set_item(pid, page)
                    >> DemoSpace.movie_seq.set(DemoSpace.movie_seq + 1)
                    # Before the inputs are cleared: `name` is a live read
                    # of the title input, not a captured value.
                    >> feedback.set(
                        title="Logged",
                        body=name
                        + nu.Str(" is in the shelf, and its page exists under ")
                        + nu.Str("Movies. Reload to see it in the rail."),
                        variant="ok",
                    )
                    >> title.set(nu.Str(""))
                    >> notes.set(nu.Str("")),
                    feedback.set(
                        title="Needs a title",
                        body="A movie page is named after the movie.",
                        variant="warn",
                    ),
                ),
            )
        )
'''


# --- Movies/<title> : the created page ---------------------------------------

# Written into kv as a string by the form block, with `__MOVIE_ID__`
# replaced by the id the click minted. `detail_parts()` splits it so the
# form can concatenate a Nu term into the middle.
#
# Delete removes the movie *and* the page, which is the pair that has to
# stay consistent: an orphan page whose movie is gone would render a hole.

_DETAIL_TEMPLATE = '''
    import nu
    import nu.ui
    from demo_space import DemoSpace
    from movies_blocks import MOVIES_PAGE_ID, MOVIE_ID_PREFIX, MOVIE_PAGE_PREFIX

    MOVIE_ID = "__MOVIE_ID__"
    PAGE_ID = MOVIE_PAGE_PREFIX + MOVIE_ID[len(MOVIE_ID_PREFIX):]

    MOVIE = DemoSpace.movies[MOVIE_ID]
    MOVIE_PAGES = DemoSpace.pages.pages[MOVIES_PAGE_ID].pages
    HERE = DemoSpace.movies.contains(MOVIE_ID)


    def out(path):
        heading = nu.ui.HeadingRef(path + ".title")
        year = nu.ui.StatRef(path + ".year")
        genre = nu.ui.StatRef(path + ".genre")
        rating = nu.ui.StatRef(path + ".rating")
        seen = nu.ui.BadgeRef(path + ".seen")
        notes = nu.ui.MarkdownRef(path + ".notes")
        remove = nu.ui.ButtonRef(path + ".remove")
        said = nu.ui.AlertRef(path + ".said")

        def text(ref, fallback):
            # `HERE` is re-read every time this is evaluated, so the same
            # paint renders the movie before a delete and the tombstone
            # after one.
            return nu.If(HERE, nu.ToStr(ref), nu.Str(fallback))

        def paint():
            return (
                heading.set(label=text(MOVIE.title, "gone"), level=2)
                >> year.set_label(nu.Str("Year"))
                >> year.set_value(text(MOVIE.year, "-"))
                >> genre.set_label(nu.Str("Genre"))
                >> genre.set_value(text(MOVIE.genre, "-"))
                >> rating.set_label(nu.Str("Rating"))
                >> rating.set_value(text(MOVIE.rating, "-"))
                >> seen.set(
                    label=nu.If(
                        HERE,
                        nu.If(MOVIE.watched, nu.Str("Watched"), nu.Str("Unseen")),
                        nu.Str("Deleted"),
                    ),
                    variant=nu.If(HERE, nu.Str("ok"), nu.Str("neutral")),
                )
                >> notes.set(text(MOVIE.notes, "_This movie was deleted._"))
            )

        return (
            paint()
            >> remove.set(label="Delete", variant="danger")
            >> said.set(
                title="",
                body=nu.Str("Movie ")
                + nu.Str(MOVIE_ID)
                + nu.Str(". Delete drops the movie and this page together."),
                variant="info",
            )
            >> nu.ReactForever(
                remove.clicked(),
                DemoSpace.movies.del_item(MOVIE_ID)
                >> MOVIE_PAGES.del_item(PAGE_ID)
                >> paint()
                >> said.set(
                    title="Deleted",
                    body=(
                        "The movie and this page are both gone from kv. "
                        "The rail still lists the page until you reload."
                    ),
                    variant="warn",
                ),
            )
        )
'''


def detail_parts() -> tuple[str, str]:
    """Split the detail template around its movie-id hole.

    The form block concatenates ``Str(head) + <minted id> + Str(tail)``
    at click time, because the id does not exist until someone clicks.
    """
    head, tail = _dedent(_DETAIL_TEMPLATE).split('"__MOVIE_ID__"')
    return head + '"', '"' + tail


# --- Movies/Control : stats, table, filters ----------------------------------

# Everything nu's movies.py has that is not the form. Two blocks: stats,
# and the shelf (filters + table together, because the filters drive the
# table and a block owns the refs it mounts).

_ROW = """
        ROW = nu.List.of(
            nu.DictAttrRef("r")["title"],
            nu.DictAttrRef("r")["year"],
            nu.DictAttrRef("r")["genre"],
            nu.DictAttrRef("r")["rating"],
            nu.If(nu.DictAttrRef("r")["watched"], nu.Str("yes"), nu.Str("no")),
            nu.DictAttrRef("r")["notes"],
        )
        COLUMNS = ["title", "year", "genre", "rating", "watched", "notes"]
"""

CONTROL_STATS_SOURCE = '''
    import nu
    import nu.ui
    from demo_space import DemoSpace

    WATCHED = nu.DictAttrRef("r")["watched"]


    def out(path):
        total = nu.ui.StatRef(path + ".total")
        watched = nu.ui.StatRef(path + ".watched")
        unseen = nu.ui.StatRef(path + ".unseen")
        latest = nu.ui.StatRef(path + ".latest")

        n = nu.Len(DemoSpace.movies)
        seen = nu.Count(
            nu.Filter(nu.Iter(DemoSpace.movies.values()), predicate=WATCHED, key="r")
        )
        # Ids are fixed width and monotonic, so the last key is the last
        # movie logged. No `latest_title` slot to keep in sync.
        last_key = nu.Last(nu.Sorted(nu.Iter(DemoSpace.movies)))

        def paint():
            return (
                total.set_label(nu.Str("Total"))
                >> total.set_value(nu.ToStr(n))
                >> watched.set_label(nu.Str("Watched"))
                >> watched.set_value(nu.ToStr(seen))
                >> unseen.set_label(nu.Str("Unseen"))
                >> unseen.set_value(nu.ToStr(nu.Sub(n, seen)))
                >> latest.set_label(nu.Str("Latest"))
                >> latest.set_value(
                    nu.If(
                        nu.Gt(n, nu.Int(0)),
                        nu.ToStr(DemoSpace.movies[last_key].title),
                        nu.Str("-"),
                    )
                )
            )

        return (
            nu.ui.HeadingRef(path + ".h").set(label="Your shelf", level=3)
            >> paint()
            >> nu.ReactForever(DemoSpace.movies.on_change(), paint())
        )
'''

CONTROL_SHELF_SOURCE = f'''
    import nu
    import nu.ui
    from demo_space import DemoSpace
    from movies_blocks import GENRES_WITH_ANY

{_LABELED}

    def out(path):
        table = nu.ui.TableRef(path + ".shelf")
        min_rating = nu.ui.NumberInputRef(path + ".min_rating")
        # "Any genre" is the empty value, and a Radix Select shows its
        # placeholder rather than an empty option, so the placeholder is
        # what names the unfiltered state.
        genre = labeled(
            nu.ui.SelectRef,
            label="Genre",
            options=GENRES_WITH_ANY,
            selected="",
            placeholder="Any genre",
        )(path + ".genre")
        watched_only = labeled(
            nu.ui.SwitchRef, label="Already watched", checked=False
        )(path + ".watched_only")
        apply = nu.ui.ButtonRef(path + ".apply")
        clear = nu.ui.ButtonRef(path + ".clear")
        empty = nu.ui.TextRef(path + ".empty")

{_ROW}
        def rows(predicate):
            rows_iter = nu.Iter(DemoSpace.movies.values())
            if predicate is not None:
                rows_iter = nu.Filter(rows_iter, predicate=predicate, key="r")
            return nu.Dict.of(
                columns=COLUMNS,
                rows=nu.Collect(nu.Map(rows_iter, transform=ROW, key="r")),
            )

        filtered = rows(
            nu.And(
                nu.Ge(nu.DictAttrRef("r")["rating"], nu.ToFloat(min_rating)),
                nu.Or(
                    nu.Eq(nu.Str(genre), nu.Str("")),
                    nu.Eq(nu.DictAttrRef("r")["genre"], nu.Str(genre)),
                ),
                nu.Or(nu.Not(nu.Bool(watched_only)), nu.DictAttrRef("r")["watched"]),
            )
        )

        return (
            # Order on screen is first-mention order in the term, so the
            # filter row is seeded in the order it should read before the
            # table is painted.
            nu.ui.HeadingRef(path + ".h").set(label="Movies", level=3)
            >> min_rating.set(1.0, min=1.0, max=10.0, step=0.5, label="Min rating")
            >> genre.set(nu.Str(""))
            >> watched_only.set(nu.Bool(False))
            >> apply.set(label="Apply", variant="secondary")
            >> clear.set(label="Clear", variant="ghost")
            >> empty.set(nu.Str("Every movie you have logged. Filters redraw the rows."))
            >> table.set(rows(None))
            >> (
                # The table repaints on any write to `movies`, so logging
                # one on Movies/ lands here without a refresh.
                nu.ReactForever(DemoSpace.movies.on_change(), table.set(rows(None)))
                | nu.ReactForever(apply.clicked(), table.set(filtered))
                | nu.ReactForever(
                    clear.clicked(),
                    min_rating.set_value(1.0)
                    >> genre.set(nu.Str(""))
                    >> watched_only.set(nu.Bool(False))
                    >> table.set(rows(None)),
                )
            )
        )
'''


# --- Prose -------------------------------------------------------------------

MOVIES_INTRO_PROSE = """# Movies

nu's `examples/movies.py`, as a page tree instead of one page with a
`/detail` route.

This page is the **form and nothing else**. Log a movie and two things
happen: the movie lands in `DemoSpace.movies`, and a page for it is
written into `DemoSpace.pages` right under this one. The block below is
an ordinary Nu tree; the page tree is ordinary kv; so a tree adding a
page is just a write.

Stats, the table and the filters live on **Control**. One page per movie
lives beside it.
"""

MOVIES_RAIL_PROSE = """**On the rail not updating.** nu has no
deep-wildcard reactive subscription, so the Pages driver re-ships the
page tree only after writes *it* makes -- create, rename, delete from the
rail itself. A page written by a block is in kv immediately and is
correct immediately; the rail just has not been told. Reload the page and
it is there.

Nothing here papers over that. The form says it in the banner every time
it creates one, because a page you cannot see is worse than one you were
told to go look for.
"""

CONTROL_INTRO_PROSE = """# Control

Everything `movies.py` has that is not the form: the stats row, the
table, and the filters.

Both blocks read `DemoSpace.movies` and react to `on_change()`, so
logging a movie on **Movies** updates them without a reload -- kv is a
shared path and that is the whole wire. The page tree is the thing that
does not auto-refresh, not the data.
"""

MOVIES_OUTRO_PROSE = """Each movie page holds one program block whose
source names its movie by id, baked in when the block wrote it. Deleting
from a movie page removes the movie and its page in one flow, so the two
never drift.
"""


def _dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip()


# Sources are written indented so they read as part of this module; the
# blocks themselves have to be flush-left python.
CONTROL_SHELF_SOURCE = _dedent(CONTROL_SHELF_SOURCE)
CONTROL_STATS_SOURCE = _dedent(CONTROL_STATS_SOURCE)
MOVIES_FORM_SOURCE = _dedent(MOVIES_FORM_SOURCE)
