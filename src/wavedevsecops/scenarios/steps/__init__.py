"""Registre des types d'étape (AD-7) : un type par module de ce paquet.

Chaque module `<nom>.py` déclare :

- `Args`, sous-classe de `StepArgs`, dont le champ `type` vaut `Literal["<nom>"]` ;
- `check(state, ctx) -> Verdict`, qui juge l'étape `ctx.step` ; `state` est l'état réel du
  dépôt (`RepoState`), ou `None` si la vue `repo` est illisible ; `ctx` est un `StepContext`
  (alias, état d'avant, intention, données de l'opération, vues).

Ajouter un type, c'est ajouter un module : ni le moteur, ni le chargeur, ni les scénarios
existants ne changent. Les modules dont le nom commence par `_` ne sont pas des types.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Union, get_args

from pydantic import Field

from wavedevsecops.contracts import RepoState
from wavedevsecops.scenarios.steps._base import (
    Observed,
    StepArgs,
    StepContext,
    Verdict,
    VerdictStatus,
)


@dataclass(frozen=True)
class StepType:
    """Un type du registre : son nom, le modèle de ses arguments, son contrôle."""

    name: str
    args: type[StepArgs]
    check: Callable[[RepoState | None, StepContext], Verdict]
    summary: str
    panel: Callable[[Any], dict[str, Any]] | None = None
    """Champs que le type ajoute à l'étape courante du panneau Scénario (optionnel)."""


def _discover() -> dict[str, StepType]:
    registry: dict[str, StepType] = {}
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        args = getattr(module, "Args", None)
        check = getattr(module, "check", None)
        if not (isinstance(args, type) and issubclass(args, StepArgs) and callable(check)):
            raise TypeError(
                f"type d'étape {info.name} : le module doit déclarer Args (StepArgs) et check"
            )
        if get_args(args.model_fields["type"].annotation) != (info.name,):
            raise TypeError(
                f"type d'étape {info.name} : Args.type doit valoir Literal[{info.name!r}]"
            )
        summary = (module.__doc__ or "").strip().splitlines()[0] if module.__doc__ else ""
        registry[info.name] = StepType(
            info.name, args, check, summary, getattr(module, "panel", None)
        )
    return registry


STEP_TYPES: dict[str, StepType] = _discover()


def step_union() -> Any:
    """Type pydantic d'une étape : union des `Args`, discriminée par `type`."""
    models = tuple(spec.args for spec in STEP_TYPES.values())
    if len(models) == 1:  # pydantic refuse un discriminant sur un seul modèle
        return models[0]
    return Annotated[Union[models], Field(discriminator="type")]  # noqa: UP007


__all__ = [
    "STEP_TYPES",
    "Observed",
    "StepArgs",
    "StepContext",
    "StepType",
    "Verdict",
    "VerdictStatus",
    "step_union",
]
