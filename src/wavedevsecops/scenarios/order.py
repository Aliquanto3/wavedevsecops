"""Ordre conseillé du catalogue (FR-9), partagé par le moteur et le serveur web.

Il vit ici, hors de `web`, parce que le moteur en a besoin pour proposer le « Scénario suivant »
du bilan (story 4.7) et que `engine` n'importe pas `web` (AD-1). Le catalogue (story 6.1)
reprend `SOCLE_SECTION`, `SOCLE_ORDER` et `catalogue_rank` d'ici.
"""

from __future__ import annotations

SOCLE_SECTION = "socle-git"
"""Section du socle git ; un scénario sans section y est rangé."""

SOCLE_ORDER: tuple[str, ...] = (
    "add-commit",
    "push-pull",
    "branche",
    "pr-merge",
    "conflit",
    "stash",
    "rebase",
    "recuperation",
)
"""Ordre conseillé du socle git (FR-9), par `scenario_id`. Un identifiant pas encore livré est
absent du catalogue ; un scénario absent de cette liste vient après, par ordre alphabétique."""


STATIONS_SECTION = "stations"
"""Section des scénarios de station (Story 9.3) ; elle vient après le socle git."""

STATION_ORDER: tuple[str, ...] = ("defaut-de-lint", "test-casse", "secret-dans-un-commit")
"""Ordre conseillé des scénarios de station, à l'intérieur d'une station, par `scenario_id`."""


def section_of(section: str | None) -> str:
    """Section effective : sans section, le socle git."""
    return section or SOCLE_SECTION


def catalogue_rank(scenario_id: str) -> tuple[int, str]:
    """Clé de tri du catalogue : rang dans `SOCLE_ORDER`, puis identifiant."""
    if scenario_id in SOCLE_ORDER:
        return SOCLE_ORDER.index(scenario_id), scenario_id
    if scenario_id in STATION_ORDER:
        return len(SOCLE_ORDER) + 1 + STATION_ORDER.index(scenario_id), scenario_id
    return len(SOCLE_ORDER), scenario_id
