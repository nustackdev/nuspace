<div align="center">
  <img width="112" alt="nuspace" src="https://nustack.dev/brand/logo-square-512@2x.png" />
  <h1>nuspace</h1>
  <p><b>Your computational space.</b> Human-first. Agent-native.</p>

  [![Python](https://img.shields.io/badge/python-%3E%3D%203.10-blue)](https://pypi.org/project/nuspace/)
  [![PyPI](https://img.shields.io/pypi/v/nuspace?color=yellow)](https://pypi.org/project/nuspace/)
  [![Downloads](https://img.shields.io/pypi/dw/nuspace?color=green)](https://pypi.org/project/nuspace/)
  [![License](https://img.shields.io/badge/license-AGPL%20v3-orange.svg)](https://github.com/nustackdev/nuspace/blob/main/LICENSE.md)

  [![Discord](https://img.shields.io/badge/discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/tCa8YE7XVr)
  [![X](https://img.shields.io/twitter/follow/nustackdev?style=social)](https://x.com/nustackdev)

  [Quick start](#quick-start) · [Gallery](#gallery) · [Usage](#usage) · [Docs](https://nustack.dev/docs/nuspace) · [Website](https://nustack.dev)

</div>

A society of tiny interconnected programs that hold data, run logic and render UI. Together, they compose into your: second brain, AI systems, data stack, software factory, research lab. Humans get the space as UI, agents get it as code.

## Quick start

```bash
pip install nuspace && nuspace run --with quickstart
```

Python 3.10 or newer. A browser opens on your space with a quickstart page. To let your agent set it up instead, see [With your agent](#with-your-agent).

https://github.com/user-attachments/assets/c74b7f85-b8c5-4796-8de6-bfc1b7679eb8

<p align="center"><sub>Tour: nustack's own org space, built from an empty page.</sub></p>

## Gallery

Spaces built with nuspace. Each one is a set of small programs talking to each other.

<details>
<summary><b>Ops</b> · Run your ops from one space.</summary>

A release breaks, the incident pages, a rule rolls it back.<br/>
<sub>Made of: storefront · deploy job · log · incident · rollback rule</sub>

https://github.com/user-attachments/assets/af777956-59ad-4158-8b47-8c26300b3498

</details>

<details>
<summary><b>Dashboards</b> · A spreadsheet for anything, live.</summary>

Orders stream in, every chart and metric follows.<br/>
<sub>Made of: orders stream · events table · export job · metric · price button</sub>

https://github.com/user-attachments/assets/69b8ca6e-0c22-400f-8bb3-44d681d3c0b5

</details>

<details>
<summary><b>Design system</b> · Your design system, one live spec.</summary>

Tokens, mocks and checks that follow every change.<br/>
<sub>Made of: tokens · proposal · release job · color checker</sub>

https://github.com/user-attachments/assets/b759347c-a44b-4074-bc51-0a4dcd050492

</details>

<details>
<summary><b>ML training</b> · Train models in your own ML lab.</summary>

Launch runs, watch them learn, stop them by rule.<br/>
<sub>Made of: run launcher · metrics · model · compare page · stop rule</sub>

https://github.com/user-attachments/assets/653a34e7-4dd5-419a-83e3-3b4c83c5d11b

</details>

<details>
<summary><b>Research</b> · Sources, claims and scores, kept live.</summary>

A paper flips a claim everywhere, an eval reruns.<br/>
<sub>Made of: probe · papers · claims · eval run</sub>

https://github.com/user-attachments/assets/f4d9eae4-1c46-4944-b5df-cc330d5eb1a3

</details>

<details>
<summary><b>Memes</b> · A blockchain, read live.</summary>

Every launch and trade, streamed into pages.<br/>
<sub>Made of: solana stream · coin pages · ranking · radar</sub>

https://github.com/user-attachments/assets/f128ab39-3453-4124-beb7-994ea8f42f91

</details>

<details>
<summary><b>Movies</b> · Your personal movie tracker.</summary>

Films, people and timelines, all linked, all live.<br/>
<sub>Made of: film base · log import job · tonight page · ratings</sub>

https://github.com/user-attachments/assets/af5b4f75-eef9-4bfa-8fb1-42bceeac87ec

</details>

## Program anything

The data, the logic, the UI, even the space itself.

- **Any data.** A note, a table, a song, a billion-entry log, a genome.
- **Any logic.** Branches and loops, reactions, parallel runs and races.
- **Any UI.** A cell draws itself. Text, tables, charts, forms.
- **It's live.** Change one cell and everything that depends on it follows. UI too.
- **Work scales.** The same cell runs in a worker, across processes or on a cluster.
- **Data scales.** A counter or a billion rows, same cell. Storage shards underneath.
- **It's made of itself.** The space has the same shape as its cells, so you and your agents can program it too.

## How it works

A space is made of **nus**: small programs written in [nu](https://github.com/nustackdev/nu), a Python programming model. A nu doesn't wire a database, a backend and a UI together. It names what it touches as Refs (a table row, a chart, an LLM, a file) and says what to do with them as Interactions (read, write, branch, compose).

- Every cell on a page is a nu: a note, a table, a chart, a job.
- nuspace runs hundreds of them as one live system. What one nu names, another can watch, steer or build on.
- The space itself is made of nus, so you and your agents program it the same way.

## Usage

```bash
# run the nearest space up from here, else your home space
nuspace run

# make the current directory a space, data in .nuspace/
nuspace init

# a throwaway space
nuspace run --tmp

# no web, just the space and its kernel
nuspace run --headless
```

Try a full app from the demos:

```bash
pip install nudemos
nuspace run --with nudemos.movies
```

## With your agent

Give your agent the nu and nuspace skills, then ask it to install nuspace and build with you.

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude plugin marketplace add nustackdev/nuskills
claude plugin install nuskills@nustack
```

Adds `/nuskills:nu` and `/nuskills:nuspace`. Then ask:

```text
Install nuspace and open my space with the quickstart page. Set up whatever's missing.
```

</details>

<details>
<summary><b>Codex</b></summary>

```bash
codex plugin marketplace add nustackdev/nuskills
```

Run `/plugins` in a session and pick `nuskills`. Then ask:

```text
Install nuspace and open my space with the quickstart page. Set up whatever's missing.
```

</details>

<details>
<summary><b>Other agents</b></summary>

```bash
git clone https://github.com/nustackdev/nuskills
mkdir -p ~/.agents/skills
cp -r nuskills/skills/nu nuskills/skills/nuspace ~/.agents/skills/
```

Or into a repo's `.agents/skills` for one project. Then ask:

```text
Install nuspace and open my space with the quickstart page. Set up whatever's missing.
```

</details>

## The stack

**One primitive, all the way down.** nuspace sits on a small stack, each layer its own repo:

- [**interaction-model**](https://github.com/nustackdev/interaction-model): the theory, every resource a Ref, Interactions first-class
- [**nu**](https://github.com/nustackdev/nu): the primitive, the interaction model in Python
- [**nustd**](https://github.com/nustackdev/nu/tree/main/pkgs/nustd): the standard library, storage, UI, workers and more
- **nuspace**: the space that runs nu programs (you are here)
- [**nuverse**](https://github.com/nustackdev/nuverse): the ecosystem, ready-made packages one install away

## Community

- [Discord](https://discord.gg/tCa8YE7XVr): ask questions, show your spaces
- [X @nustackdev](https://x.com/nustackdev): releases and work in progress
- [Issues](https://github.com/nustackdev/nuspace/issues): bugs and feature requests

Building on nuspace? Add the badge:

[![nuspace](https://img.shields.io/badge/built%20with-nuspace-%237A4CE0)](https://github.com/nustackdev/nuspace)

```md
[![nuspace](https://img.shields.io/badge/built%20with-nuspace-%237A4CE0)](https://github.com/nustackdev/nuspace)
```

## License

GNU Affero General Public License v3.0. See [LICENSE.md](https://github.com/nustackdev/nuspace/blob/main/LICENSE.md).
