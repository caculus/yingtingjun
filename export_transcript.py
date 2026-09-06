"""Export bilingual transcript to .txt / .md / .html."""

from __future__ import annotations

import html
import io
import zipfile
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_EXPORT_FORMATS = ("txt", "md", "html")


def format_export_ts(seconds: float) -> str:
    """Match player-friendly mm:ss (drop ms) for export headers."""
    total = max(0, int(round(float(seconds))))
    mm, ss = divmod(total, 60)
    hh, mm = divmod(mm, 60)
    if hh:
        return f"{hh:d}:{mm:02d}:{ss:02d}"
    return f"{mm:02d}:{ss:02d}"


def _speaker(turn: dict[str, Any]) -> str:
    return str(turn.get("speaker") or "SPEAKER").strip() or "SPEAKER"


def _en(turn: dict[str, Any]) -> str:
    return str(turn.get("text") or "").strip()


def _zh(turn: dict[str, Any]) -> str:
    return str(turn.get("text_zh") or "").strip()


def _header(
    turn: dict[str, Any],
    *,
    include_speakers: bool = True,
    include_timestamps: bool = False,
) -> str | None:
    parts: list[str] = []
    if include_speakers:
        parts.append(_speaker(turn))
    if include_timestamps:
        start = format_export_ts(float(turn.get("start") or 0))
        end = format_export_ts(float(turn.get("end") or 0))
        parts.append(f"{start} → {end}")
    if not parts:
        return None
    return "  ".join(parts)


def normalize_export_formats(formats: Iterable[str]) -> list[str]:
    selected: list[str] = []
    for fmt in formats:
        key = str(fmt or "").strip().lower().lstrip(".")
        if key in SUPPORTED_EXPORT_FORMATS and key not in selected:
            selected.append(key)
    if not selected:
        raise ValueError("請至少選擇一種格式（txt / md / html）")
    return selected


def render_txt(
    turns: Iterable[dict[str, Any]],
    *,
    include_speakers: bool = True,
    include_timestamps: bool = False,
    title: str | None = None,
) -> str:
    lines: list[str] = []
    if title:
        lines.extend([title, ""])
    for turn in turns:
        en = _en(turn)
        zh = _zh(turn)
        if not en and not zh:
            continue
        header = _header(
            turn,
            include_speakers=include_speakers,
            include_timestamps=include_timestamps,
        )
        if header:
            lines.append(header)
        if en:
            lines.append(en)
        if zh:
            lines.append(zh)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_md(
    turns: Iterable[dict[str, Any]],
    *,
    include_speakers: bool = True,
    include_timestamps: bool = False,
    title: str | None = None,
) -> str:
    lines: list[str] = []
    heading = title or "Transcript"
    lines.extend([f"# {heading}", ""])
    lines.append(f"- Speakers: {'yes' if include_speakers else 'no'}")
    lines.append(f"- Timestamps: {'yes' if include_timestamps else 'no'}")
    lines.append("")
    lines.append("---")
    lines.append("")
    for turn in turns:
        en = _en(turn)
        zh = _zh(turn)
        if not en and not zh:
            continue
        header = _header(
            turn,
            include_speakers=include_speakers,
            include_timestamps=include_timestamps,
        )
        if header:
            lines.append(f"## {header}")
            lines.append("")
        if en:
            lines.append(en)
            lines.append("")
        if zh:
            lines.append(zh)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(
    turns: Iterable[dict[str, Any]],
    *,
    include_speakers: bool = True,
    include_timestamps: bool = False,
    title: str | None = None,
) -> str:
    heading = title or "Transcript"
    safe_title = html.escape(heading)
    blocks: list[str] = []
    for turn in turns:
        en = _en(turn)
        zh = _zh(turn)
        if not en and not zh:
            continue
        header = _header(
            turn,
            include_speakers=include_speakers,
            include_timestamps=include_timestamps,
        )
        parts = ['  <section class="turn">']
        if header:
            parts.append(f"    <h2>{html.escape(header)}</h2>")
        if en:
            parts.append(f'    <p class="en">{html.escape(en)}</p>')
        if zh:
            parts.append(f'    <p class="zh">{html.escape(zh)}</p>')
        parts.append("  </section>")
        blocks.append("\n".join(parts))

    body = "\n\n".join(blocks) if blocks else '  <p class="empty">（無內容）</p>'
    meta_bits = []
    meta_bits.append("含說話者" if include_speakers else "不含說話者")
    meta_bits.append("含時間戳" if include_timestamps else "不含時間戳")
    meta = " · ".join(meta_bits) + " · 英文 + 中文"
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f4ef;
      --ink: #1c2420;
      --muted: #5c6b63;
      --en: #24302a;
      --zh: #3d4a43;
      --line: #d9d2c6;
      --card: #fffdf9;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, "Songti TC",
        "Noto Serif CJK TC", serif;
      background: linear-gradient(180deg, #efe8dc 0%, var(--bg) 28%, #f3f0ea 100%);
      color: var(--ink);
      line-height: 1.55;
    }}
    main {{
      max-width: 44rem;
      margin: 0 auto;
      padding: 2rem 1.25rem 3rem;
    }}
    h1 {{
      margin: 0 0 0.35rem;
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: 0.01em;
    }}
    .meta {{
      margin: 0 0 1.5rem;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .turn {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 1rem 1.1rem;
      margin: 0 0 0.85rem;
    }}
    .turn h2 {{
      margin: 0 0 0.55rem;
      font-size: 0.92rem;
      font-weight: 600;
      color: var(--muted);
      font-family: ui-sans-serif, system-ui, sans-serif;
    }}
    .en {{
      margin: 0 0 0.35rem;
      color: var(--en);
      font-size: 1.05rem;
    }}
    .zh {{
      margin: 0;
      color: var(--zh);
      font-size: 1rem;
    }}
    .empty {{ color: var(--muted); }}
  </style>
</head>
<body>
<main>
  <h1>{safe_title}</h1>
  <p class="meta">{meta}</p>
{body}
</main>
</body>
</html>
"""


def render_export_texts(
    turns: list[dict[str, Any]],
    *,
    basename: str,
    formats: Iterable[str],
    include_speakers: bool = True,
    include_timestamps: bool = False,
    title: str | None = None,
) -> dict[str, str]:
    """Return mapping of filename -> text content for selected formats."""
    selected = normalize_export_formats(formats)
    title = title or basename
    out: dict[str, str] = {}
    for fmt in selected:
        if fmt == "txt":
            content = render_txt(
                turns,
                include_speakers=include_speakers,
                include_timestamps=include_timestamps,
                title=title,
            )
        elif fmt == "md":
            content = render_md(
                turns,
                include_speakers=include_speakers,
                include_timestamps=include_timestamps,
                title=title,
            )
        else:
            content = render_html(
                turns,
                include_speakers=include_speakers,
                include_timestamps=include_timestamps,
                title=title,
            )
        out[f"{basename}.{fmt}"] = content
    return out


def build_export_download(
    turns: list[dict[str, Any]],
    *,
    basename: str,
    formats: Iterable[str],
    include_speakers: bool = True,
    include_timestamps: bool = False,
    title: str | None = None,
) -> tuple[str, bytes, str]:
    """Build a browser download payload.

    Returns (download_filename, body_bytes, content_type).
    One format → that file; multiple → `{basename}.zip`.
    """
    files = render_export_texts(
        turns,
        basename=basename,
        formats=formats,
        include_speakers=include_speakers,
        include_timestamps=include_timestamps,
        title=title,
    )
    if len(files) == 1:
        name, text = next(iter(files.items()))
        body = text.encode("utf-8")
        if name.endswith(".html"):
            mime = "text/html; charset=utf-8"
        elif name.endswith(".md"):
            mime = "text/markdown; charset=utf-8"
        else:
            mime = "text/plain; charset=utf-8"
        return name, body, mime

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, text in files.items():
            zf.writestr(name, text.encode("utf-8"))
    return f"{basename}.zip", buf.getvalue(), "application/zip"


def write_export_files(
    turns: list[dict[str, Any]],
    *,
    directory: Path,
    basename: str,
    formats: Iterable[str],
    include_speakers: bool = True,
    include_timestamps: bool = False,
    title: str | None = None,
) -> list[Path]:
    """Write selected formats into directory. Returns written paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = render_export_texts(
        turns,
        basename=basename,
        formats=formats,
        include_speakers=include_speakers,
        include_timestamps=include_timestamps,
        title=title,
    )
    written: list[Path] = []
    for name, text in files.items():
        path = directory / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
