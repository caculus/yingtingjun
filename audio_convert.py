#!/usr/bin/env python3
"""Convert any supported audio to 16 kHz mono PCM WAV (afconvert / ffmpeg / soundfile)."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

TARGET_SR = 16000
TARGET_CHANNELS = 1


def find_afconvert_bin() -> Path | None:
    path = Path("/usr/bin/afconvert")
    return path if path.is_file() else None


def find_ffmpeg_bin(
    *,
    env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    which: Callable[[str], str | None] | None = None,
) -> Path | None:
    """Look up ffmpeg: YTJ_FFMPEG / FFMPEG_BIN → repo bin/ → PATH → common Windows installs."""
    env = os.environ if env is None else env
    for key in ("YTJ_FFMPEG", "FFMPEG_BIN"):
        raw = str(env.get(key) or "").strip()
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return candidate

    root = repo_root if repo_root is not None else Path(__file__).resolve().parent
    for base in (root, root.parent):
        for name in ("ffmpeg.exe", "ffmpeg"):
            candidate = base / "bin" / name
            if candidate.is_file():
                return candidate

    which_fn = shutil.which if which is None else which
    found = which_fn("ffmpeg")
    if found:
        return Path(found)

    return _find_ffmpeg_common_windows(env)


def _find_ffmpeg_common_windows(env: Mapping[str, str]) -> Path | None:
    """winget / scoop / Program Files — covers serve_player started before PATH refresh."""
    local = str(env.get("LOCALAPPDATA") or "").strip()
    home = str(env.get("USERPROFILE") or "").strip()
    program_files = str(env.get("ProgramFiles") or r"C:\Program Files").strip()
    program_files_x86 = str(env.get("ProgramFiles(x86)") or r"C:\Program Files (x86)").strip()

    candidates: list[Path] = []
    if local:
        candidates.append(Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
        packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            for pkg in sorted(packages.glob("Gyan.FFmpeg*"), reverse=True):
                candidates.extend(sorted(pkg.glob("**/bin/ffmpeg.exe"), reverse=True))
    if home:
        candidates.append(Path(home) / "scoop" / "shims" / "ffmpeg.exe")
        candidates.append(Path(home) / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe")
    for base in (program_files, program_files_x86):
        if base:
            candidates.append(Path(base) / "ffmpeg" / "bin" / "ffmpeg.exe")
    candidates.append(Path(r"C:\ffmpeg\bin\ffmpeg.exe"))

    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def build_afconvert_cmd(afconvert: Path, src: Path, dest: Path) -> list[str]:
    return [
        str(afconvert),
        "-f",
        "WAVE",
        "-d",
        f"LEI16@{TARGET_SR}",
        "-c",
        str(TARGET_CHANNELS),
        str(src),
        str(dest),
    ]


def build_ffmpeg_cmd(ffmpeg: Path, src: Path, dest: Path) -> list[str]:
    return [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-ac",
        str(TARGET_CHANNELS),
        "-ar",
        str(TARGET_SR),
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]


def try_copy_16k_mono_wav(src: Path, dest: Path) -> bool:
    """If src is already 16 kHz WAV, rewrite as mono PCM16. False = need a converter."""
    if src.suffix.lower() != ".wav":
        return False
    try:
        import soundfile as sf

        audio, sr = sf.read(str(src), always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if int(sr) != TARGET_SR:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dest), audio, TARGET_SR, subtype="PCM_16")
        return True
    except Exception:
        return False


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except TypeError:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _run_converter(cmd: list[str], dest: Path, run: Callable) -> None:
    try:
        proc = run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        _unlink_quiet(dest)
        err = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(
            f"轉檔失敗（{' '.join(cmd[:2])}）：{err[-800:]}"
        ) from exc
    except FileNotFoundError as exc:
        _unlink_quiet(dest)
        raise RuntimeError(f"找不到轉檔程式：{cmd[0]}") from exc
    if getattr(proc, "returncode", 0) not in (0, None):
        _unlink_quiet(dest)
        raise RuntimeError(f"轉檔失敗：exit={proc.returncode}")


def convert_to_work_wav(
    src: Path,
    dest: Path,
    *,
    ffmpeg: Path | None = None,
    afconvert: Path | None = None,
    run: Callable = subprocess.run,
    soundfile_fallback: Callable[[Path, Path], None] | None = None,
) -> str:
    """Write 16 kHz mono WAV to dest. Returns converter id: wav|afconvert|ffmpeg|soundfile."""
    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dest.resolve():
        return "reuse"

    if try_copy_16k_mono_wav(src, dest):
        return "wav"

    if afconvert is not None:
        _run_converter(build_afconvert_cmd(afconvert, src, dest), dest, run)
        return "afconvert"

    if ffmpeg is not None:
        _run_converter(build_ffmpeg_cmd(ffmpeg, src, dest), dest, run)
        return "ffmpeg"

    if soundfile_fallback is not None:
        try:
            soundfile_fallback(src, dest)
            return "soundfile"
        except Exception as exc:
            _unlink_quiet(dest)
            raise RuntimeError(
                "無法轉成 16 kHz WAV。請安裝 ffmpeg 並加入 PATH，"
                "或設 YTJ_FFMPEG / FFMPEG_BIN，或把 ffmpeg 放到專案 bin/。"
                f" soundfile 後備也失敗：{exc}"
            ) from exc

    raise RuntimeError(
        "無法轉成 16 kHz WAV：找不到 afconvert / ffmpeg，也沒有 soundfile 後備。"
        "請安裝 ffmpeg（Windows: winget install Gyan.FFmpeg）並加入 PATH，"
        "或設環境變數 YTJ_FFMPEG，或把 ffmpeg.exe 放到專案 bin/。"
    )
