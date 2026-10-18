"""Bilan de fin de scénario : textes du `score-summary`, écrits par le serveur (AD-2, AD-14).

Le bilan est dérivé des faits du premier passage (`progress.facts.derive`) : rien n'est écrit,
donc le même bilan revient après un redémarrage, et un Recommencer ne le change pas (FR-10).

Contrat lu par le panneau Scénario et, plus tard, par l'export du rapport (story 6.5) :
`build_summary(progress)` rend un dict JSON aux clés stables, ci-dessous.
"""

from __future__ import annotations

from typing import Any

from wavedevsecops.progress.facts import ScenarioProgress

FIRST_ATTEMPT_STEP_TYPES = frozenset({"quiz", "designate"})
"""Types d'étape comptés dans le score du premier coup (quiz 4.5, désignation 5.2)."""
NO_QUIZ_TEXT = "Aucune question dans ce scénario"
SEPARATOR = " · "


def hints_text(count: int) -> str:
    """« 0 indice », « 1 indice », « 2 indices » (le zéro reste au singulier)."""
    return f"{count} indice" if count < 2 else f"{count} indices"


def score_text(correct: int, total: int) -> str:
    """« 3 sur 4 du premier coup » ; sans question, un texte qui le dit."""
    return f"{correct} sur {total} du premier coup" if total else NO_QUIZ_TEXT


def build_summary(progress: ScenarioProgress, asked: int = 0) -> dict[str, Any]:
    """Bilan d'un scénario terminé.

    `asked` : nombre de questions du scénario (étapes de `FIRST_ATTEMPT_STEP_TYPES`). Le total
    vaut au moins ce nombre : un suivi perdu ne fait pas dire « Aucune question » à un scénario
    qui en pose.

    Clés : `quiz_correct`, `quiz_total` (premiers essais justes / posés), `hints` (indices
    ouverts), `score_text`, `hints_text` et `text` (« 3 sur 4 du premier coup · 1 indice »).
    """
    total = max(progress.quiz_total, asked)
    score = score_text(progress.quiz_correct, total)
    hints = hints_text(progress.hints)
    return {
        "quiz_correct": progress.quiz_correct,
        "quiz_total": total,
        "hints": progress.hints,
        "score_text": score,
        "hints_text": hints,
        "text": f"{score}{SEPARATOR}{hints}",
    }
