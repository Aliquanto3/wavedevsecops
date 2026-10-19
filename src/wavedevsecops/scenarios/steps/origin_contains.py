"""Étape validée quand `origin` porte de nouveau des commits donnés (AD-7, AD-8).

Le jugement lit le dépôt nu `origin.git` lui-même, pas la branche de suivi locale : seul un
envoi réussi le satisfait. Un commit est « présent » sur la branche d'`origin` s'il en est un
ancêtre (fusion, avance rapide, restauration de la branche) ou si elle porte un commit de même
patch (`git cherry` : `cherry-pick`, `rebase`), et si le sommet garde son travail : chaque
fichier que le commit ajoute ou modifie y a le même contenu, chaque fichier qu'il supprime en
est absent (un `git rm` ou un `revert` poussé après la fusion ne passe pas). Quelle que soit la
suite de commandes.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field

from wavedevsecops.contracts import RepoState, element_id, parse_element_id
from wavedevsecops.scenarios.steps._base import Observed, StepArgs, StepContext, Verdict

log = logging.getLogger("wavedevsecops")


class Args(StepArgs):
    type: Literal["origin_contains"]
    branch: str = "main"
    """Branche d'`origin` examinée (nom court)."""
    present: list[str] = Field(min_length=1)
    """Commits (`@alias`) qui doivent être sur la branche, d'identité ou de patch."""


def _sha(ctx: StepContext, alias: str) -> str | None:
    target = ctx.aliases.get(alias.removeprefix("@"))
    if not target:
        return None
    try:
        kind, segments = parse_element_id(target)
    except ValueError:
        return None
    return segments[0] if kind == "commit" and segments else None


def _kept(git, origin, tip: str, sha: str) -> bool:
    """Le sommet `tip` garde le travail de `sha` : mêmes blobs pour les fichiers que `sha`
    ajoute ou modifie, absence de ceux qu'il supprime. Échec fermé."""
    changed = git.run(
        "diff-tree", "-r", "--root", "--no-commit-id", "--no-renames", "-z", sha, cwd=origin
    )
    if not changed.ok:
        return False
    items = [item for item in changed.stdout.split("\0") if item]
    expected: dict[str, str | None] = {}
    for meta, path in zip(items[::2], items[1::2], strict=False):
        fields = meta.split()
        if len(fields) < 5:
            return False
        expected[path] = None if fields[4] == "D" else fields[3]
    if not expected:
        return True
    listed = git.run(
        "--literal-pathspecs",
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        tip,
        "--",
        *expected,
        cwd=origin,
    )
    if not listed.ok:
        return False
    actual: dict[str, str] = {}
    for entry in listed.stdout.split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if path and len(fields) == 3:
            actual[path] = fields[2]
    return all(actual.get(path) == blob for path, blob in expected.items())


def _present(git, origin, tip: str, sha: str) -> bool:
    """`sha` est sur la branche de sommet `tip` (ancêtre, ou patch équivalent) et le sommet
    garde son travail. Échec fermé."""
    known = git.run("cat-file", "-e", f"{sha}^{{commit}}", cwd=origin)
    if not known.ok:
        return False
    ancestor = git.run("merge-base", "--is-ancestor", sha, tip, cwd=origin)
    if ancestor.returncode == 0:
        return _kept(git, origin, tip, sha)
    if ancestor.returncode != 1:
        return False
    cherry = git.run("cherry", tip, sha, cwd=origin)
    if not cherry.ok:
        return False
    for line in cherry.stdout.splitlines():
        mark, _, found = line.partition(" ")
        if found.strip() == sha:
            return mark == "-" and _kept(git, origin, tip, sha)
    return False


def check(state: RepoState | None, ctx: StepContext) -> Verdict:
    """`passed` si `origin` porte tous les commits demandés ; sinon `failed` qui nomme ceux
    qui manquent, ou `pending` si rien n'a bougé."""
    if state is None:
        return Verdict(status="pending")
    step: Args = ctx.step
    git = ctx.git() if ctx.git is not None else None
    if git is None or ctx.layout is None:
        return Verdict(status="pending")
    origin = ctx.layout.origin
    try:
        tip = git.run(
            "rev-parse", "--verify", "-q", f"refs/heads/{step.branch}^{{commit}}", cwd=origin
        )
        found: list[tuple[str | None, bool]] = []
        if tip.ok:
            top = tip.stdout.strip()
            for alias in step.present:
                sha = _sha(ctx, alias)
                found.append((sha, sha is not None and _present(git, origin, top, sha)))
    except Exception:  # noqa: BLE001 - un git indisponible ne bloque rien
        log.exception("Étape %s : origin illisible", step.step_id)
        return Verdict(status="pending")
    if tip.ok and all(ok for _, ok in found):
        return Verdict(status="passed")
    if ctx.previous is not None and ctx.previous == state:
        return Verdict(status="pending")
    expected = (
        f"`origin/{step.branch}` porte les commits attendus (le même commit ou son patch) "
        "et garde leurs fichiers."
    )
    if not tip.ok:
        reason = f"La branche `{step.branch}` n'existe plus sur `origin`."
        observed = [Observed(text=reason)]
    else:
        missing = [sha for sha, ok in found if not ok and sha is not None]
        names = ", ".join(f"`{sha[:7]}`" for sha in missing)
        reason = (
            f"Sur `origin/{step.branch}`, il manque encore : {names}. Un envoi n'a d'effet que "
            f"s'il aboutit : après le `push`, `git log origin/{step.branch}` doit les montrer."
        )
        observed = [
            Observed(
                text=(
                    f"Le commit `{sha[:7]}` (ou son travail) n'est pas sur `origin/{step.branch}`."
                ),
                element_id=element_id("commit", sha),
            )
            for sha in missing
        ]
    return Verdict(status="failed", reason_text=reason, expected_text=expected, observed=observed)
