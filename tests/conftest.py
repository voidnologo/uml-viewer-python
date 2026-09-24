import textwrap
from pathlib import Path

import pytest


def write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body))
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A small package `app.core` with nested modules, relative imports, and a Protocol."""
    write(tmp_path, "app/__init__.py", "")
    write(tmp_path, "app/core/__init__.py", '"""core root."""\nimport app.core.helpers\n')
    write(
        tmp_path,
        "app/core/ports.py",
        """
        from typing import Protocol


        class Store(Protocol):
            def get(self, key: str) -> str: ...
        """,
    )
    write(
        tmp_path,
        "app/core/rules/engine.py",
        """
        from typing import TYPE_CHECKING

        import sqlalchemy.orm
        from ..ports import Store
        from app.core import helpers
        from app.other import thing

        if TYPE_CHECKING:
            from app.core.rules import compiler


        class MemoryStore(Store):
            def get(self, key: str) -> str:
                return key

            def _cache(self):
                return None


        def run(x):
            if x:
                return 1
            return 2


        def _private():
            from . import compiler as late
            return late
        """,
    )
    write(tmp_path, "app/core/rules/__init__.py", "")
    write(tmp_path, "app/core/rules/compiler.py", "def compile_rule(\n    rule,\n) -> str:\n    return rule\n\n\nVALUE = 1\n")
    write(tmp_path, "app/core/helpers.py", "def helper():\n    return 1\n")
    return tmp_path
