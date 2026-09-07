"""Register ``py`` for Echo4 injects when unrealsdk did not ship it.

Echo4 historically pastes ``py import Squ1ggsBoostingTools...``. Some BL4 SDK
builds only expose the UE console (``ulm`` works) and report
``Command not recognized: py ...``. This shim restores ``py <code>``.
"""

from __future__ import annotations

import argparse

from mods_base import command
from unrealsdk import logging

_PREFIX = "[SQBT py]"


@command(
    "py",
    description="Execute Python (Echo4 / SDK console bridge). Usage: py print(1)",
)
def _cmd_py(args: argparse.Namespace) -> None:
    parts = list(getattr(args, "parts", None) or [])
    code = " ".join(str(p) for p in parts).strip()
    if not code:
        # Some mods_base builds put the remainder on .arg / .args / .text
        for attr in ("arg", "args", "text", "raw", "line"):
            raw = getattr(args, attr, None)
            if raw is None:
                continue
            if isinstance(raw, (list, tuple)):
                code = " ".join(str(x) for x in raw).strip()
            else:
                code = str(raw).strip()
            if code:
                break
    if not code:
        logging.info(f"{_PREFIX} Usage: py <python code>")
        return
    try:
        try:
            result = eval(compile(code, "<echo4-py>", "eval"), {"__builtins__": __builtins__}, {})
            if result is not None:
                logging.info(f"{_PREFIX} {result!r}")
        except SyntaxError:
            exec(compile(code, "<echo4-py>", "exec"), {"__name__": "__main__", "__builtins__": __builtins__})
    except Exception as exc:
        logging.error(f"{_PREFIX} {type(exc).__name__}: {exc}")
