<div align="center">
  <img width="112" alt="nuspace" src="https://nustack.dev/brand/logo-square-512@2x.png" />
  <h1>nuspace</h1>
  <p>Computational space for everything you work with: notes, data, tools, agents.</p>
  
  [![Python](https://img.shields.io/badge/python-%3E%3D%203.10-blue)](https://pypi.org/project/nuspace/)
  [![PyPI](https://img.shields.io/pypi/v/nuspace?color=yellow)](https://pypi.org/project/nuspace/)
  [![Downloads](https://img.shields.io/pypi/dw/nuspace?color=green)](https://pypi.org/project/nuspace/)
  [![License](https://img.shields.io/badge/license-AGPL%20v3-orange.svg)](https://github.com/nustackdev/nuspace/blob/main/LICENSE.md)
  
  [![Discord](https://img.shields.io/badge/discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/tCa8YE7XVr)
  [![X](https://img.shields.io/twitter/follow/nustackdev?style=social)](https://x.com/nustackdev)

</div>


Elsewhere, a note is a dead document, data is scattered, tools are siloed and an agent's work is lost in chat. In nuspace, they're all connected cells: living programs that hold data, logic and look in one form.

**nuspace in action:**

https://github.com/user-attachments/assets/c74b7f85-b8c5-4796-8de6-bfc1b7679eb8

**Other demos:**

<details>
<summary><b>Ops space</b></summary>

A real storefront, its jobs, logs, deploys and alert rules, run and watched from one space, all live.

https://github.com/user-attachments/assets/236dbecd-f734-4aa3-965d-2cbc3bea27e7

</details>

<details>
<summary><b>Data space</b></summary>

A shop's orders, customers and events as dashboards that follow every sale, import and price change.

https://github.com/user-attachments/assets/0101726c-da30-4a36-9323-9f41a14a6be1

</details>

<details>
<summary><b>Design space</b></summary>

Tokens, the mark, components, mocks and checks drawn from one spec, with releases cut by a job, all live.

https://github.com/user-attachments/assets/9d8cb9ca-2e41-4a12-8caa-412099eec02c

</details>

<details>
<summary><b>ML space</b></summary>

Launch runs, watch them learn, use their models and build your own tools around them, all live.

https://github.com/user-attachments/assets/7d6bb201-2ac4-462e-9080-c40067c3c6fc

</details>

<details>
<summary><b>Research space</b></summary>

A research desk on LLMs: papers weighed against claims, our own evals on Claude beside them, all live.

https://github.com/user-attachments/assets/dc573d2e-ab0a-45e6-87ce-8d69a1d9d8f4

</details>

<details>
<summary><b>Agents space</b></summary>

Brief, watch and steer Claude Code sessions, chain them into flows, and build your own tools around them, all live.

https://github.com/user-attachments/assets/a3ec5bff-7ca7-41c3-91d0-6f5f927a0108

</details>

<details>
<summary><b>Memes space</b></summary>

Every launch and trade on the meme market, streamed into pages that redraw as they land.

https://github.com/user-attachments/assets/8979c5b9-6c8c-4675-81e5-3f25c5ec7cdd

</details>

<details>
<summary><b>Movies space</b></summary>

A film base you run yourself. Films, people and timelines, all linked, all live.

https://github.com/user-attachments/assets/edbda441-2f65-4f46-8965-dfdd414becba

</details>

## What it can do

**Program anything.** The data, the logic, the look, even the space itself.

- **Any data.** A note, a table, a song, a billion-entry log, a genome.
- **Any logic.** Summarize your inbox, dim the lights at sunset, render a video.
- **Any UI.** A cell draws itself. Text, tables, charts, forms.
- **It's live.** Change one cell and everything that depends on it follows live. UI too.
- **Work scales.** The same cell runs in a worker, across processes or on a cluster.
- **Data scales.** A counter or a billion rows, same cell. Storage shards underneath.
- **It's made of itself.** The space has the same shape as its cells, so you and your agents can program it too.

## Who it's for

<details>
<summary><b>For agents</b></summary>

- **Reach:** any data, any cell, the space itself
- **Memory:** work that outlives your context window
- **Tools:** build your own, then use them
- **Visibility:** everything you build, your human sees too

</details>

<details>
<summary><b>For individuals</b></summary>

- **Knowledge:** notes, reading, a second brain
- **Tracking:** habits, money, films, health
- **Research:** sources, claims, scores, live
- **Automation:** your scripts and home, with a screen

</details>

<details>
<summary><b>For teams</b></summary>

- **Knowledge:** team wikis, BI, research
- **Dashboards:** every data source, live
- **Ops:** every automation and job in one place
- **Infra:** ML runs, pipelines, deploys

</details>

## Get started

Hand it to your agent or install manually:

<details open>
<summary><b>Manual</b></summary>

Install from PyPI and run a space yourself. Python 3.10 or newer, Linux or macOS.

1. **Install**

   ```bash
   pip install nuspace
   ```

2. **Run**

   ```bash
   nuspace run my.nuspace
   ```

   A browser opens on your space. Press `/` on a plane to add a cell.

3. **Try a demo**

   ```bash
   pip install nudemos
   nuspace run --with nudemos.movies
   ```

   A throwaway space with a full app in it.

</details>

<details>
<summary><b>Claude Code</b></summary>

Claude learns nu and nuspace from the skills, installs nuspace and opens your first space.

1. **Add the marketplace**

   ```bash
   claude plugin marketplace add nustackdev/nuskills
   ```

2. **Install the plugin**

   ```bash
   claude plugin install nuskills@nustack
   ```

   Adds `/nuskills:nu` and `/nuskills:nuspace`.

3. **Ask for a space**

   ```text
   Install nuspace, start a space and build a live monitor of this machine.
   ```

   Claude loads the nuspace skill on its own when the task matches.

</details>

<details>
<summary><b>Codex</b></summary>

The same repo is a Codex marketplace. Same skills, same text.

1. **Add the marketplace**

   ```bash
   codex plugin marketplace add nustackdev/nuskills
   ```

2. **Install the plugin**

   ```text
   /plugins
   ```

   Run it in a session and pick `nuskills`.

3. **Ask for a space**

   ```text
   $nuspace Install nuspace, start a space and build a live monitor of this machine.
   ```

   Or skip `$nuspace`, Codex loads it when the task matches.

</details>

<details>
<summary><b>Other agents</b></summary>

The skills are plain folders. Drop them where your agent looks for skills.

1. **Get the skills**

   ```bash
   git clone https://github.com/nustackdev/nuskills
   ```

2. **Copy them in**

   ```bash
   mkdir -p ~/.agents/skills
   cp -r nuskills/skills/nu nuskills/skills/nuspace ~/.agents/skills/
   ```

   Or into a repo's `.agents/skills` for one project.

3. **Ask for a space**

   ```text
   Install nuspace, start a space and build a live monitor of this machine.
   ```

</details>

> [!NOTE]
> nuspace is early. Things move fast and the store format is not frozen yet.

## How it works

**One primitive, all the way down.** nuspace is built on one idea: every resource is a Ref, and everything you do with it is an Interaction. nu implements that idea, and nuspace runs nu programs. Every cell in your space is one.

| | Layer | What it is |
| --- | --- | --- |
| 01 | <code>the theory</code> <br/> [**interaction-model**](https://github.com/nustackdev/interaction-model) | Every resource is a Ref: a KV slot, a UI widget, an LLM endpoint, a remote object. Everything you do with it is an Interaction. |
| 02 | <code>the primitive</code> <br/> [**nu**](https://github.com/nustackdev/nu) | The interaction model implementation in Python. |
| 03 | <code>the std library</code> <br/> [**nustd**](https://github.com/nustackdev/nu/tree/main/pkgs/nustd) | nu Refs and Interactions for everyday tasks. |
| 04 | <code>the space</code> <br/> [**nuspace**](https://github.com/nustackdev/nuspace) | A space that runs nu programs. Every cell is one. |
| 05 | <code>the ecosystem</code> <br/> [**nuverse**](https://github.com/nustackdev/nuverse) | Ready made spaces and extensions, one install away. |
| + | **your space**, on top of it all | Everything below exists so your space can be anything. |

## Community

- [Discord](https://discord.gg/tCa8YE7XVr) for questions and what you build
- [X @nustackdev](https://x.com/nustackdev) for releases and demos
- [Issues](https://github.com/nustackdev/nuspace/issues) for bugs and feature requests

Building on nuspace? Add the badge to your README:

[![nuspace](https://img.shields.io/badge/built%20with-nuspace-%237A4CE0)](https://github.com/nustackdev/nuspace)

```md
[![nuspace](https://img.shields.io/badge/built%20with-nuspace-%237A4CE0)](https://github.com/nustackdev/nuspace)
```

## License

GNU Affero General Public License v3.0. See [LICENSE.md](https://github.com/nustackdev/nuspace/blob/main/LICENSE.md).
