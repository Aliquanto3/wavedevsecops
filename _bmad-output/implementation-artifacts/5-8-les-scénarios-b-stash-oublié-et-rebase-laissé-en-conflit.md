---
story: "5.8"
key: 5-8-les-scénarios-b-stash-oublié-et-rebase-laissé-en-conflit
title: Les scénarios B « stash oublié » et « rebase laissé en conflit »
status: review
branch: story/5-8-scenarios-b-stash-rebase
ad: [AD-7, AD-4, AD-3]
---

# Story 5.8 : Les scénarios B « stash oublié » et « rebase laissé en conflit »

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.8 » ; FR-12. S'appuie sur les ops `stash` et `agent_rebase_conflict` (5.1), `fetch` (5.7), la désignation (5.2-5.5), les scénarios B de 5.6 et 5.7 et les scénarios A de 6.3.

## Livré

`content/scenarios/stash.B.yaml` et `content/scenarios/rebase.B.yaml`, `tracks: [llm, no_ai]`, même setup pour les deux parcours (empreintes dans `content/fingerprints.json`).

**stash.B** : l'agent a mis `au_revoir` de côté (« WIP : fonction au_revoir », op `stash`, dossier propre).
- `designer` (`designate`, accepte `commit`) : l'entrée du stash (`commit:<sha du stash>`, alias `@stash-agent`).
- `reprendre` (`repo_state`) : validée sur l'état réel, quel que soit le chemin (`stash pop`, ou `stash apply` + `commit -a`) : un commit après `depart`, sans fusion, index et arbre propres, `src/bonjour.py` contient `def au_revoir`. La pile peut garder l'entrée (`apply`).

**rebase.B** : l'agent a commité « Raccourcit le salut » sur `feature`, le collègue a changé la même ligne sur `main`, l'agent a récupéré (`fetch`) puis rebasé : le dépôt est au milieu d'un rebase en conflit (`agent_rebase_conflict`, `onto: origin/main`).
- `designer` : le commit en conflit (principal) ou le fichier `path:worktree:src/bonjour.py` (équivalent).
- `sortir` (`quiz`) : `git rebase --abort` (exécuté pour de bon par le quiz, comme tout quiz : `--skip` et `--continue` sont les mauvais choix, avec `effect_text`).
- `relancer` (`repo_state`, `in_progress: rebase`) : l'apprenant relance `git rebase origin/main` et retrouve le conflit.
- `resoudre` : mêmes conditions que `rebase.A` (6.3), réutilisées telles quelles : fin du rebase, HEAD sur `feature`, index propre, aucun marqueur, au moins deux commits après `depart`, sans fusion ; `foreseen` pour rebase en cours, marqueurs commités, fusion, rebase non abouti.

## Ajouts au code partagé

- Vue `staging` : nouveau groupe `stash` (`StagingItem`, `element_id` = `commit:<sha du stash>`, lettre `S`) ; le stash n'était visible nulle part dans l'interface, donc non désignable. Rendu dans la vue « Index » (section « Stash »), marqué `designable` par `mark_views`, pris en compte par `_exists` (la correction ne rejette plus un commit de stash), le panneau de désignation et les liens (`names`, `explain`).
- Aucune condition `repo_state` nouvelle.

## Reports

- Encart « Ce qui l'aurait bloqué » : non implémenté (décision d'Anaël).
- Un `git stash drop` suivi d'une réécriture à la main au contenu identique est accepté (même résultat, même commit de contenu) ; un contenu différent ne l'est pas.
- Le groupe « Stash » partage le titre « Index » de la section ; un titre propre et une CSS dédiée (`is-stash`) restent à faire.
- Contrôle dans un navigateur réel pour Anaël : section « Stash » de la vue Index et sa désignation.

## Tests

`tests/test_scenario_b_stash_rebase.py` (bout en bout en `slow`) : lint du contenu et vouvoiement, setup des deux scénarios dans les deux parcours, désignation juste, équivalente et fausse, `pop` + commit, `apply` + `commit -a`, contournements refusés (stash appliqué sans commit, `drop` puis contenu différent, `drop` + commit vide ; marqueurs, `--abort` puis fusion, `--skip`, abandon seul), quiz `--abort`/`--skip`. Empreintes : `tests/test_fingerprints.py`.
