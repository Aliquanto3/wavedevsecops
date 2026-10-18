"""Registre des ops de setup (AD-7) : une op par module de ce paquet.

Chaque module `<nom>.py` déclare :

- `Args`, sous-classe de `OpArgs`, dont le champ `op` vaut `Literal["<nom>"]` ;
- `apply(args, ctx) -> str`, qui exécute l'op dans le `SetupContext` et rend l'`element_id`
  de l'élément produit (celui que désigne `as: <alias>`).

Ajouter une op, c'est ajouter un module : ni le chargeur ni les scénarios existants ne
changent. Les modules dont le nom commence par `_` ne sont pas des ops.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Union, get_args

from pydantic import Field

from wavedevsecops.scenarios.ops._base import OpArgs


@dataclass(frozen=True)
class OpSpec:
    """Une op du registre : son nom, le modèle de ses arguments, son exécution."""

    name: str
    args: type[OpArgs]
    apply: Callable[[Any, Any], str]
    summary: str


def _discover() -> dict[str, OpSpec]:
    registry: dict[str, OpSpec] = {}
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        args = getattr(module, "Args", None)
        apply = getattr(module, "apply", None)
        if not (isinstance(args, type) and issubclass(args, OpArgs) and callable(apply)):
            raise TypeError(f"op {info.name} : le module doit déclarer Args (OpArgs) et apply")
        if get_args(args.model_fields["op"].annotation) != (info.name,):
            raise TypeError(f"op {info.name} : Args.op doit valoir Literal[{info.name!r}]")
        summary = (module.__doc__ or "").strip().splitlines()[0] if module.__doc__ else ""
        registry[info.name] = OpSpec(info.name, args, apply, summary)
    return registry


REGISTRY: dict[str, OpSpec] = _discover()


def op_union() -> Any:
    """Type pydantic d'une op du setup : union des `Args`, discriminée par `op`."""
    models = tuple(spec.args for spec in REGISTRY.values())
    return Annotated[Union[models], Field(discriminator="op")]  # noqa: UP007


__all__ = ["REGISTRY", "OpArgs", "OpSpec", "op_union"]
