<div align="center">
  <h3>
    nuspace - your computational space
  </h3>
  For everything you work with: notes, data, tools, agents. Open-source, self-hosted, your data stays local.
</div>

<br/>

<div align="center">

  [![Discord](https://img.shields.io/badge/discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/tCa8YE7XVr)
  [![Twitter Follow](https://img.shields.io/twitter/follow/nustackdev?style=social)](https://twitter.com/nustackdev)

  [![Platform Support](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-blue)]()
  [![PyPI - Python Version](https://img.shields.io/badge/python-%3E%3D%203.10-blue)](https://pypi.org/project/nuspace/)
  [![PyPI Package](https://img.shields.io/pypi/v/nuspace?color=yellow)](https://pypi.org/project/nuspace/)
  [![License](https://img.shields.io/badge/License-AGPL%20v3-orange.svg)](https://www.gnu.org/licenses/agpl-3.0)
  [![PyPI Downloads](https://img.shields.io/pypi/dw/nuspace?color=green)](https://pypi.org/project/nuspace/)

</div>

<br/>

---

<h3 align="center">
  <a href="#ℹ️-about"><b>About</b></a> &bull;
  <a href="#quickstart"><b>Quickstart</b></a> &bull;
  <a href="#community"><b>Community</b></a>
</h3>

---

# ℹ️ About

Build your computational space for everything you work with: notes, data, tools, agents.

Elsewhere, a note is a dead document, data is scattered, tools are siloed and an agent's work is lost in chat. In nuspace, they're all connected cells: living programs that hold data, logic and look in one form.

- **Cell**: the one building block. A note, a table, a chart, a job, an agent at work.
- **Living program**: every cell runs. It keeps its state, reacts to the rest of the space and draws itself on screen.
- **Connected**: change one cell and everything that depends on it follows, live, in every open tab.

> **Program anything.** The data, the logic, the look, even the space itself. You and your agents shape it together, on your machine.

> Early. Things move fast and the store format is not frozen yet.

## What it can do

Every cell gets all of it, nothing to wire up.

- **Any data.** A note, a table, a song, a billion-entry log, a genome.
- **Any logic.** Summarize your inbox, dim the lights at sunset, render a video.
- **Any UI.** A cell draws itself. Text, tables, charts, forms.
- **It's live.** Change one cell and everything that depends on it follows live. UI too.
- **Work scales.** The same cell runs in a worker, across processes or on a cluster.
- **Data scales.** A counter or a billion rows, same cell. Storage shards underneath.
- **It's made of itself.** The space has the same shape as its cells, so you and your agents can program it too.


## Quickstart

### Install

Python 3.10 or newer.

```bash
pip install nuspace
```

### Run

```bash
nuspace run my.nuspace
```

A browser opens on http://127.0.0.1:8080 and your space is live. Press `/` on a plane to add a cell. `--headless` runs it with nothing drawn.

### Try a demo

A throwaway space with a full app in it.

```bash
pip install "nuspace[demos]"
nuspace demo movies
```

`nuspace demo` lists them all.

### Next

- `nuspace doctor` checks the install: versions, extras, extensions.
- Planes and snippets are extensions, found on install through the `nuspace.extensions` entry point. Bring your own and they live in the space like everything else.
- Your space is a directory on your machine. All state lives in that one folder.

## Community

### Badge

Building on nuspace? Add the badge to your README:

[![nuspace](https://img.shields.io/badge/built%20with-nuspace-%237A4CE0)](https://github.com/nustackdev/nuspace)

```
[![nuspace](https://img.shields.io/badge/built%20with-nuspace-%237A4CE0)](https://github.com/nustackdev/nuspace)
```

### Questions

1. [Visit the website](https://nustack.dev)
2. [Open a feature request or report a bug](https://github.com/nustackdev/nuspace/issues)
3. [Join the Discord](https://discord.gg/tCa8YE7XVr)

## License

GNU Affero General Public License v3.0. See [LICENSE.md](LICENSE.md).
