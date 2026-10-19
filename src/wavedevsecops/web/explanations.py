"""Explications attachées aux éléments (story 2.10, AD-7, NFR-13).

`content/explanations.yaml` est le catalogue : une entrée par clé d'explication (`explain_ref`
portée par la projection). `GET /api/explanations` le sert tel quel au front, qui n'écrit aucune
explication lui-même.

Contrat (la story 9.4 s'y appuie pour relier un terme à sa barrière) :

```yaml
schema_version: 1
entries:
  <explain_ref>:            # ex. graph.commit, remote.pr, terminal.output
    title_text: "Un commit"        # titre du popover
    body_text: "Deux ou trois phrases, vouvoiement."
    barrier_id: ""                  # facultatif : id d'une barrière de content/chain.yaml
```

Un fichier absent ou invalide donne un catalogue vide, journalisé : l'application reste
utilisable, le « i » dit alors que l'explication n'est pas disponible.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from wavedevsecops.config import Settings, get_settings

log = logging.getLogger(__name__)

FILE_NAME = "explanations.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Explanation(_Strict):
    title_text: str = Field(min_length=1)
    body_text: str = Field(min_length=1)
    barrier_id: str = ""
    """Barrière (`content/chain.yaml`) que l'élément fait comprendre ; vide : aucune."""


class ExplanationCatalogue(_Strict):
    schema_version: Literal[1]
    entries: dict[str, Explanation]


def load_explanations(settings: Settings | None = None) -> ExplanationCatalogue | None:
    """Catalogue validé ; rien s'il manque ou est invalide (journalisé)."""
    path = (settings or get_settings()).content_path() / FILE_NAME
    try:
        return ExplanationCatalogue.model_validate(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )
    except ValidationError as error:
        log.warning("Explications ignorées (%s) : contenu invalide (%s)", path.name, error)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        log.warning("Explications ignorées (%s) : %s", path.name, error)
    return None


def explanations_body(settings: Settings | None = None) -> dict[str, Any]:
    catalogue = load_explanations(settings)
    if catalogue is None:
        return {"schema_version": 1, "entries": {}}
    return catalogue.model_dump(mode="json")


def install_explanation_routes(app: FastAPI, settings: Settings) -> None:
    @app.get("/api/explanations")
    async def explanations() -> Response:
        body = await asyncio.to_thread(explanations_body, settings)
        return JSONResponse(body, headers={"Cache-Control": "no-store"})
