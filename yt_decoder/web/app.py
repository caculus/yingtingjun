"""Starlette app for yt-decoder serve (Proposal A / A1)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from yt_decoder import __version__
from yt_decoder.constants import DEFAULT_MAX_DURATION_SEC, DEFAULT_MODE
from yt_decoder.util import default_outdir
from yt_decoder.web.jobs import JobManager

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    *,
    outdir: Path | None = None,
    yingtingjun_root: Path | None = None,
) -> Starlette:
    resolved_outdir = outdir or default_outdir()
    manager = JobManager(outdir=resolved_outdir, yingtingjun_root=yingtingjun_root)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "ok": True,
                "version": __version__,
                "busy": manager.busy(),
                "outdir": str(resolved_outdir),
            }
        )

    async def config(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "outdir": str(resolved_outdir),
                "default_mode": DEFAULT_MODE,
                "max_duration_sec": DEFAULT_MAX_DURATION_SEC,
                "yingtingjun": str(yingtingjun_root) if yingtingjun_root else None,
                "version": __version__,
            }
        )

    async def start_import(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": "invalid_json", "message": "需要 JSON body"}, status_code=400)

        url = (body.get("url") or "").strip()
        if not url:
            return JSONResponse({"ok": False, "error": "invalid_url", "message": "請提供 YouTube URL"}, status_code=400)

        mode = (body.get("mode") or DEFAULT_MODE).strip()
        if mode not in {"auto", "caption", "whisper"}:
            return JSONResponse({"ok": False, "error": "invalid_mode", "message": "mode 無效"}, status_code=400)

        skip_translate = bool(body.get("skip_translate"))
        max_duration = int(body.get("max_duration_sec") or DEFAULT_MAX_DURATION_SEC)

        try:
            job = manager.start(
                url,
                mode=mode,
                skip_translate=skip_translate,
                max_duration_sec=max_duration,
            )
        except RuntimeError:
            return JSONResponse(
                {"ok": False, "error": "busy", "message": "匯入進行中，請稍候再試"},
                status_code=409,
            )
        except ValueError as exc:
            return JSONResponse(
                {"ok": False, "error": "invalid_url", "message": str(exc)},
                status_code=400,
            )

        return JSONResponse({"ok": True, "job_id": job.id, "url": job.url})

    async def job_events(request: Request) -> StreamingResponse:
        job_id = request.path_params["job_id"]
        job = manager.get(job_id)
        if job is None:
            return JSONResponse({"ok": False, "error": "not_found", "message": "找不到 job"}, status_code=404)

        async def event_stream():
            while True:
                try:
                    event = await asyncio.to_thread(job.events.get, True, 1.0)
                except Exception:
                    # queue.Empty after timeout
                    if await request.is_disconnected():
                        break
                    if job.status in {"done", "error"} and job.events.empty():
                        break
                    yield f"event: ping\ndata: {{}}\n\n"
                    continue

                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if event.get("type") == "end":
                    break

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    routes = [
        Route("/api/health", health),
        Route("/api/config", config),
        Route("/api/import", start_import, methods=["POST"]),
        Route("/api/import/{job_id}/events", job_events),
        Mount("/", app=StaticFiles(directory=str(STATIC_DIR), html=True), name="static"),
    ]
    return Starlette(routes=routes)


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    outdir: Path | None = None,
    yingtingjun_root: Path | None = None,
    open_browser: bool = True,
) -> None:
    import webbrowser

    import uvicorn

    app = create_app(outdir=outdir, yingtingjun_root=yingtingjun_root)
    url = f"http://{host}:{port}/"
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")
