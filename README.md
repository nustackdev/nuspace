# nuspace

A live computing space for people and agents.

> Early. Things move fast and the store format is not frozen yet.

## About

A space is made of **planes**, and planes are made of **cells**: a note, a table, a job, a lens into your data, a conversation with an agent. They live side by side, talk to each other, and grow together into one coherent system.

- **It reacts.** Live isn't a websocket someone wired up for one screen. Every value in the space can be reacted to by anything else, so all of it is live.
- **It remembers.** Every write is persisted, in a transaction, as it happens. Storage is sharded by design, so a cell holds a billion rows the same way it holds a counter.
- **It draws.** A cell puts text, tables, charts and forms on screen the same way it saves a value, and every open tab stays in sync.
- **It scales.** The same program runs in a worker, across processes or on a cluster, without changing shape.
- **It grows.** The kernel only runs things. Everything else is a plane, even the system. Nothing you can't extend or replace.
- **It is programmable.** It doesn't offer an API, it is one. People and agents write programs with the same reach. Not a menu of calls: a language.
- **It is made of itself.** There is no outside. The services that keep your space running, the operations that change it, the screens you use it through: all written in the same language your cells speak. So a cell can do anything nuspace can. Build a plane. Start a job. Rewrite a service. So can an agent. nuspace is a complete computer that can reprogram itself while it runs.

## Why it works

nuspace is built on [Nu](https://github.com/nustackdev/nu) and runs Nu, where everything is an interaction. Reading a disk, drawing a table, running a job, calling a model: same primitive, different place. Persistence, reactivity, interfaces and distribution aren't four systems glued together. They are one primitive on different fabrics, which is why every cell gets all of them for free, and why the space can keep growing without falling apart.

## Try it

```bash
pip install nuspace
nuspace serve my.nuspace
```

A browser opens on http://127.0.0.1:8080 and your space is alive. Press `/` on a plane to add a cell.

Planes and snippets are extensions that come from **nuverse**, installed alongside. Bring your own and they live in the space like everything else.

## Yours

Self-hosted. Your space is a directory on your machine.

## License

GNU Affero General Public License v3.0. See [LICENSE.md](LICENSE.md).
