"""Seed the bundled Aesop demo lesson into uploads/ + workdir/ + output/ once."""

from __future__ import annotations

import shutil
from pathlib import Path

DEMO_STEM = "demo-aesop-charcoal-burner"
DEMO_AUDIO_NAME = f"{DEMO_STEM}.mp3"
DEMO_JSON_NAME = f"{DEMO_STEM}.json"
MARKER_NAME = ".ytj_demo_seeded"


def find_demo_dir(app_root: Path | None = None) -> Path | None:
    """Locate bundled demo/ next to serve_player (dev or packaged app)."""
    roots: list[Path] = []
    if app_root is not None:
        roots.append(Path(app_root))
    here = Path(__file__).resolve().parent
    roots.extend([here, here.parent])
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        candidate = root / "demo"
        audio = candidate / DEMO_AUDIO_NAME
        transcript = candidate / DEMO_JSON_NAME
        if audio.is_file() and transcript.is_file():
            return candidate
    return None


def demo_dest_paths(uploads: Path, workdir: Path, outdir: Path) -> tuple[Path, Path, Path]:
    return (
        uploads / DEMO_AUDIO_NAME,
        workdir / DEMO_AUDIO_NAME,
        outdir / DEMO_JSON_NAME,
    )


def demo_already_present(uploads: Path, workdir: Path, outdir: Path) -> bool:
    upload_audio, work_audio, transcript = demo_dest_paths(uploads, workdir, outdir)
    return work_audio.is_file() and transcript.is_file() and upload_audio.is_file()


def seed_demo_lesson(
    uploads: Path,
    workdir: Path,
    outdir: Path,
    *,
    app_root: Path | None = None,
    force: bool = False,
) -> dict:
    """
    Copy bundled demo into the user's study data dirs.

    Library UI lists workdir files, so the audio must exist there (and in uploads
    for rename/delete parity). Transcript goes to outdir.
    """
    demo_dir = find_demo_dir(app_root)
    if demo_dir is None:
        return {"ok": False, "seeded": False, "error": "找不到內建 demo/ 教材"}

    uploads = Path(uploads)
    workdir = Path(workdir)
    outdir = Path(outdir)
    for folder in (uploads, workdir, outdir):
        folder.mkdir(parents=True, exist_ok=True)

    marker = uploads.parent / MARKER_NAME
    upload_audio, work_audio, json_dst = demo_dest_paths(uploads, workdir, outdir)
    already = work_audio.is_file() and json_dst.is_file() and upload_audio.is_file()

    if already and marker.is_file() and not force:
        return {
            "ok": True,
            "seeded": False,
            "already_present": True,
            "stem": DEMO_STEM,
            "audio": str(work_audio),
            "transcript": str(json_dst),
        }

    if marker.is_file() and not already and not force:
        # User deleted the demo after first seed — do not recreate.
        return {
            "ok": True,
            "seeded": False,
            "already_present": False,
            "skipped": True,
            "stem": DEMO_STEM,
        }

    audio_src = demo_dir / DEMO_AUDIO_NAME
    json_src = demo_dir / DEMO_JSON_NAME
    try:
        if force or not upload_audio.is_file():
            shutil.copy2(audio_src, upload_audio)
        if force or not work_audio.is_file():
            shutil.copy2(audio_src, work_audio)
        if force or not json_dst.is_file():
            shutil.copy2(json_src, json_dst)
        marker.write_text(f"{DEMO_STEM}\n", encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "seeded": False, "error": f"無法寫入試用教材：{exc}"}

    return {
        "ok": True,
        "seeded": not already,
        "already_present": already,
        "stem": DEMO_STEM,
        "audio": str(work_audio),
        "transcript": str(json_dst),
    }
