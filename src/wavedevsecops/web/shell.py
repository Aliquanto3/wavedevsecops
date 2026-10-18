"""Surfaces de la coquille d'interface : le serveur déclare celles que le jalon courant livre.

Ajouter une surface = ajouter une ligne à `SURFACES` avec le jalon qui la livre (EXPERIENCE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

CURRENT_MILESTONE = "v0.1"


@dataclass(frozen=True)
class Surface:
    key: str
    label: str
    path: str
    subtitle: str
    milestone: str


SURFACES: tuple[Surface, ...] = (
    Surface("catalogue", "Catalogue", "/", "Les scénarios, par parcours.", "v0.1"),
    Surface("diagnostic", "Diagnostic", "/diagnostic", "Les outils de ce poste.", "v0.1"),
    Surface("vocabulaire", "Vocabulaire", "/vocabulaire", "Les termes de la chaîne.", "v0.2"),
    Surface("fiche", "Fiche", "/fiche", "Les barrières et leurs preuves.", "v0.3"),
)


def _version(milestone: str) -> tuple[int, ...]:
    return tuple(int(part) for part in milestone.lstrip("v").split("."))


def delivered_surfaces(milestone: str = CURRENT_MILESTONE) -> list[Surface]:
    """Surfaces livrées au plus tard par `milestone`, dans l'ordre de l'en-tête."""
    return [s for s in SURFACES if _version(s.milestone) <= _version(milestone)]
