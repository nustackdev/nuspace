"""Root click group for the ``nuspace`` CLI (rendered via rich-click).

Commands:

- ``nuspace init <dir>``          -- create dir + seed a "home" page.
- ``nuspace run <dir>``           -- start server (rocksdb + ws + control).
- ``nuspace add-page <slug>``     -- add a page (via server if running).
- ``nuspace add-block <p> text``  -- add a text block on a page.
- ``nuspace ls [<page>]``         -- list pages, or blocks on a page.

If a server is running for the same dir, commands hit its
``POST /control/primitive`` endpoint (only the server holds the rocksdb
lock). Otherwise, ``init`` / ``add-page`` / ``add-block`` fall back to
opening the db directly and running the primitive under ``nu.arun``.
``ls`` requires either the server or a readable db.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import rich_click as click

from nuspace.cli._meta import nuspace_version


click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.MAX_WIDTH = 100


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="nuspace: self-hosted Nu runtime.",
)
@click.version_option(nuspace_version(), "-V", "--version", prog_name="nuspace")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Root ``nuspace`` group."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# --- helpers ----------------------------------------------------------------


def _server_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _server_running(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        req = urllib.request.Request(  # noqa: S310
            f"{_server_url(host, port)}/control/state",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout):  # noqa: S310
            return True
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False


def _post_primitive(host: str, port: int, op: str, args: dict) -> None:
    body = json.dumps({"op": op, "args": args}).encode()
    req = urllib.request.Request(  # noqa: S310
        f"{_server_url(host, port)}/control/primitive",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        click.echo(f"error: {e.code} {detail}", err=True)
        sys.exit(1)


def _get_state(host: str, port: int) -> dict:
    with urllib.request.urlopen(  # noqa: S310
        f"{_server_url(host, port)}/control/state",
        timeout=5,
    ) as resp:
        return json.loads(resp.read().decode())


def _run_primitive_direct(dir_: Path, op: str, args: dict) -> None:
    """No server running: open the db in-process and run one primitive."""
    import nu
    from nuspace.control import build_primitive_term

    term = build_primitive_term(op, args)
    app = nu.With(
        nu.kv.rocksdb_navigator(str(dir_)),
        body=nu.kv.auto_flow_atomic(term),
    )
    asyncio.run(nu.arun(app))


def _dispatch(dir_: Path, host: str, port: int, op: str, args: dict) -> None:
    if _server_running(host, port):
        _post_primitive(host, port, op, args)
    else:
        _run_primitive_direct(dir_, op, args)


# --- commands ---------------------------------------------------------------


@cli.command()
@click.argument("dir", type=click.Path(file_okay=False, dir_okay=True))
def init(dir: str) -> None:
    """Create ``dir`` if needed, then seed a default "home" page."""
    path = Path(dir)
    path.mkdir(parents=True, exist_ok=True)
    _run_primitive_direct(path, "seed_home_if_empty", {})
    click.echo(f"nuspace initialised at {path}")


@cli.command()
@click.argument("dir", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--host", default=DEFAULT_HOST, show_default=True)
@click.option("--port", default=DEFAULT_PORT, show_default=True, type=int)
@click.option("--open-browser/--no-open-browser", default=False)
def run(dir: str, host: str, port: int, open_browser: bool) -> None:
    """Start the nuspace runtime backed by rocksdb at ``dir``."""
    import nu
    from nuspace.app import build_space_app

    path = Path(dir)
    path.mkdir(parents=True, exist_ok=True)
    app = build_space_app(path, host=host, port=port, open_browser=open_browser)
    try:
        asyncio.run(nu.arun(app))
    except KeyboardInterrupt:
        sys.exit(0)


@cli.command("add-page")
@click.argument("slug")
@click.option("--title", default=None, help="Display label (defaults to slug).")
@click.option("--dir", "dir_", default=".db", show_default=True, type=click.Path())
@click.option("--host", default=DEFAULT_HOST, show_default=True)
@click.option("--port", default=DEFAULT_PORT, show_default=True, type=int)
def add_page(slug: str, title: str | None, dir_: str, host: str, port: int) -> None:
    """Add a page to the space."""
    _dispatch(
        Path(dir_),
        host,
        port,
        "add_page",
        {"slug": slug, "title": title},
    )
    click.echo(f"added page: {slug}")


@cli.command("add-block")
@click.argument("page_slug")
@click.argument("template", type=click.Choice(["text", "stat"]))
@click.option("--source", "source_app_id", default="", help="Stat template: source block id.")
@click.option("--label", default="", help="Stat template: display label.")
@click.option("--dir", "dir_", default=".db", show_default=True, type=click.Path())
@click.option("--host", default=DEFAULT_HOST, show_default=True)
@click.option("--port", default=DEFAULT_PORT, show_default=True, type=int)
def add_block(
    page_slug: str,
    template: str,
    source_app_id: str,
    label: str,
    dir_: str,
    host: str,
    port: int,
) -> None:
    """Add a block on a page from a named snippet template."""
    from nuspace.core.primitives import mint_app_id
    from nuspace.snippets import stat_snippet, text_snippet

    app_id = mint_app_id()
    if template == "text":
        snippet = text_snippet(app_id)
    elif template == "stat":
        if not source_app_id:
            click.echo("stat template requires --source <block_id>", err=True)
            sys.exit(1)
        snippet = stat_snippet(app_id, source_app_id, label)
    else:  # click already validates; belt + braces
        click.echo(f"unknown template {template!r}", err=True)
        sys.exit(1)
    _dispatch(
        Path(dir_),
        host,
        port,
        "add_block",
        {"page_slug": page_slug, "snippet": snippet, "app_id": app_id},
    )
    click.echo(f"added block {app_id} on page {page_slug}")


@cli.command("ls")
@click.argument("page_slug", required=False)
@click.option("--dir", "dir_", default=".db", show_default=True, type=click.Path())
@click.option("--host", default=DEFAULT_HOST, show_default=True)
@click.option("--port", default=DEFAULT_PORT, show_default=True, type=int)
def ls(page_slug: str | None, dir_: str, host: str, port: int) -> None:
    """List pages, or blocks under ``page_slug`` if given."""
    if page_slug is None:
        _ls_pages(dir_, host, port)
    else:
        _ls_blocks(page_slug, dir_, host, port)


def _ls_pages(dir_: str, host: str, port: int) -> None:
    """Print one line per page: ``<slug>  "<title>"  (<n> blocks)[ (active)]``."""
    if _server_running(host, port):
        state = _get_state(host, port)
        active_slug = state.get("active_page", {}).get("slug") if state.get("active_page") else None
        for p in state.get("pages", []):
            slug = p["slug"]
            n = _count_blocks_via_switch(host, port, slug)
            marker = " (active)" if slug == active_slug else ""
            click.echo(f'{slug}  "{p["title"]}"  ({n} blocks){marker}')
        # restore active page if we shuffled it
        if active_slug:
            _post_primitive(host, port, "switch_page", {"slug": active_slug})
    else:
        listing = _read_pages_listing_direct(Path(dir_))
        for row in listing:
            marker = " (active)" if row["active"] else ""
            click.echo(f'{row["slug"]}  "{row["title"]}"  ({row["n_blocks"]} blocks){marker}')


def _ls_blocks(page_slug: str, dir_: str, host: str, port: int) -> None:
    if _server_running(host, port):
        _post_primitive(host, port, "switch_page", {"slug": page_slug})
        state = _get_state(host, port)
        ap = state.get("active_page")
        if not ap or ap["slug"] != page_slug:
            click.echo(f"page {page_slug!r} not found", err=True)
            return
        blocks = ap["blocks"]
    else:
        blocks = _read_blocks_direct(Path(dir_), page_slug)
    for b in blocks:
        fields = ", ".join(f"{f['type']}({f['path']})" for f in b["fields"]) or "-"
        click.echo(f"{b['id']}  {fields}")


def _count_blocks_via_switch(host: str, port: int, slug: str) -> int:
    """Server helper: switch to slug, read state, count blocks."""
    _post_primitive(host, port, "switch_page", {"slug": slug})
    state = _get_state(host, port)
    ap = state.get("active_page")
    if ap and ap["slug"] == slug:
        return len(ap["blocks"])
    return 0


def _read_pages_listing_direct(dir_: Path) -> list[dict]:
    """Direct-db listing with block counts per page."""
    import nu
    from nu.context.fabric import Provide
    from nuspace.core.shapes import ACTIVE_PAGE, Space

    captured: dict = {"rows": []}

    class _Capture:
        async def asetup(self, ctx: object) -> None:
            slugs_v, _ = await nu.arun(
                nu.kv.Snapshot(nu.Collect(nu.Iter(Space.pages_index))), ctx,
            )
            slugs = list(slugs_v or [])
            try:
                active_v, _ = await nu.arun(nu.kv.Snapshot(ACTIVE_PAGE), ctx)
                active = str(active_v) if active_v is not None else None
            except Exception:
                active = None
            rows = []
            for slug in slugs:
                try:
                    title_v, _ = await nu.arun(nu.kv.Snapshot(Space.pages[slug].title), ctx)
                    title = str(title_v)
                except Exception:
                    title = str(slug)
                try:
                    blocks_v, _ = await nu.arun(
                        nu.kv.Snapshot(nu.Collect(nu.Iter(Space.pages[slug].blocks))), ctx,
                    )
                    n = len(list(blocks_v or []))
                except Exception:
                    n = 0
                rows.append({"slug": str(slug), "title": title, "n_blocks": n,
                             "active": str(slug) == active})
            captured["rows"] = rows

        async def acleanup(self) -> None:
            return

    async def go() -> None:
        app = nu.With(
            nu.kv.rocksdb_navigator(str(dir_)),
            Provide(_Capture, {}),
            body=nu.Delay(0),
        )
        await nu.arun(app)

    asyncio.run(go())
    return captured["rows"]


def _read_blocks_direct(dir_: Path, page_slug: str) -> list[dict]:
    """Direct-db read of block entries for a page (matches mount payload shape)."""
    import nu
    from nu.context.fabric import Provide
    from nuspace.core.shapes import Space
    from nuspace.snippets import parse_snippet
    from nuspace.web.server.page import _enumerate_ui_refs, block_entry

    captured: dict = {"blocks": []}

    class _Capture:
        async def asetup(self, ctx: object) -> None:
            try:
                bl_v, _ = await nu.arun(
                    nu.kv.Snapshot(nu.Collect(nu.Iter(Space.pages[page_slug].blocks))),
                    ctx,
                )
            except Exception:
                captured["blocks"] = []
                return
            out = []
            for bid in list(bl_v or []):
                bid = str(bid)
                try:
                    snip_v, _ = await nu.arun(nu.kv.Snapshot(Space.apps[bid].snippet), ctx)
                    snippet = str(snip_v) if snip_v is not None else ""
                except Exception:
                    snippet = ""
                fields = []
                if snippet:
                    try:
                        fields = _enumerate_ui_refs(parse_snippet(snippet, f"apps/{bid}"))
                    except Exception:
                        fields = []
                out.append(block_entry(bid, snippet=snippet, fields=fields))
            captured["blocks"] = out

        async def acleanup(self) -> None:
            return

    async def go() -> None:
        app = nu.With(
            nu.kv.rocksdb_navigator(str(dir_)),
            Provide(_Capture, {}),
            body=nu.Delay(0),
        )
        await nu.arun(app)

    asyncio.run(go())
    return captured["blocks"]


def _read_state_direct(dir_: Path) -> dict:
    """Direct-db read of the mount payload -- no server.

    Uses a tiny capture fabric to grab the base ctx (with the rocksdb
    navigator bound) and reads the mount payload inside its ``asetup``.
    """
    import nu
    from nu.context.fabric import Provide
    from nuspace.web.server.page import build_mount_payload_from_kv

    captured: dict = {}

    class _Capture:
        async def asetup(self, ctx: object) -> None:
            captured.update(await build_mount_payload_from_kv(ctx))

        async def acleanup(self) -> None:
            return

    async def go() -> None:
        app = nu.With(
            nu.kv.rocksdb_navigator(str(dir_)),
            Provide(_Capture, {}),
            body=nu.Delay(0),
        )
        await nu.arun(app)

    asyncio.run(go())
    return captured


def main() -> None:
    """Console-script entrypoint for ``nuspace``."""
    cli()
