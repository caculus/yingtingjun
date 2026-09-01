"""Import option and result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImportOptions:
    output_dir: Path
    workdir: Path
    uploads_dir: Path
    mode: str = "auto"
    caption_pref: str = "manual_first"
    skip_translate: bool = False
    max_duration_sec: int = 2700
    yingtingjun_root: Path | None = None
    preferred_stem: str | None = None

    @classmethod
    def from_data_root(cls, root: Path, **kwargs) -> ImportOptions:
        """Layout used by standalone yt-decoder CLI (data/output, data/workdir, …)."""
        return cls(
            output_dir=root / "output",
            workdir=root / "workdir",
            uploads_dir=root / "uploads",
            **kwargs,
        )

    @classmethod
    def from_yingtingjun(
        cls,
        *,
        output_dir: Path,
        workdir: Path,
        uploads_dir: Path,
        **kwargs,
    ) -> ImportOptions:
        """Layout used by yingtingjun serve_player (separate outdir/workdir/uploads)."""
        return cls(
            output_dir=output_dir,
            workdir=workdir,
            uploads_dir=uploads_dir,
            **kwargs,
        )


@dataclass
class ImportResult:
    stem: str
    json_path: Path
    audio_path: Path
    caption_kind: str
    turns_count: int
