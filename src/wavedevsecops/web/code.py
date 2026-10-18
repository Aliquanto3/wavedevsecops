"""Lectures de la vue Code (story 2.8, AD-2, AD-17) : fichiers, contenu d'un fichier et diff.

- `GET /api/ws/<id>/code/tree` : fichiers de l'arbre de travail ;
- `GET /api/ws/<id>/code/file?path=` : contenu et empreinte (`base_hash` de `save_file`) ;
- `GET /api/ws/<id>/code/diff?target=worktree|<sha>` : diff projeté avec ses `element_id`.

Ce sont des lectures sans essai ni file : le disque est lu par `wsfs` (chemins confinés) et git par
`gitio` (contexte interne, sans verrou). L'écriture reste l'intention `save_file`.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from wavedevsecops import wsfs
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import WorkspaceManager, resolve_git
from wavedevsecops.engine.code_intents import content_hash
from wavedevsecops.gitio import Git, GitError
from wavedevsecops.projections.diff import WORKTREE, read_diff
from wavedevsecops.web.workspaces import _engine, _refusal, _Refused

log = logging.getLogger("wavedevsecops")
BINARY_TEXT = "Ce fichier n'est pas du texte : il s'ouvre dans votre éditeur, pas ici."
TOO_LARGE_TEXT = "Ce fichier est trop gros pour la vue Code : ouvrez-le dans votre éditeur."


def _file_body(repo, path: str) -> dict:
    data = wsfs.read_bytes(repo, path)
    if data is None:
        raise wsfs.SandboxFileError(
            f"« {path} » n'existe pas.", "Choisissez un fichier de la liste."
        )
    body = {
        "path": path,
        "hash": content_hash(data),
        "editable": True,
        "content": "",
        "note_text": "",
    }
    if len(data) > wsfs.CODE_READ_LIMIT:
        return {**body, "editable": False, "note_text": TOO_LARGE_TEXT}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {**body, "editable": False, "note_text": BINARY_TEXT}
    if "\0" in text:
        return {**body, "editable": False, "note_text": BINARY_TEXT}
    return {**body, "content": wsfs.to_lf(text)}


def install_code_routes(app: FastAPI, manager: WorkspaceManager) -> None:
    settings = manager.settings

    @app.get("/api/ws/{workspace_id}/code/tree")
    async def code_tree(workspace_id: str) -> Response:
        try:
            engine = await _engine(manager, workspace_id)
        except _Refused as refused:
            return refused.response
        files, truncated = await asyncio.to_thread(wsfs.code_files, engine.layout.repo)
        return JSONResponse({"files": files, "truncated": truncated})

    @app.get("/api/ws/{workspace_id}/code/file")
    async def code_file(workspace_id: str, path: str = "") -> Response:
        try:
            engine = await _engine(manager, workspace_id)
        except _Refused as refused:
            return refused.response
        try:
            body = await asyncio.to_thread(_file_body, engine.layout.repo, path)
        except AppError as error:
            return _refusal(404, f"{error.cause_text} {error.action_text}")
        return JSONResponse(body)

    @app.get("/api/ws/{workspace_id}/code/diff")
    async def code_diff(workspace_id: str, target: str = WORKTREE) -> Response:
        try:
            engine = await _engine(manager, workspace_id)
        except _Refused as refused:
            return refused.response
        git = Git.for_workspace(
            engine.git_path or resolve_git(settings), engine.layout.root, settings
        )
        try:
            view = await asyncio.to_thread(read_diff, git, engine.layout.repo, target)
        except GitError:
            log.warning("Diff illisible pour %s", workspace_id, exc_info=True)
            return _refusal(409, "Git n'a pas pu calculer le diff. Réessayez dans un instant.")
        except AppError as error:
            return _refusal(404, f"{error.cause_text} {error.action_text}")
        return JSONResponse(view.model_dump(mode="json"))
