# Changelog

## Packages shipped from this repo

- **nuspace** (the runtime, the `nuspace` command) — 0.3.1
- **nuspace-ui** (the compiled web bundle) — 0.3.0
- **nuverse** (the Planes and snippets a space ships with) — 0.1.0

Below is the changelog for **nuspace** - the full commit stream. Newest first.
The `nuspace-ui` wheel is the same source tree's vite output and is not tracked
separately here.

## Unreleased

- Apps become Planes: registered data seeded with cells, created from one add plane popup
- The sidebar is one tree of planes, reordered and nested by dragging rows
- Everything is called a plane or a cell, across the interface, wire and code
- Interface text, labels and messages now use normal sentence case
- A home page shows recent pages, a live overview and how to get started
- Split panes get a tab bar to switch, rename and close them
- A compact page setting tightens the header and drops the space below
- Panes get a settings menu, resize handles and side scrolling when crowded
- Pages keep their own settings, like editable and full width, apart from system ones
- Open several pages side by side in one tab, each running on its own
- Watch live runs, workers and planes from their own sidebar pages
- Tests split per package, with shared helpers in one place
- One example opens a space with the bundled extensions and nothing else
- A page opened before it finishes being created still comes up
- Resize the sidebar, and cell controls show on hover and stay in view
- A cell finishing no longer breaks drawing for the other cells on its page
- Every cell renders the same way, and / inserts any registered snippet
- Publish nuverse on its own tag so the extensions ship separately
- Pick any registered snippet from the / menu
- An open page runs every cell as soon as you land on it, even after a restart
- Ship apps and snippets as nuverse, a separate package found on install
- Run a cell the moment it is added to an open page, and stop it when removed
- Forget old browser tabs on open, and give the web example prose and program cells
- Open a space from one call or the command line, with extensions found on install
- Serve the browser from a device that tracks tabs and never runs planes
- Start, restart, reload and route planes through ordinary services on workers
- Run cells on workers through one kernel that records, stops and reaps every run
- Add the operations every part of a space is built from
- Store planes, cells and runs apart, and let a program declare its own typed state
- Clear the v3 source out of the way for the v4 rewrite

## 0.3.1 — 2026-09-23

- Opening a page no longer slows down with each extra cell on it
- Navigating away clears the old page at once instead of blinking through it
- Keep workers ready in advance, so opening a plane no longer waits for one to start
- Draw a page without a web server loaded behind it, so it opens much sooner
- Let a chat work as long as the work takes, and stop it only when it is stuck
- Always get a way to say something else, whatever a turn drew
- Watch a chat work step by step, and never get a broken answer
- Ask a chat for something and it draws the answer and how you reply

## 0.3.0 — 2026-09-21

- Make a chat, ask it for something, and watch it work the space
- See how a job is set to run, and edit what it does in a real editor
- Keep pages and jobs in separate sidebar sections, and make either in one click
- Collapse the whole interface to one sidebar and one viewer over any plane
- A plane now says whether it draws and whether you can edit it
- Open a space in the browser and write prose and programs into a plane's cells
- Boot a browser tab with the chrome it holds before anything is drawn
- Let a cell draw on a browser connection, and let a driver say which planes are up
- Run a space of planes and cells, each cell with its own restart policy
- Clear the v0.2 source out of the way for the v0.3 rewrite

## 0.2.1 — 2026-09-17

- Open a page on quiet air and its own name instead of decoration
- Type where you want a block instead of choosing what to make first
- Adding or deleting a block now leaves every other block on the page running
- Hovering a page block now reveals only that block's controls, and they hide again
- Slow the block controls' tooltips so passing over them says nothing
- Wipe a block's ui before it reruns, so its refs stop duplicating
- Give every block the same hover chrome: insert, drag, copy, code and status
- Follow nu 0.5.0's import split so apps and snippets keep resolving the fabrics

## 0.2.0 — 2026-09-15

- Root a snippet's refs under its own block, so an author never says where
- Hand a snippet the page and section ids in place of a namespace string
- Key a section's scratch kv by id, so one block can name another
- Delete the mount walk and the fields round trip the browser read blocks from
- Declare screens as slots and boot the browser with writes rather than an envelope
- Add the agent sidebar: a nuagent run on Space.agent, a conversation on Space.chat, and a ChatRef pinned on the shell

## 0.1.1 — 2026-09-14

- Depend on nucore and nustd[all]: a space reaches most fabrics, so picking extras only defers the ImportError
- Resolve ui-kit from the registry and drop the sibling-checkout aliases

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
