# uml-viewer-python

> **This is an add-on to [unclebob/uml-viewer](https://github.com/unclebob/uml-viewer) by Robert C. Martin ("Uncle Bob").** The viewer, including layout, arrow routing, drill-down, class cards, proposals, the Dependency Rule check, CRAP coloring and the companion mailbox, is his work, and this repo doesn't copy any of it. It adds Python language support and swaps the companion agent from Grok to [Claude Code](https://claude.com/claude-code). Read the [upstream README](https://github.com/unclebob/uml-viewer#readme) first; everything it says about navigating the viewer applies here.

The upstream viewer is fetched at run time as a Clojure git dependency pinned to commit `79cc1ef4`. It runs unmodified, and this repo only plugs into the extension points it already provides.

## What it adds

| Upstream extension point | Supplied here |
|---|---|
| `LanguageGraph` (source → classes and edges) | `umlpy scan`: Python AST. Each module is a class, each import is a dependency, and `Protocol`/`ABC` classes mark interfaces. |
| `LanguageSource` (click a member → source) | `umlpy.python-source` (Clojure): module → `.py`/`__init__.py`, plus `def`, `class` and `Class.method` lookup. |
| `.metrics/crap.edn` overlay | `umlpy metrics`: [radon](https://radon.readthedocs.io) complexity plus a coverage.py JSON report, scored with CRAP = cc² × (1 − cov)³ + cc. |
| `GROK_BIN` companion executable | `umlpy-companion`: ignores Grok's arguments and starts `claude` with Python-specific rules. |

Python maps onto the viewer like this:
- A module is a class, and dots after `:prefix` are the nesting.
- Module-level functions and `Class.method` are ops; names starting with `_` are private.
- Module-level classes are fields, typed by their base classes.
- External imports appear as ovals only when policy `:foreign` lists them.

Not supported yet: mutation testing. The M badge stays empty, and the companion says so if you ask for a mutation refresh.

## Requirements

- macOS. The upstream companion window uses Terminal.app, AppleScript and tmux.
- Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/)
- Java 21+ and the Clojure CLI: `brew install clojure/tools/clojure`. Homebrew's keg-only `openjdk` is found automatically.
- tmux
- [Claude Code](https://claude.com/claude-code) (`claude` on your `PATH`)

## Install

```bash
git clone https://github.com/voidnologo/uml-viewer-python
uv tool install -e ./uml-viewer-python     # puts umlpy and umlpy-companion on PATH
```

## Use

From the root of the Python project you want to view:

```bash
umlpy init --prefix myapp.billing      # writes .uml-viewer/policy.edn; --src if the package lives under src/
umlpy ir                               # scan + upstream IR generator → .uml-viewer/diagram.edn
umlpy metrics                          # complexity only (boxes stay uncolored)
umlpy view                             # viewer window + Claude companion in a Terminal window
```

The first `umlpy view` downloads the upstream viewer and Quil, and macOS asks you to allow `java` to control Terminal and System Events. The canvas says *Waiting for agent* until the companion regenerates the diagram and sends `:display`.

`init` adds `.uml-viewer/`, `.metrics/` and `uml-viewer-log.txt` to `.git/info/exclude`, so the project's `.gitignore` is untouched.

### CRAP coloring

Give the policy the command that produces a coverage.py JSON report:

```edn
:coverage {:command "pytest tests/billing --cov=myapp/billing --cov-report=json:.metrics/coverage.json"
           :json ".metrics/coverage.json"}
```

Then `umlpy metrics --run-tests`, or right-click → **Refresh CRAP** in the viewer. Functions in files the test run never imported count as 0% covered.

### Viewer basics

These come from upstream; see its README for the full list.

| Action | Keys |
|---|---|
| Zoom in / out / reset | Ctrl = / Ctrl − / Ctrl 0 |
| Pan | scroll; Shift-scroll or ← → for horizontal |
| Open a component / go up | double-click / Esc |
| Class card → source | double-click a module, click a member |
| Fewer arrows | **Declutter** in the inspector |

### The companion

The Terminal window is a Claude Code session in this project with rules in [`src/umlpy/companion_rules.md`](src/umlpy/companion_rules.md). Ask it things like:
- "set levels so `core` is innermost"
- "add `sqlalchemy` as foreign"
- "propose grouping these modules by the Common Closure Principle"
- "make the code match this proposal"

Viewer actions (Regen, Refresh CRAP, Omit, selecting a proposal) reach it as mail.

It starts with `--permission-mode acceptEdits --allowedTools "Bash(umlpy:*)"`: file edits and `umlpy` commands run without asking, and any other shell command prompts in its window. To change that, put replacement flags in `.uml-viewer/claude-args`, for example `--permission-mode plan`.

## Commands

| Command | Does |
|---|---|
| `umlpy init --prefix PKG [--src DIR]` | Hierarchical policy with `:order` from the real top-level segments |
| `umlpy ir [--display]` | Sync `:order` with the tree (keeps proposals, levels and omit), scan, generate; `--display` tells the viewer to show it |
| `umlpy metrics [--coverage-json F \| --run-tests]` | Write `.metrics/crap.edn` |
| `umlpy mail pop` / `umlpy mail send OP k=v…` | Companion side of the mailbox |
| `umlpy view [--restart]` | Launch the viewer; `--restart` is for the companion recycling the window |
| `umlpy scan` | Print the scanned facts (debugging) |

## Development

```bash
uv sync
uv run pytest
```

## License

MIT, see [LICENSE](LICENSE). This covers the code in this repository only. [unclebob/uml-viewer](https://github.com/unclebob/uml-viewer) is a separate project with its own terms; it is fetched from its own repository at run time, not redistributed here.
