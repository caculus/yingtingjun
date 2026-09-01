"""CLI entry: probe / import / serve."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from yt_decoder import __version__
from yt_decoder.constants import DEFAULT_MAX_DURATION_SEC, DEFAULT_MODE
from yt_decoder.errors import ProbeError
from yt_decoder.import_video import run_import
from yt_decoder.probe import probe_url
from yt_decoder.types import ImportOptions
from yt_decoder.util import UrlError, default_outdir, normalize_youtube_url

DEFAULT_SERVE_PORT = 8766


def _add_yingtingjun_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--yingtingjun",
        type=Path,
        default=None,
        help="英聽君 repo 路徑（或設 YT_DECODER_YINGTINGJUN）",
    )


def _resolve_yingtingjun_arg(path: Path | None) -> Path | None:
    if path is not None:
        os.environ["YT_DECODER_YINGTINGJUN"] = str(path.expanduser())
        return path.expanduser()
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-decoder",
        description="YouTube URL → Yingtingjun-compatible bilingual transcript + audio",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="Probe video metadata and caption tracks")
    probe.add_argument("url", help="YouTube video URL")
    probe.add_argument(
        "--max-duration",
        type=int,
        default=DEFAULT_MAX_DURATION_SEC,
        help=f"Max duration in seconds (default: {DEFAULT_MAX_DURATION_SEC})",
    )

    imp = sub.add_parser("import", help="Import URL → audio + JSON")
    imp.add_argument("url", help="YouTube video URL")
    imp.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Output root (default: ~/Documents/Yingtingjun/data)",
    )
    imp.add_argument(
        "--mode",
        choices=["auto", "caption", "whisper"],
        default=DEFAULT_MODE,
        help="Import mode: auto=caption first, whisper fallback (default: auto)",
    )
    imp.add_argument(
        "--caption",
        choices=["manual_first", "auto_ok", "manual_only"],
        default="manual_first",
        help="Caption track preference",
    )
    imp.add_argument(
        "--skip-translate",
        action="store_true",
        help="Skip Chinese translation",
    )
    imp.add_argument(
        "--download-video",
        action="store_true",
        help="Also download low-res mp4 (M3b+)",
    )
    imp.add_argument(
        "--max-duration",
        type=int,
        default=DEFAULT_MAX_DURATION_SEC,
        help=f"Max duration in seconds (default: {DEFAULT_MAX_DURATION_SEC})",
    )
    _add_yingtingjun_arg(imp)

    serve = sub.add_parser("serve", help="Open minimal local import UI (Proposal A)")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVE_PORT,
        help=f"Port (default: {DEFAULT_SERVE_PORT})",
    )
    serve.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Output root (default: ~/Documents/Yingtingjun/data)",
    )
    serve.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open browser automatically",
    )
    _add_yingtingjun_arg(serve)
    return parser


def cmd_probe(args: argparse.Namespace) -> int:
    try:
        url = normalize_youtube_url(args.url)
    except UrlError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": str(exc)}), file=sys.stderr)
        return 1

    try:
        result = probe_url(url, max_duration_sec=args.max_duration)
    except ProbeError as exc:
        print(
            json.dumps({"ok": False, "error": exc.code, "message": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    if args.download_video:
        print("錯誤：--download-video 尚未實作（M3b+）", file=sys.stderr)
        return 2

    try:
        url = normalize_youtube_url(args.url)
    except UrlError as exc:
        print(f"錯誤 [{exc.code}]: {exc}", file=sys.stderr)
        return 1

    outdir: Path = args.outdir or default_outdir()
    options = ImportOptions.from_data_root(
        outdir,
        mode=args.mode,
        caption_pref=args.caption,
        skip_translate=args.skip_translate,
        max_duration_sec=args.max_duration,
        yingtingjun_root=_resolve_yingtingjun_arg(args.yingtingjun),
    )

    try:
        run_import(url, options)
    except ProbeError as exc:
        print(f"錯誤 [{exc.code}]: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"錯誤: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        from yt_decoder.web.app import run_server
    except ImportError:
        print(
            "錯誤：缺少 web 依賴。請執行：pip install -e \".[web]\"",
            file=sys.stderr,
        )
        return 2

    run_server(
        host=args.host,
        port=args.port,
        outdir=args.outdir or default_outdir(),
        yingtingjun_root=_resolve_yingtingjun_arg(args.yingtingjun),
        open_browser=not args.no_open,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "probe":
        return cmd_probe(args)
    if args.command == "import":
        return cmd_import(args)
    if args.command == "serve":
        return cmd_serve(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
