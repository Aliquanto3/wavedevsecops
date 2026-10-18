"""Routes d'un espace : état, flux SSE et intentions (AD-17).

- `GET /api/ws/<workspace_id>/state` : état courant (`boot_id`, `seq`, `epoch`, état, projection) ;
- `GET /api/ws/<workspace_id>/events` : flux SSE, `id = <boot_id>:<seq>`, reprise par
  `Last-Event-ID` (ou `?last_event_id=` à la première connexion) ;
- `POST /api/ws/<workspace_id>/<intent>` : 202 `{op_id}` ; refus en 409 avec `reason_text`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from wavedevsecops.contracts import AppError
from wavedevsecops.engine import (
    INTENTS,
    InvalidIntent,
    OperationRefused,
    UnknownIntent,
    WorkspaceEngine,
    WorkspaceManager,
    WorkspaceNotFound,
    build_operation,
)
from wavedevsecops.events import Envelope

log = logging.getLogger("wavedevsecops")
WAIT_STEP_S = 1.0
"""Attente maximale d'un événement avant de revérifier l'arrêt et le maintien du flux."""


def _refusal(status: int, reason_text: str) -> JSONResponse:
    return JSONResponse({"reason_text": reason_text}, status_code=status)


class _Refused(Exception):
    def __init__(self, response: Response) -> None:
        self.response = response


async def _engine(manager: WorkspaceManager, workspace_id: str) -> WorkspaceEngine:
    try:
        return await asyncio.to_thread(manager.get, workspace_id)
    except WorkspaceNotFound as missing:
        raise _Refused(_refusal(404, f"{missing.cause_text} {missing.action_text}")) from None
    except OperationRefused as refused:
        raise _Refused(_refusal(409, refused.reason_text)) from None
    except AppError as error:
        raise _Refused(_refusal(409, f"{error.cause_text} {error.action_text}")) from None


def install_workspace_routes(app: FastAPI, manager: WorkspaceManager) -> None:
    heartbeat_s = manager.settings.sse_heartbeat_s

    @app.get("/api/ws/{workspace_id}/state")
    async def ws_state(workspace_id: str) -> Response:
        try:
            engine = await _engine(manager, workspace_id)
        except _Refused as refused:
            return refused.response
        return JSONResponse(engine.snapshot())

    @app.get("/api/ws/{workspace_id}/events")
    async def ws_events(workspace_id: str, request: Request) -> Response:
        try:
            engine = await _engine(manager, workspace_id)
        except _Refused as refused:
            return refused.response
        journal = manager.events(workspace_id)
        last_event_id = request.headers.get("last-event-id") or request.query_params.get(
            "last_event_id"
        )
        loop = asyncio.get_running_loop()
        inbox: asyncio.Queue[Envelope] = asyncio.Queue()

        def push(envelope: Envelope) -> None:
            loop.call_soon_threadsafe(inbox.put_nowait, envelope)

        missed, detach = journal.attach(last_event_id, push)

        async def stream() -> AsyncIterator[str]:
            try:
                yield "retry: 2000\n\n"
                if missed is None:
                    reason = journal.resync_reason(last_event_id)
                    yield journal.resync_envelope(reason, epoch=engine.epoch).to_sse()
                else:
                    for envelope in missed:
                        yield envelope.to_sse()
                beat = time.monotonic()
                while not manager.closed:
                    try:
                        envelope = await asyncio.wait_for(inbox.get(), timeout=WAIT_STEP_S)
                    except TimeoutError:
                        if time.monotonic() - beat >= heartbeat_s:
                            beat = time.monotonic()
                            yield ": keepalive\n\n"
                        continue
                    yield envelope.to_sse()
            finally:
                detach()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream; charset=utf-8",
            headers={"X-Accel-Buffering": "no"},
        )

    @app.post("/api/ws/{workspace_id}/{intent}")
    async def ws_intent(workspace_id: str, intent: str, request: Request) -> Response:
        if intent not in INTENTS:
            return _refusal(404, UnknownIntent(f"L'action « {intent} » n'existe pas.").reason_text)
        raw = await request.body()
        try:
            body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except UnicodeDecodeError, json.JSONDecodeError:
            return _refusal(
                422, "L'action a été envoyée avec des données illisibles. Rechargez la page."
            )
        try:
            engine = await _engine(manager, workspace_id)
        except _Refused as refused:
            return refused.response
        try:
            op = build_operation(engine, intent, body)
            engine.submit(op)
        except UnknownIntent as unknown:
            return _refusal(404, unknown.reason_text)
        except InvalidIntent as invalid:
            return _refusal(422, invalid.reason_text)
        except OperationRefused as refused:
            return _refusal(409, refused.reason_text)
        except AppError as error:
            return _refusal(409, f"{error.cause_text} {error.action_text}")
        return JSONResponse({"op_id": op.op_id, "workspace_id": workspace_id}, status_code=202)
