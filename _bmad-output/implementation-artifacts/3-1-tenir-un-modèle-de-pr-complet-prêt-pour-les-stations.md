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
- Les revues ne sont pas invalidées par un nouveau SHA par défaut, comme sur GitHub ; la protection porte `dismiss_stale_reviews` (faux par défaut) pour ne compter que les revues du `head_sha` courant. Choix du défaut remonté à Anaël.
- `pr_updated` et `check_updated` restent des charges ouvertes du catalogue : leur émission arrive avec 3.2 et 3.3 (`RefreshResult.updated` et `sha_changed` donnent les PR à signaler et les runs à demander).

## Reports

- Appel de `github_sim.refresh` dans le corps des opérations qui changent les refs de `origin` : push du terminal (`terminal_line`, 2.4) et `pr_merge` (3.2), avant la projection, puis émission de `pr_updated` pour `RefreshResult.updated`. Le changement externe le fait déjà (`engine.manager.github_refresher`), mais le surveillant ignore `.git/` : un push fait hors de l'application sans autre modification de l'arbre n'est vu qu'à la prochaine opération. 2.4 doit donc appeler `refresh` elle-même.
- Merge par `merge-tree`/`commit-tree`/`update-ref` : story 3.2. Hook `pre-receive` (lit `protections[].block_direct_push`) et op `install_hooks` : story 3.5. Op `colleague_commit` et réactions du collègue : story 3.4. Projection Distant + PR : story 3.3.
- Demande d'un run au pipeline simulé quand les checks repassent à `queued` : avec `ci` (AD-10).

## Revue

Revue Opus, 2026-10-18, après rebase sur `main` (de2df2c). Grammaire `element_id` de la 2.6 (`origin/story/2-6-etat-graphe`) vérifiée : `pr:<n>`, `check:<pr>:<job_id>:<sha40>`, `review:<pr>:<n>` et `ref:<nom complet>` sont conformes, rien à ajuster.

- medium · second avis 1 · corrigé : `refresh` n'était appelé qu'au setup. Le changement externe recalcule maintenant les PR dans la file (`github_refresher`, nouvelle empreinte publiée si `github.json` change) ; `refresh` n'écrit rien sans `github.json`. Le push du terminal (2.4) et `pr_merge` (3.2) restent à brancher (Reports).
- low · second avis 2 · corrigé : `dismiss_stale_reviews` dans la protection et l'op `set_protection`, faux par défaut (comportement de GitHub conservé).
- low · second avis 3 · corrigé : `re.fullmatch` refuse `"build
"`.
- low · second avis 4 · corrigé : test des historiques sans ancêtre commun (`commit-tree` sans parent).
- low · second avis 5 · corrigé : un code de sortie inattendu de `merge-tree` devient une raison de blocage `conflict` (« n'a pas pu calculer la fusion ») au lieu d'arrêter le setup ou le recalcul.
- low · second avis 6 · corrigé : `os.replace` réessayé trois fois sous Windows sur `PermissionError`.
- low · second avis 7 · corrigé : `job_id` en double refusé par l'op `open_pr` et par `github_sim.open_pr`.
- low · second avis 8 · rejeté : la règle statique est un garde-fou contre l'erreur, pas contre le contournement délibéré ; la revue de code couvre le reste.
- low · second avis 9 · corrigé : `approvals` est un champ persisté de la PR, recalculé à chaque écriture (la méthode devient `count_approvals`).
- low · revue · corrigé : la raison `head_missing` visait `ref:refs/heads/<branche>`, soit la branche locale de l'apprenant ; elle vise `ref:refs/remotes/origin/<branche>`, comme `set_protection`.
- low · revue · reporté (3.2/3.5) : le drapeau `required` d'un check reste vrai si la protection retire ce check ensuite (le déclaré et l'imposé ne sont pas distingués). Sans effet tant qu'aucun scénario ne change une protection après coup.
