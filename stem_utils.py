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


class StemCollisionError(StemError):
    """Target stem already exists or rename plan conflicts."""


_RECORDING_SUFFIXES = (
    ".json.bak-range",
    ".json.range-meta.json",
    ".whisper.json",
    ".turns.json",
    ".json",
    ".md",
    ".txt",
    ".srt",
)


def recording_stem_from_filename(name: str) -> str | None:
    """Map a data-dir filename back to its recording stem."""
    if name.endswith(".work.wav"):
        return name[: -len(".work.wav")]
    for suffix in _RECORDING_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    if "." in name:
        return Path(name).stem
    return name or None


def media_stem(path: Path) -> str:
    """meeting.work.wav → meeting; lesson.json → lesson."""
    key = recording_stem_from_filename(path.name)
    if key is not None:
        return key
    return path.stem


def path_matches_stem(path: Path, stem: str) -> bool:
    return recording_stem_from_filename(path.name) == stem


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


def renamed_file_path(path: Path, old_stem: str, new_stem: str) -> Path:
    """Compute destination path when migrating *old_stem* → *new_stem*."""
    current = recording_stem_from_filename(path.name)
    if current != old_stem:
        raise StemError(f"無法重新命名：{path.name}")
    name = path.name
    if name.endswith(".work.wav"):
        return path.with_name(f"{new_stem}.work.wav")
    for suffix in _RECORDING_SUFFIXES:
        if name.endswith(suffix):
            return path.with_name(f"{new_stem}{suffix}")
    return path.with_name(f"{new_stem}{path.suffix}")


def build_stem_rename_plan(
    files: list[Path],
    old_stem: str,
    new_stem: str,
) -> list[tuple[Path, Path]]:
    if old_stem == new_stem:
        raise StemError("名稱未變更")
    if not files:
        raise StemError("找不到可重新命名的檔案")

    plan: list[tuple[Path, Path]] = []
    destinations: set[str] = set()
    sources = {str(path.resolve()) for path in files}

    for src in files:
        dst = renamed_file_path(src, old_stem, new_stem)
        dst_key = str(dst.resolve())
        if dst_key in destinations:
            raise StemCollisionError(f"重新命名會造成衝突：{dst.name}")
        if dst.exists() and dst_key not in sources:
            raise StemCollisionError(f"「{new_stem}」已存在，請換一個名稱")
        destinations.add(dst_key)
        plan.append((src, dst))
    return plan


def execute_stem_rename(plan: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    """Rename files in *plan*; rollback on failure."""
    done: list[tuple[Path, Path]] = []
    try:
        for src, dst in plan:
            if src.resolve() == dst.resolve():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            done.append((src, dst))
    except OSError as exc:
        for src, dst in reversed(done):
            try:
                if dst.exists():
                    dst.rename(src)
            except OSError:
                pass
        raise StemError(f"重新命名失敗：{exc}") from exc
    return done
