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


TRACKS: tuple[tuple[str, str, str], ...] = (
    (
        "llm",
        "Parcours LLM",
        "Le code d'exercice est écrit par un assistant, que vous relisez et corrigez.",
    ),
    (
        "no_ai",
        "Parcours sans IA",
        "Le code d'exercice est écrit à la main, sans assistant.",
    ),
)
"""Parcours proposés : `(clé, libellé, phrase du choix)`. Source unique du `path-picker` et du
`path-menu` (UX-DR4, UX-DR29)."""


def track_options() -> list[dict[str, str]]:
    return [{"key": k, "label": label, "text": text} for k, label, text in TRACKS]


STATION_MILESTONES: dict[int, str] = {1: "v0.2", 2: "v0.2", 3: "v0.2", 4: "v0.3"}
"""Jalon qui livre chaque station de la chaîne (AD-2) : l'encart « Ce qui l'aurait bloqué » (5.9)
annonce « Arrive en <jalon> » tant que le jalon courant ne l'a pas atteint."""


def _version(milestone: str) -> tuple[int, ...]:
    return tuple(int(part) for part in milestone.lstrip("v").split("."))


def station_delivered(station: int, milestone: str = CURRENT_MILESTONE) -> bool:
    """Vrai si le jalon `milestone` livre la station (une station sans jalon déclaré : non)."""
    declared = STATION_MILESTONES.get(station)
    return declared is not None and _version(declared) <= _version(milestone)


def delivered_surfaces(milestone: str = CURRENT_MILESTONE) -> list[Surface]:
    """Surfaces livrées au plus tard par `milestone`, dans l'ordre de l'en-tête."""
    return [s for s in SURFACES if _version(s.milestone) <= _version(milestone)]
