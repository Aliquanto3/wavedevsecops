---
story: "3.1"
key: 3-1-tenir-un-modèle-de-pr-complet-prêt-pour-les-stations
title: Tenir un modèle de PR complet, prêt pour les stations
status: review
branch: story/3-1-modele-pr
ad: [AD-5, AD-6, AD-7, AD-8, AD-20]
---

# Story 3.1 : Tenir un modèle de PR complet, prêt pour les stations

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 3.1 » ; AR-9.

## Livré

- `contracts/github.py` (nouveau sous-module, `contracts/__init__.py` inchangé) : schéma de `github.json`, `schema_version` 1. `GithubState{next_number, protections, pulls}` ; `PullRequest{number, title_text, head, base, state, head_sha, base_sha, checks, reviews, required_approvals, protection, mergeable, blocking_reasons, merge_sha}` ; `Check{job_id, head_sha, base_sha, state queued|running|success|failure|error, required, output, findings, duration_ms, updated_at}` ; `Review`, `BranchProtection{branch, required_approvals, required_checks, block_direct_push}`, `BlockReason{kind check|approvals|conflict|head_missing, text, element_id}`, `Finding`. `element_id` d'AD-2 : `pr:<n>`, `check:<pr>:<job_id>:<head_sha>`, `review:<pr>:<n>`.
- `github_sim/` : seul écrivain de `github.json` (`wsfs.write_json`, atomique, JSON trié, LF). `load` (migrations numérotées `MIGRATIONS`, version future ou fichier illisible → `GithubSimError` en français ; fichier absent → état vide), `init`, `open_pr` (branches lues sur `origin.git`, refus si absente, PR numérotées à partir de 1 et jamais réutilisées, checks et revues déclarés liés aux SHA courants), `set_protection`, `refresh` (idempotent, n'écrit que si une PR change), `evaluate` (pur), `has_conflict` (`git merge-tree --write-tree --no-messages`, sans worktree ; historiques sans ancêtre commun = conflit), `canonical_digest`.
- Chaque écriture recalcule toutes les PR ouvertes contre les refs de `origin` : `head_sha`/`base_sha` changés → checks remis à `queued` (sortie, constats, durée effacés) dans la même écriture ; checks obligatoires de la protection ajoutés s'ils manquent ; `mergeable` et raisons de blocage (check non `success` ou réussi sur un ancien SHA, approbations, conflit, branche disparue), chacune avec son texte et son `element_id`. Approbations : dernière revue décisive de chaque auteur.
- Ops de setup `open_pr` (head, base, title_text, checks, reviews déclarés ; produit `pr:<n>`) et `set_protection` (produit `ref:refs/remotes/origin/<branche>`), avec `@alias` d'une branche locale ou de suivi (`scenarios/ops/_origin.py`).
- `run_setup` crée `github.json` vide avant les ops et recalcule les PR après la dernière op. L'empreinte (AD-6) inclut `github.json` canonique sans `checks[].output`, durées ni horodatages ; `content/fingerprints.json` régénéré (les quatre empreintes changent : ajout de la ligne `github`).
- Règle statique « seul `github_sim` nomme `github.json` » (`tests/static_rules.py`, `test_architecture`), avec exemple synthétique.
- Tests `tests/test_github_sim.py` (vrai git) : champs du modèle, fichier vide versionné, numérotation, branche absente, check obligatoire déclaré en échec/erreur/succès, remise à `queued` au changement de tête puis de base, `refresh` idempotent, vieux succès refusé, conflit par `merge-tree`, approbations, branche disparue, empreinte insensible à la sortie et à la durée, version future, migration.

## Décisions

- Pas de garde d'exécution « dans la file » : `github_sim` ne dépend pas d'`engine` (pas de cycle). L'exigence « depuis une opération de la file » tient par construction (le setup passe par la file, AD-1 ; les intentions `pr_open`/`pr_merge` de 3.2 y passeront) et le seul écrivain est vérifié statiquement.
- La protection est stockée une fois, au niveau de `github.json` (`protections`) ; chaque PR en porte une copie (`protection`, `required_approvals`) rafraîchie à chaque recalcul : la vue lit la PR seule.
- `head_missing` s'ajoute aux trois raisons d'AD-8 : une PR dont la branche a disparu d'`origin` ne peut pas être calculée.
- Les revues ne sont pas invalidées par un nouveau SHA (pas de « dismiss stale reviews » en v0.1).
- `pr_updated` et `check_updated` restent des charges ouvertes du catalogue : leur émission arrive avec 3.2 et 3.3 (`RefreshResult.updated` et `sha_changed` donnent les PR à signaler et les runs à demander).

## Reports

- Appel de `github_sim.refresh` après chaque opération qui peut changer les refs de `origin` (push du terminal, 2.4 ; `pr_merge`, 3.2) et émission de `pr_updated` : avec ces stories. La fonction est prête et idempotente.
- Merge par `merge-tree`/`commit-tree`/`update-ref` : story 3.2. Hook `pre-receive` (lit `protections[].block_direct_push`) et op `install_hooks` : story 3.5. Op `colleague_commit` et réactions du collègue : story 3.4. Projection Distant + PR : story 3.3.
- Demande d'un run au pipeline simulé quand les checks repassent à `queued` : avec `ci` (AD-10).
