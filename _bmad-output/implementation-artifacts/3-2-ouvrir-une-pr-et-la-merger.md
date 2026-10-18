---
story: "3.2"
key: 3-2-ouvrir-une-pr-et-la-merger
title: Ouvrir une PR et la merger
status: review
branch: story/3-2-pr-merge
ad: [AD-1, AD-2, AD-8, AD-17]
---

# Story 3.2 : Ouvrir une PR et la merger

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 3.2 » ; FR-6, FR-4.

## Livré

- `github_sim.merge_pr` : recalcule la PR, refuse si elle n'est pas mergeable (raisons de blocage dans le message), puis écrit le merge dans `origin.git` sans worktree ni `receive-pack` : `merge-tree --write-tree`, `commit-tree` (message « Merge pull request #n from <branche> », identité fixe `MERGE_IDENTITY`) et `update-ref <ref> <nouveau> <ancien attendu>`. La PR passe à `merged` avec `merge_sha` ; les autres PR sont recalculées dans la même écriture.
- Base qui a bougé entre le calcul et l'écriture : `update-ref` refuse, rien n'est écrit, les PR sont recalculées et `MergeRaced` dit en français de relire les blocages puis de réessayer.
- `engine/pr_intents.py` : intentions `pr_open` (`head`, `base` = `main`, `title_text`) et `pr_merge` (`number`). Refus connus d'avance (branche absente d'`origin` : « Poussez d'abord la branche… » ; PR inconnue, fermée ou bloquée) en 409 dès la réception, sans écrire ; le corps de l'opération revérifie dans la file et dit le refus à l'écran (code 2). Chaque PR touchée émet `pr_updated` (`number`, `element_id`, `state`).
- Branchement : `terminal.AFTER_COMMAND_HOOKS` reçoit `pr_intents.refresh_after_command` (dans `web/app.py`, à côté de `terminal.register_intents()`, sans doublon) : après `push`, `pull` ou `fetch`, `github_sim.refresh` recalcule les PR et `pr_updated` part pour celles qui changent. Ni la liste blanche AD-4, ni `contracts/`, ni `events/` ne changent.
- Tests `tests/test_pr_intents.py` (vrai git, vraie file) : ouverture puis merge de bout en bout (identité, message, deux parents, `origin/main` à jour après `git fetch`), branche absente (409), conflit (refus du merge), base qui bouge pendant le merge, rafraîchissement par un push du terminal.

## Décisions

- Le 409 synchrone lit `github.json` et `origin.git` hors file (lecture seule) ; toute écriture reste dans la file.
- `pr_updated` garde sa charge ouverte du catalogue ; le schéma définitif viendra avec 3.3.
- Après un merge, toutes les PR sont annoncées (recalcul des PR sœurs, sans filtre fin) : `pr_updated` est idempotent côté vue.

## Reports

- Vue Distant + PR (3.3), collègue et hook `pre-receive` (3.4, 3.5), run du pipeline simulé à la remise en file des checks (ci, AD-10).
- Pas de fermeture de PR (`closed`) ni de merge squash/rebase : hors périmètre.
- Le drapeau `required` d'un check n'est pas distingué du déclaré (reporté de 3.1).
