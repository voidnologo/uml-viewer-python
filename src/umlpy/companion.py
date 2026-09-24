"""`GROK_BIN` target: the viewer launches this in its tmux pane; it becomes Claude Code.

The viewer passes Grok's flags, Clojure-specific rules, and a launch prompt. All of it
is replaced with Python rules and a Python launch prompt.
"""

import os
import shlex
import shutil
import sys
from importlib import resources
from pathlib import Path

# Set in the companion's environment so `umlpy ir --display` waits for the viewer to take the command.
COMPANION_ENV = "UMLPY_COMPANION"
DEFAULT_PERMISSIONS = ["--permission-mode", "acceptEdits", "--allowedTools", "Bash(umlpy:*)"]
# Read from the project, because tmux may start the pane with the tmux server's environment, not ours.
ARGS_FILE = Path(".uml-viewer/claude-args")

LAUNCH_PROMPT = (
    "You are the uml-viewer companion for this project. Run `umlpy ir --display` now, "
    "then say in one line that the diagram is up and wait for directives."
)


def rules() -> str:
    return (resources.files("umlpy") / "companion_rules.md").read_text()


def claude_bin() -> str:
    candidates = [os.environ.get("UMLPY_CLAUDE_BIN"), shutil.which("claude"), str(Path.home() / ".local/bin/claude")]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("umlpy-companion: claude CLI not found; set UMLPY_CLAUDE_BIN")


def permission_args(project_root: Path) -> list[str]:
    args_file = project_root / ARGS_FILE
    if args_file.is_file():
        return shlex.split(args_file.read_text())
    return DEFAULT_PERMISSIONS


def command(project_root: Path) -> list[str]:
    return [
        claude_bin(),
        *permission_args(project_root),
        "--name",
        "uml-viewer companion",
        "--append-system-prompt",
        rules(),
        LAUNCH_PROMPT,
    ]


def main() -> None:
    # Grok's arguments (--yolo --trust --rules … prompt) are deliberately ignored.
    bin_dir = str(Path(sys.argv[0]).resolve().parent)
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    os.environ[COMPANION_ENV] = "1"
    cmd = command(Path.cwd())
    os.execv(cmd[0], cmd)
