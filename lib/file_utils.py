"""Helpers for materializing FileStacks and collecting fcc_tools outputs."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
from pathlib import Path

from simstack.models.files import FileStack

logger = logging.getLogger(__name__)


def command_string(args: list[str]) -> str:
    """Shell-escape a CLI argv list for ``node_runner.subprocess``."""
    return " ".join(shlex.quote(part) for part in args)


def materialize_file_stack(
    file_stack: FileStack,
    *,
    local_dir: Path | None = None,
    preferred_name: str | None = None,
) -> tuple[Path, Path | None]:
    """
    Ensure ``file_stack`` exists under ``local_dir`` (default: cwd).

    Returns ``(path_in_cwd, cleanup_path_or_none)``.
    """
    cwd = Path.cwd() if local_dir is None else Path(local_dir)
    local_file = Path(file_stack.get(local_dir=cwd))
    target_name = preferred_name or local_file.name
    target = cwd / target_name

    if local_file.resolve() == target.resolve():
        return target, None

    if target.exists():
        try:
            if os.path.samefile(local_file, target):
                return target, None
        except OSError:
            pass

    shutil.copy2(local_file, target)
    return target, target


def collect_outputs(
    node_runner,
    patterns: list[str],
    *,
    required: bool = True,
) -> list[FileStack]:
    """Attach matching cwd files to ``node_runner`` as FileStacks."""
    collected: list[FileStack] = []
    for pattern in patterns:
        path = Path(pattern)
        if not path.exists():
            if required:
                raise FileNotFoundError(f"Expected output not found: {pattern}")
            continue
        stack = FileStack.from_local_file(
            str(path), in_memory=True, is_hashable=True, secure_source=True
        )
        node_runner.info_files.append(stack)
        collected.append(stack)
    return collected


def default_state_output(input_path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    return f"{input_path.stem}.fcc"


def default_eldip_output(input_path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    return f"{input_path.stem}.eldip"
