# Fabrics

A Ref is only resolvable through the fabric that owns its address. Each fabric ships its own Ref types; you pick a fabric by picking which Ref you declare a slot with.

Every fabric but `nu.mem` lives under `nustd`, which is a separate import from `nu`. `nu` is the language plus the memory fabric, and `nustd` is the other fabrics plus the standard library, so a module that declares a `nustd` slot needs both `import nu` and `import nustd`.

Two you are bound to unless told otherwise:

- `nu.mem` - shape fabric over plain nested python dicts. Ephemeral, in-process, the default. Its Refs sit at the top of `nu`, from `nu.StrRef`/`nu.IntRef`/`nu.ListRef`/`nu.DictRef` up to `nu.ShapeRef`/`nu.ProgramRef`.
- `nustd.kv` - virtuals KV-storage fabric for Shapes, over rocksdb, lmdb, redis or memory. `nu.mem`'s Refs plus `ViewRef`, `Kh57Ref`, primitive-collection Refs, and the `Transaction`/`Snapshot`/`Atomic`/`RetryOnConflict` spans. Same program, durable.

The rest exist and are context. They are not bound on your surface unless the task says so.

- `nustd.service` - expose a plain python object's methods as Nu Refs.
- `nustd` itself, at its top level - typed Nu surfaces over python's standard library: `nustd.uuid`, `nustd.datetime`, `nustd.pathlib` and the rest.
- `nustd.http` - http endpoints as Refs.
- `nustd.llm` - OpenAI-compatible chat over ollama, openai, openrouter, groq, cerebras, vllm, xai.
- `nustd.cc` - Claude Code sessions as Refs.
- `nustd.ui` - component fabric; Refs are widgets, containers are pages, served over http.
- `nustd.cluster` - Ray compute fabric.
- `nustd.mp` - multiprocessing compute fabric.
- `nustd.proxy` - transparent RPC transport that wraps another fabric over the wire.

The catalogue you are given lists no fabric Refs and none of their verbs, so read a fabric's surface before writing against it.
