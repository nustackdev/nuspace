# Changelog

## Packages shipped from this repo

- **nuspace** (the runtime, the `nuspace` command) — 0.1.0
- **nuspace-ui** (the compiled web bundle) — 0.1.0

Below is the changelog for **nuspace** - the full commit stream. Newest first.
The `nuspace-ui` wheel is the same source tree's vite output and is not tracked
separately here.

## 0.1.0 — 2026-09-14

- Add CI/CD: publish-nuspace and publish-nuspace-ui workflows, trusted publishing, tag-driven releases
- Rename the distribution nuspace-py to nuspace, make nuspace-ui a hard dependency
- Keep a hot spare worker so navigation skips the spawn
- Let the page worker follow its own sections instead of respawning
- Give workers the store's change feed and drop the proxy workaround
- Run a whole page in one pool worker
- Run page sections in pool workers with the connection's session proxied in
- Attach the apps and page supervisors and assemble the space in one tree
- Add the lens surface: shape reflection as Miller columns
- Add the apps web surface and compose both drivers into one space
- Add the web layer: pages ref, nav ref and the reactive driver
- Bind the reconcile attrs with Let instead of SetCmd
- Flatten pages onto parent and children relations, drop recursive addressing
- Add the pages submodule and break the shapes import cycle
- Organize apps into shapes, ops and runner
- Replace the runner with a reactive apps driver on nu.mp_pool
- Add the runner: one Nu tree that dispatches apps onto a worker pool
- Add a recursive shape slot and runtime-depth addressing
- Remove the imperative driver layer
- Make every block a Nu program addressed by tpl
- Restore the left inset on flat rail rows
- Extract the shared rail row, header and roving focus into components
- Unify the section status and spec contracts into one home
- Decompose the lens surface into interactions over per-op refs
- Decompose the apps surface into interactions over per-op refs
- Decompose the pages surface into interactions over per-op refs
- Restructure the ui project into app, design, components and refs
- Remove a stray character that broke taste_app import
- Add the taste app: a nuagent run over the movie shelf
- Mount Apps in the demo; flatten apps in the probe scripts
- Build the Apps pillar on a space-lifetime supervisor
- Add the Movies app to the demo
- Fix theme color-scheme, banner noise, and the lens cursor on pop
- Restyle lens on the design system
- Rebuild the pages rail: layout, reveal model, keyboard
- Give pages a real masthead
- Make the demo's port and store env-overridable
- Rebuild the shell chrome on kit components; add theming
- Add a biome config for the nuspace ui bundle
- Replace the prose leaf with a ProseMirror editor
- Resolve the worker's kv scope from config; add the Ticker demo page
- Adopt nu.prog for section construction
- Rebuild pages on an out-of-process section executor
- Add section path tags in both modes and + text / + llm section templates
- Fix section mounting: mount only ui refs under the owning section's path prefix
- Add Pages section: recursive Page shape, PagesRef with nested rail + section canvas, code/display modes
- Add Apps section: nested Group shape, AppsRef with tree+editor, router depth, CRUD flows
- Fix LensRef: strip runtime payload mutation; browser owns cursor, server stateless
- Add nuspace 3-page shell: Apps/Pages/Lens routes, HeaderRef + SidebarRef, LensRef path-as-observable
- Upgrade nuspace to ui-kit 0.1.3 and use kit's registerRefEntry directly
- Add LensRef v1: nuspace server + ui split, refs/lens, examples/lens_demo, App.tsx dupe fix
- Wipe web/ mvp: rm server + block ui; rename ui to shell; scaffold refs/ + nuspace_ui.py entry
- Fix Space ref read-back: proxy body/tag wiring; add read_probe example
- Rewrite nuspace core as Nu-dialect: typed Shape refs (Space/App/Page/Section, AppsRef/SectionsRef with .add/.run), examples/{run,seed_direct,seed_via_proxy}.py; gut CLI, drop old primitives/control/app
- Reorganize src/nuspace/ui/ into src/nuspace/web/{server,ui}; fix tailwind @source path
- Refactor nuspace to kind-blind: block is just a snippet, mount enumerates ui refs from the term; add editable code mode + update_snippet primitive; empty-block creation
- Add stat block kind: reactive display of another text block's value
- Add per-block display/code toggle and + new page / + new block ui actions
- Add nuspace mvp v0: python host, react spa, kv primitives, cli, text-block snippet load
- Add dev scaffolding
- Init nuspace
