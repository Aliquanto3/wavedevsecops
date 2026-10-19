"""Lectures de la vue Code (story 2.8, AD-2, AD-17) : fichiers, contenu d'un fichier et diff.

- `GET /api/ws/<id>/code/tree` : fichiers de l'arbre de travail ;
- `GET /api/ws/<id>/code/file?path=` : contenu et empreinte (`base_hash` de `save_file`) ;
- `GET /api/ws/<id>/code/diff?target=worktree|<sha>` : diff projeté avec ses `element_id` ;
- `GET /api/ws/<id>/code/pipeline?pr=<n>` : les trois écritures du pipeline au SHA de tête de la
  PR, avec les lignes de chaque tâche (`pipeline-tabs`, story 7.6), en lecture seule.

Ce sont des lectures sans essai ni file : le disque est lu par `wsfs` (chemins confinés) et git par
`gitio` (contexte interne, sans verrou). L'écriture reste l'intention `save_file`.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from wavedevsecops import ci, github_sim, wsfs
from wavedevsecops.ci.pipeline_files import FileLines, read_pipeline_files
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


READ_ONLY_TEXT = "Lecture seule"
NOT_EXECUTED_TEXT = "Ces fichiers se lisent : rien ne s'exécute depuis cette vue."
MARKS_NOTE_TEXT = (
    "Certaines tâches ne sont pas repérées dans ces fichiers : leurs lignes ne sont pas surlignées."
)


def _tab(item: FileLines, pipeline: ci.Pipeline) -> dict:
    jobs: dict[str, dict | None] = {}
    for job in pipeline.jobs:
        found = item.ranges.get(job.job_id)
        jobs[job.job_id] = (
            None
            if found is None
            else {
                "first": found.first,
                "last": found.last,
                "range_text": found.text,
                "a11y_name_text": f"{job.label_text} : {found.text} de {item.file.label_text}",
            }
        )
    return {
        "id": item.file.tab_id,
        "label_text": item.file.label_text,
        "path": item.file.path,
        "available": item.available,
        "content": item.content,
        "jobs": jobs,
    }


def pipeline_view(git: Git, layout: wsfs.Layout, pipeline: ci.Pipeline, number: int) -> dict:
    """Vue `pipeline-tabs` d'une PR : fichiers au SHA de tête et plage de chaque tâche. Des
    balises absentes donnent des constats non bloquants, jamais une erreur (AD-10)."""
    pull = next((p for p in github_sim.load(layout).pulls if p.number == number), None)
    if pull is None:
        raise AppError(
            f"La PR n°{number} n'existe pas.", "Choisissez une PR de la vue Distant + PR."
        )
    files = read_pipeline_files(git, layout, pull.head_sha, pipeline)
    findings = [f for item in files for f in item.findings]
    return {
        "number": number,
        "head_sha": pull.head_sha,
        "title_text": f"Pipeline de la PR n°{number}, commit {pull.head_sha[:7]}",
        "read_only_text": READ_ONLY_TEXT,
        "not_executed_text": NOT_EXECUTED_TEXT,
        "jobs": [{"job_id": job.job_id, "label_text": job.label_text} for job in pipeline.jobs],
        "tabs": [_tab(item, pipeline) for item in files],
        "findings": [f.model_dump(mode="json") for f in findings],
        "notice_text": MARKS_NOTE_TEXT if findings else "",
    }


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

    @app.get("/api/ws/{workspace_id}/code/pipeline")
    async def code_pipeline(workspace_id: str, pr: int = 0) -> Response:
        try:
            engine = await _engine(manager, workspace_id)
        except _Refused as refused:
            return refused.response
        git = Git.for_workspace(
            engine.git_path or resolve_git(settings), engine.layout.root, settings
        )
        try:
            pipeline = await asyncio.to_thread(ci.load_pipeline, settings)
            view = await asyncio.to_thread(pipeline_view, git, engine.layout, pipeline, pr)
        except GitError:
            log.warning("Pipeline illisible pour %s", workspace_id, exc_info=True)
            return _refusal(409, "Git n'a pas pu lire les fichiers du pipeline. Réessayez.")
        except AppError as error:
            return _refusal(404, f"{error.cause_text} {error.action_text}")
        return JSONResponse(view)
