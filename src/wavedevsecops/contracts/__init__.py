"""Schémas partagés et grammaire `element_id` (AD-2).

Module feuille (AD-1) : n'importe rien du projet ; tout module peut l'importer.
"""

from __future__ import annotations


class AppError(Exception):
    """Erreur métier typée (convention « Erreurs »).

    Elle porte deux textes en français pour l'apprenant : ce qui s'est passé
    (`cause_text`) et ce qu'il peut faire (`action_text`). Jamais de trace Python montrée.
    """

    def __init__(self, cause_text: str, action_text: str) -> None:
        super().__init__(f"{cause_text} {action_text}")
        self.cause_text = cause_text
        self.action_text = action_text
