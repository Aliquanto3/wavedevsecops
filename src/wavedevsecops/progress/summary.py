"""Bilan de fin de scénario : textes du `score-summary`, écrits par le serveur (AD-2, AD-14).

Le bilan est dérivé des faits du premier passage (`progress.facts.derive`) : rien n'est écrit,
donc le même bilan revient après un redémarrage, et un Recommencer ne le change pas (FR-10).

Contrat lu par le panneau Scénario et, plus tard, par l'export du rapport (story 6.5) :
`build_summary(progress)` rend un dict JSON aux clés stables, ci-dessous.
"""

from __future__ import annotations

from typing import Any

from wavedevsecops.progress.facts import ScenarioProgress

NO_QUIZ_TEXT = "Aucune question dans ce scénario"
SEPARATOR = " · "


def hints_text(count: int) -> str:
    """« 0 indice », « 1 indice », « 2 indices » (le zéro reste au singulier)."""
    return f"{count} indice" if count < 2 else f"{count} indices"


def score_text(correct: int, total: int) -> str:
    """« 3 sur 4 du premier coup » ; sans question, un texte qui le dit."""
    return f"{correct} sur {total} du premier coup" if total else NO_QUIZ_TEXT


def build_summary(progress: ScenarioProgress) -> dict[str, Any]:
    """Bilan d'un scénario terminé.

    Clés : `quiz_correct`, `quiz_total` (premiers essais justes / posés), `hints` (indices
    ouverts), `score_text`, `hints_text` et `text` (« 3 sur 4 du premier coup · 1 indice »).
    """
    score = score_text(progress.quiz_correct, progress.quiz_total)
    hints = hints_text(progress.hints)
    return {
        "quiz_correct": progress.quiz_correct,
        "quiz_total": progress.quiz_total,
        "hints": progress.hints,
        "score_text": score,
        "hints_text": hints,
        "text": f"{score}{SEPARATOR}{hints}",
    }
