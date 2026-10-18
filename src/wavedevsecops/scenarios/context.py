"""Contexte d'exécution du setup : espace, git, alias, horloge et identités fixes (AD-3, AD-7).

Les dates et les identités sont fixes : un même scénario donne les mêmes SHA sur les trois
systèmes. Les alias (`as: <alias>`) sont résolus en `element_id` (AD-2) ; une op les cite
sous la forme `@alias`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from wavedevsecops.config import get_settings
from wavedevsecops.contracts import AppError, parse_element_id
from wavedevsecops.gitio import LEARNER_EMAIL, LEARNER_NAME, Git
from wavedevsecops.wsfs import Layout

Persona = Literal["learner", "colleague", "agent"]


@dataclass(frozen=True)
class Identity:
    name: str
    email: str


PERSONAS: dict[str, Identity] = {
    "learner": Identity(LEARNER_NAME, LEARNER_EMAIL),
    "colleague": Identity("Sacha Martin", "sacha.martin@exemple.test"),
    "agent": Identity("Agent B", "agent-b@exemple.test"),
}
"""Identités fixes des auteurs du setup (l'apprenant, le collègue simulé, l'agent B)."""

SETUP_EPOCH = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
"""Date du premier commit d'un setup ; les suivants avancent de `COMMIT_STEP`."""
COMMIT_STEP = timedelta(minutes=1)


class SetupError(AppError):
    """Le setup d'un scénario n'a pas pu aboutir (alias inconnu, gabarit absent…)."""

    def __init__(self, cause_text: str) -> None:
        super().__init__(cause_text, "Corrigez le scénario, puis relancez sa préparation.")


def git_date(moment: datetime) -> str:
    """Date au format interne de git (`@<secondes> +hhmm`), sans ambiguïté d'analyse."""
    offset = moment.utcoffset() or timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, rest = divmod(abs(minutes), 60)
    return f"@{int(moment.timestamp())} {sign}{hours:02d}{rest:02d}"


@dataclass
class SetupContext:
    """État partagé par les ops d'un setup."""

    layout: Layout
    git: Git
    exercise_root: Path = field(default_factory=lambda: get_settings().content_path() / "exercise")
    """`content/exercise/` : un gabarit par parcours (`llm/`, `no_ai/`)."""
    aliases: dict[str, str] = field(default_factory=dict)
    commits: int = 0

    def next_date(self, fixed: datetime | None = None) -> datetime:
        """Date du prochain commit : `fixed` si l'op la donne, sinon l'horloge du setup."""
        moment = fixed or SETUP_EPOCH + self.commits * COMMIT_STEP
        self.commits += 1
        return moment

    def identity_env(self, persona: str, moment: datetime) -> dict[str, str]:
        """Variables d'auteur et de committer d'un commit du setup."""
        who = PERSONAS[persona]
        date = git_date(moment)
        return {
            "GIT_AUTHOR_NAME": who.name,
            "GIT_AUTHOR_EMAIL": who.email,
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_NAME": who.name,
            "GIT_COMMITTER_EMAIL": who.email,
            "GIT_COMMITTER_DATE": date,
        }

    def element(self, value: str) -> str:
        """`element_id` désigné par `@alias`."""
        name = value.removeprefix("@")
        try:
            return self.aliases[name]
        except KeyError:
            raise SetupError(
                f"L'alias « @{name} » n'est défini par aucune op précédente."
            ) from None

    def revision(self, value: str) -> str:
        """Révision git d'une valeur : `@alias` (commit ou ref) ou nom de révision tel quel."""
        if not value.startswith("@"):
            return value
        kind, segments = parse_element_id(self.element(value))
        if kind not in {"commit", "ref"}:
            raise SetupError(f"L'alias « {value} » ne désigne ni un commit ni une ref.")
        return segments[0]

    def branch_name(self, value: str) -> str:
        """Nom court d'une branche : `@alias` d'une ref `refs/heads/…` ou nom tel quel."""
        revision = self.revision(value)
        if value.startswith("@") and not revision.startswith("refs/heads/"):
            raise SetupError(f"L'alias « {value} » ne désigne pas une branche locale.")
        return revision.removeprefix("refs/heads/")
