"""Run the upstream viewer and IR generator on the JVM with the Python glue on the classpath."""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from importlib import resources
from pathlib import Path

from umlpy import edn
from umlpy.edn import Symbol, kw

UPSTREAM_URL = "https://github.com/unclebob/uml-viewer.git"
UPSTREAM_SHA = "79cc1ef4e41992ecb1bb17e18f6e7e7ae11a2019"
QUIL_VERSION = "4.3.1563"
LOG_FILE = "uml-viewer-log.txt"

# Homebrew's openjdk is keg-only, so macOS's /usr/bin/java stub cannot find it.
JAVA_CANDIDATES = ("/opt/homebrew/opt/openjdk/bin/java", "/usr/local/opt/openjdk/bin/java")


class LaunchError(RuntimeError):
    pass


def clj_dir() -> Path:
    return Path(str(resources.files("umlpy") / "clj"))


def deps_edn() -> str:
    return edn.dumps(
        {
            kw("deps"): {
                Symbol("io.github.unclebob/uml-viewer"): {kw("git/url"): UPSTREAM_URL, kw("git/sha"): UPSTREAM_SHA},
                Symbol("quil/quil"): {kw("mvn/version"): QUIL_VERSION},
                Symbol("umlpy/glue"): {kw("local/root"): str(clj_dir())},
            }
        }
    )


def _java_works(cmd: str) -> bool:
    try:
        return subprocess.run([cmd, "-version"], capture_output=True).returncode == 0
    except OSError:
        return False


def java_env() -> dict[str, str]:
    """Environment with JAVA_CMD pointing at a working JVM, unless the user already chose one."""
    env = dict(os.environ)
    if env.get("JAVA_CMD") or env.get("JAVA_HOME") or _java_works("java"):
        return env
    for candidate in JAVA_CANDIDATES:
        if Path(candidate).exists() and _java_works(candidate):
            env["JAVA_CMD"] = candidate
            return env
    raise LaunchError("no Java runtime found; install one (brew install openjdk) or set JAVA_CMD")


def clojure_bin() -> str:
    found = shutil.which("clojure")
    if not found:
        raise LaunchError("Clojure CLI not found; install it with: brew install clojure/tools/clojure")
    return found


def run_ir(policy_path: Path, facts_path: Path) -> str:
    """Upstream policy application over pre-scanned facts; returns the path it wrote."""
    cmd = [clojure_bin(), "-Sdeps", deps_edn(), "-M", "-m", "umlpy.ir", str(policy_path), str(facts_path)]
    done = subprocess.run(cmd, env=java_env(), capture_output=True, text=True)
    if done.returncode != 0:
        raise LaunchError(f"IR generation failed:\n{done.stderr.strip()}")
    sys.stderr.write(done.stderr)
    return done.stdout.strip().removeprefix("Wrote ").strip()


def companion_bin() -> str:
    """The `umlpy-companion` script installed next to this interpreter's `umlpy`."""
    sibling = Path(sys.argv[0]).resolve().parent / "umlpy-companion"
    found = str(sibling) if sibling.exists() else shutil.which("umlpy-companion")
    if not found:
        raise LaunchError("umlpy-companion is not installed next to umlpy")
    return found


def viewer_env(src_root: str) -> dict[str, str]:
    env = java_env()
    bin_dir = str(Path(companion_bin()).parent)
    env["GROK_BIN"] = companion_bin()
    env["UMLPY_SRC"] = src_root
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def start_viewer(project_root: Path, diagram: str, src_root: str, restart: bool) -> int:
    """Detached viewer JVM; output appends to uml-viewer-log.txt. Returns the pid."""
    args = ["--restart", diagram] if restart else [diagram]
    cmd = [clojure_bin(), "-Sdeps", deps_edn(), "-M", "-m", "umlpy.viewer", *args]
    log_path = project_root / LOG_FILE
    with log_path.open("a") as log:
        log.write(f"----- {datetime.now():%Y-%m-%d %H:%M:%S} starting uml-viewer {' '.join(args)}\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=project_root,
            env=viewer_env(src_root),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid
