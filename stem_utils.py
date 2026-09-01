"""Stem sanitization and file grouping for import/rename."""

from __future__ import annotations

import re
from pathlib import Path

STEM_MAX_LEN = 80
_INVALID_STEM_CHARS = re.compile(r'[/\\:*?"<>|]')
_WIN_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class StemError(ValueError):
    """Invalid user-provided stem."""


def media_stem(path: Path) -> str:
    """meeting.work.wav → meeting"""
    name = path.name
    if name.endswith(".work.wav"):
        return name[: -len(".work.wav")]
    return path.stem


def path_matches_stem(path: Path, stem: str) -> bool:
    return (
        media_stem(path) == stem
        or path.stem == stem
        or path.name.startswith(stem + ".")
    )


def sanitize_stem(raw: str) -> str:
    """Normalize a user-facing recording name into a safe filesystem stem."""
    text = (raw or "").strip()
    if not text:
        raise StemError("名稱不可為空")
    text = _INVALID_STEM_CHARS.sub("-", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"-{2,}", "-", text).strip("-. ")
    if not text or text in {".", ".."}:
        raise StemError("名稱不可為空")
    if len(text) > STEM_MAX_LEN:
        text = text[:STEM_MAX_LEN].rstrip("-. ")
    if not text:
        raise StemError("名稱不可為空")
    reserved = text.split(".")[0].upper()
    if reserved in _WIN_RESERVED:
        text = f"{text}_"
    return text


def iter_files_for_stem(
    *,
    workdir: Path,
    outdir: Path,
    uploads: Path,
    notesdir: Path,
    stem: str,
) -> list[Path]:
    """Return all regular files tied to *stem* across data directories."""
    paths: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        paths.append(path)

    for directory in (workdir, outdir, uploads):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file() and path_matches_stem(path, stem):
                add(path)

    notes_path = notesdir / f"{Path(stem).name}.json"
    if notes_path.is_file():
        add(notes_path)
    return paths
