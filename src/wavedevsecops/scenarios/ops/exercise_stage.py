"""Pose le gabarit d'exercice du parcours, à un stade du code d'exercice (AD-7, FR-16)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.context import SetupError
from wavedevsecops.scenarios.ops._base import OpArgs

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext

STAGES_DIR = "stages"
"""Sous-dossier d'un gabarit qui porte les stades du code d'exercice (parcours LLM)."""
LLM_STAGES = ("simple_call", "system_prompt", "tools", "loop")
"""Stades du parcours LLM, dans l'ordre : appel simple, prompt système, outils, boucle."""


class Args(OpArgs):
    op: Literal["exercise_stage"]
    stage: Literal["base", "simple_call", "system_prompt", "tools", "loop"]
    """`base` : le gabarit du parcours sans IA. Les autres : le parcours LLM à ce stade."""


IGNORED_DIRS = frozenset({"__pycache__", ".ruff_cache", ".pytest_cache", ".venv"})
"""Caches que les outils posent à côté des gabarits sur le poste d'un auteur."""


def template_files(root: Path) -> dict[str, Path]:
    """Fichiers d'un dossier de gabarit, par chemin posix relatif, sans les caches d'outils."""
    return {
        p.relative_to(root).as_posix(): p
        for p in sorted(root.rglob("*"))
        if p.is_file() and not IGNORED_DIRS & set(p.relative_to(root).parts)
    }


def apply(args: Args, ctx: SetupContext) -> str:
    track = ctx.layout.track
    if track == "no_ai" and args.stage != "base":
        raise SetupError(f"Le stade « {args.stage} » n'existe pas pour le parcours « no_ai ».")
    if track != "no_ai" and args.stage == "base":
        raise SetupError(f"Le parcours « {track} » demande un stade du code LLM, pas « base ».")
    template = ctx.exercise_root / track
    if not template.is_dir():
        raise SetupError(f"Le gabarit d'exercice « {track} » est introuvable.")
    files = {
        path: source
        for path, source in template_files(template).items()
        if not path.startswith(f"{STAGES_DIR}/")
    }
    if args.stage != "base":
        # Le stade remplace les fichiers de même chemin (le code d'exercice).
        files.update(template_files(template / STAGES_DIR / args.stage))
    for path, source in files.items():
        wsfs.write_text(ctx.layout.repo, path, source.read_text(encoding="utf-8"))
    return element_id("path", "worktree", "pyproject.toml")
