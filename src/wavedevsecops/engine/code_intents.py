"""Intentions `save_file` et `open_external` de la vue Code (AD-1, AD-4, AD-17).

`save_file{path, content, base_hash}` écrit un fichier de `repo/` par `wsfs` (chemin confiné,
UTF-8, LF, atomique), à condition que le fichier n'ait pas changé depuis son ouverture :
`base_hash` est l'empreinte SHA-256 de ses octets sur le disque, rendue par la lecture
`GET …/code/file`. Un écart est refusé en 409 dès la réception, et revérifié dans la file, où
le disque a pu bouger. `open_external{path}` ouvre le fichier, résolu par `wsfs`, dans
l'éditeur par défaut du système.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

from wavedevsecops import toolrun, wsfs
from wavedevsecops.engine.intents import INTENTS, Intent, register_intent
from wavedevsecops.engine.operations import (
    OpContext,
    Operation,
    OperationRefused,
    WorkspaceEngine,
)

SAVE = "save_file"
OPEN = "open_external"
EXIT_REFUSED = 2
MAX_CONTENT = wsfs.CODE_READ_LIMIT

OPENER: Callable[[Path], None] = toolrun.open_in_default_editor
"""Ouvre un chemin dans l'éditeur du système ; remplacé par les tests."""


class SaveFile(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    content: str = Field(max_length=MAX_CONTENT)
    base_hash: str = Field(default="", max_length=64, pattern=r"^[0-9a-f]*$")
    """Empreinte du fichier à l'ouverture ; vide : le fichier n'existait pas."""


class OpenExternal(BaseModel):
    path: str = Field(min_length=1, max_length=1000)


def content_hash(data: bytes | None) -> str:
    """Empreinte d'un fichier tel que le disque le porte ; vide s'il n'existe pas."""
    return "" if data is None else hashlib.sha256(data).hexdigest()


def conflict_text(path: str) -> str:
    return (
        f"Le fichier « {path} » a changé sur le disque depuis son ouverture. "
        "Gardez votre version ou rechargez le fichier."
    )


def _check_save(repo: Path, body: SaveFile) -> None:
    """Refus connus d'avance : écart d'empreinte, dossier à la place du fichier, dossier absent."""
    target = wsfs.confine(repo, body.path)
    if target.is_dir():
        raise wsfs.SandboxFileError(f"« {body.path} » est un dossier.", "Choisissez un fichier.")
    current = wsfs.read_bytes(repo, body.path)
    if content_hash(current) != body.base_hash:
        raise OperationRefused(conflict_text(body.path))
    if current is None:
        wsfs.require_parent(repo, body.path)


def build_save_file(engine: WorkspaceEngine, body: SaveFile) -> Operation:
    repo = engine.layout.repo
    _check_save(repo, body)

    def run(ctx: OpContext) -> int:
        try:
            _check_save(ctx.layout.repo, body)
        except OperationRefused as refused:
            ctx.output(refused.reason_text, "refused")
            return EXIT_REFUSED
        wsfs.write_text(ctx.layout.repo, body.path, body.content)
        ctx.output(f"Fichier « {body.path} » enregistré.", "app")
        return 0

    return Operation(SAVE, run)


def build_open_external(engine: WorkspaceEngine, body: OpenExternal) -> Operation:
    target = wsfs.confine(engine.layout.repo, body.path, portable=False)
    if not target.is_file():
        raise wsfs.SandboxFileError(
            f"« {body.path} » n'existe pas.", "Choisissez un fichier de la liste."
        )

    def run(ctx: OpContext) -> int:
        try:
            OPENER(wsfs.confine(ctx.layout.repo, body.path, portable=False))
        except OSError:
            ctx.output(
                f"Le système n'a pas pu ouvrir « {body.path} » dans un éditeur. "
                "Modifiez-le dans la vue Code.",
                "refused",
            )
            return EXIT_REFUSED
        ctx.output(f"Fichier « {body.path} » ouvert dans votre éditeur.", "app")
        return 0

    return Operation(OPEN, run, writes=False, validate=False)


def register_intents() -> None:
    """Enregistre `save_file` et `open_external` (idempotent)."""
    for name, model, build in (
        (SAVE, SaveFile, build_save_file),
        (OPEN, OpenExternal, build_open_external),
    ):
        if name not in INTENTS:
            register_intent(Intent(name, model, build))
