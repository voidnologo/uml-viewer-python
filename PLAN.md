# uml-viewer-python — Plan

Python support for [unclebob/uml-viewer](https://github.com/unclebob/uml-viewer), with Claude Code as the companion agent in place of Grok. The viewer itself stays upstream and unmodified; this repo adds a Python scanner, a Python source extractor, a metrics producer, and a launcher.

## Goal

Point the viewer at a Python project (first target: one package of a large FastAPI/SQLAlchemy service), see its module tree as UML with CRAP coloring, drill down to source, and talk to a Claude companion that can regenerate the diagram, build proposals, and edit code.

## How upstream is extended without forking

| Upstream seam | What this repo supplies |
|---|---|
| `LanguageGraph` protocol (`scan` → `{:classes :edges}`) | `umlpy scan` (Python AST) writes the facts to EDN; a Clojure `PythonGraph` reads that file and the upstream IR generator applies the policy (proposals, levels, violations stay upstream logic). |
| `LanguageSource` protocol (click-to-source) | Clojure `PythonSource`: module path → `.py` / `__init__.py`, `def` / `class` / `Class.method` line lookup. |
| `.metrics/crap.edn` overlay | `umlpy metrics`: radon cyclomatic complexity + coverage.py JSON → crap4clj-format entries (`crap = cc² × (1 − cov)³ + cc`). |
| Main passes the source impl to `core/start!` | Own Clojure main (`umlpy.viewer`) registers the Python impls and calls upstream `core/start!`. |
| `GROK_BIN` env var picks the companion executable | `umlpy-companion` wrapper: drops Grok's flags and Clojure rules, execs `claude` with Python rules and launch prompt. tmux session, Terminal window, mailbox, respawn all stay upstream. |

Upstream is pulled as a Clojure git dep pinned by SHA (`79cc1ef4`); nothing is cloned into the examined project.

## Python → UML mapping

- A module is a class; a package's `__init__.py` is the module for that package; dots after `:prefix` are the tree.
- Members: module-level functions and `Class.method` as ops (`_name` is private); module-level classes as fields typed by their bases.
- Edges: every project import (`import`, `from … import`, relative, function-local, `TYPE_CHECKING`) is a `:dependency` on the imported module. External imports are foreign classes, shown only if listed in policy `:foreign`.
- A module that defines a `Protocol` / `ABC` class gets `:stereotype :interface`; subclassing such a class from another module adds an `:implements` edge.

## CLI

| Command | Does |
|---|---|
| `umlpy init --src . --prefix pkg.sub` | Write `.uml-viewer/policy.edn` (hierarchical, `:order` from real top segments). |
| `umlpy ir` | Sync `:order` with the tree (keeps proposals, levels, omit), scan, run the upstream IR generator, write the diagram EDN. |
| `umlpy metrics [--coverage-json F]` | Write `.metrics/crap.edn`. Without coverage: complexity only, no CRAP color. |
| `umlpy mail pop` / `umlpy mail send OP [k=v…]` | Companion reads/writes mailbox queues without hand-editing EDN. |
| `umlpy view [--restart]` | Launch the viewer JVM in the background (log to `uml-viewer-log.txt`); fresh start spawns the Claude companion. |

## Companion

`claude --permission-mode acceptEdits --allowedTools "Bash(umlpy:*)" --append-system-prompt <rules> <launch prompt>`. Other shell commands prompt in the companion's Terminal window. `UMLPY_CLAUDE_ARGS` replaces the permission flags if you want something else.

## Out of scope (v1)

- Mutation testing: right-click Refresh Mutation reaches the companion, which reports it is unsupported.
- Any change to the upstream viewer.

## Risks

- tmux wake-up sends text + `C-m` + `C-j`; `C-j` in Claude's input may leave a stray newline. Verify; mitigate in rules if needed.
- Viewer writes the policy file (new/rename proposal); the Python EDN round-trip must preserve symbols, vectors, and vector map keys.
- Coverage on a database-backed project runs its real test suite; run it in a separate worktree against a separately named test DB so a shared local test DB is untouched.

## Steps

1. Scaffold (uv, pytest), EDN reader/writer.
2. Scanner + tests.
3. Metrics + tests.
4. Policy sync, mailbox + tests.
5. Clojure glue (graph, source, mains) + launcher + companion wrapper.
6. Real-project trial in a worktree: init, ir, metrics, view; verify drill-down, click-to-source, companion round trip.
7. README walkthrough.
