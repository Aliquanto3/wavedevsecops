---
story: "6.3"
key: 6-3-les-scénarios-a-conflit-stash-rebase-et-récupération
title: Les scénarios A « conflit », « stash », « rebase » et « récupération »
status: review
branch: story/6-3-scenarios-a-avances
ad: [AD-7, AD-4, AD-2, AD-18]
---

# Story 6.3 : Les scénarios A « conflit », « stash », « rebase » et « récupération »

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 6.3 » ; FR-9, FR-11, FR-15, FR-16, UJ-2, SM-3 ; spine AD-7, AD-4, AD-2, AD-18. S'appuie sur le modèle de la 6.2 (format, quiz, indices), le collègue simulé (3.4), les actes de l'agent B (5.1 : `stash`), la validation d'étape (4.1), le quiz (4.5), les indices (4.6) et « Recommencer » (4.4).

## Livré

- Quatre scénarios `content/scenarios/<id>.A.yaml`, aux identifiants de `SOCLE_ORDER` (`conflit`, `stash`, `rebase`, `recuperation`), `tracks: [llm, no_ai]`, sans `section` ni `station`. Chaque étape a sa consigne, son explication (et une clé `explain_ref` quand le graphe a un mot à dire) et ses trois paliers d'indice, dont une commande partielle avec `___`. Le premier palier ne donne jamais la commande.
  - **conflit** (2 étapes) : le setup met `main` et `feature` en désaccord sur la même ligne de `src/bonjour.py` ; `git merge feature` s'arrête (`in_progress: merge`) ; l'apprenant résout les marqueurs dans la vue Code, puis `git add` et `git commit` terminent la fusion (état réel : plus d'opération en cours, index propre, trois commits depuis le départ). `foreseen` : fusion encore en cours, fusion abandonnée (`merge --abort`).
  - **stash** (3 étapes) : travail non commité dans `README.md` et commit du collègue sur le même fichier (un `pull` serait refusé). Quiz « ranger son travail » (`git stash` ; `pull` refusé ; `reset --hard` qui détruit le travail), `git pull`, puis reprise (`stash pop`, accepté aussi par `apply` puis `drop`, l'état faisant foi). Les deux modifications touchent des lignes distinctes : pas de conflit au `pop`.
  - **rebase** (4 étapes) : `feature` déjà poussée, le collègue a changé la même ligne sur `main`. `git fetch`, `git rebase origin/main` (conflit, `in_progress: rebase`), résolution puis `git rebase --continue` (historique linéaire, deux commits depuis le départ), quiz « pousser une branche réécrite » (`--force-with-lease` ; `push` refusé ; `--force` expliqué comme imprudent).
  - **recuperation** (3 étapes) : `git reset --hard HEAD~1` (le commit « Note une idée d'amélioration » n'est jamais poussé, donc réellement perdu), quiz `git reflog` (contre `git log` et `git stash list`), puis restauration par `git reset --hard HEAD@{1}` (toute autre position du reflog ou nouvelle branche + `reset` convient si `main` retrouve le commit). Le commit perdu est affiché en tirets (`lost`) du `reset` à la restauration.
- `content/fingerprints.json` : huit empreintes de plus (`scripts/update_fingerprints.py`), deux par scénario, stables sur deux générations.
- Aucun changement de code partagé : les ops (`switch`, `colleague_commit`, `push`, `commit`) et les types d'étape (`repo_state` avec `in_progress` et `stash`, `quiz`) suffisent.
- Tests `tests/test_scenarios_socle.py`, étendu aux huit scénarios : lint de contenu (consigne, explication, trois paliers dont un blanc, aucun avertissement, clés d'explication valides), chaque scénario joué de bout en bout dans les deux parcours (8 parties de plus) avec état final vérifié (fusion à deux parents, marqueurs absents, pile vide, historique de `feature` linéaire et origine réécrite, commit perdu puis plus en tirets), et les erreurs réalistes : `merge --abort`, `git add` avec marqueurs, `pull` refusé et `reset --hard` rattrapable, `stash drop`, `rebase --abort`, `push` refusé, `git log` à la place du reflog, `reset --mixed` qui laisse le fichier.

## Décisions

- Même setup pour les deux parcours (comme en 6.2) : les scénarios enseignent git sur le petit projet neutre ; les empreintes sont donc identiques pour `llm` et `no_ai`.
- Le conflit de « rebase » est provoqué par l'apprenant (`git rebase origin/main`), non par l'op `agent_rebase_conflict` : le rebase fait partie de ce qu'il apprend à lancer. Cette op reste destinée aux scénarios B.
- « stash » : le quiz joue le rôle de la mise de côté (la bonne réponse est exécutée par le quiz) ; la reprise est une étape sur état réel, pour accepter `pop` comme `apply` + `drop` (AD-7).
- « rebase » : l'étape de résolution exige deux commits depuis `@depart` sur `feature` ; un `rebase --abort` laisse un seul commit, donc n'est pas validé (foreseen dédié).
- « récupération » : pas de `push` dans le setup, sinon `origin/main` retiendrait le commit et il ne serait pas « perdu » (pas de tirets).
- Le texte du commit de fusion (`Fusionne feature`) est suggéré, jamais exigé. `git commit` exige `-m` dans le terminal (liste blanche, AD-4) ; `merge --continue` / `rebase --continue` passent sans éditeur (`GIT_EDITOR=:`).

## Reports

- **Marqueurs de conflit restants** : aucune condition de `repo_state` ne lit le contenu d'un fichier ; un `git add` d'un fichier avec marqueurs suivi de `git commit` valide l'étape « conflit ». Le test final vérifie l'absence de marqueurs, l'étape non. Une condition `tree.content_absent` serait un ajout au code partagé (4.1) : hors périmètre.
- **Identifiants** `conflit`, `stash`, `rebase`, `recuperation` : imposés par `SOCLE_ORDER`, en attente de validation d'Anaël ; un renommage touche les quatre fichiers, `SOCLE_ORDER`, `fingerprints.json` et `SOLUTIONS` du test.
- **Rebase vs fusion** : l'étape de résolution du rebase accepte aussi un historique à trois commits (fusion) si l'apprenant a quitté le rebase puis fusionné ; non bloquant, `lancer_le_rebase` ayant déjà exigé un rebase.
- Les scénarios B correspondants (5.6 à 5.8) ne sont pas touchés. Relecture pédagogique du français (ton, vouvoiement, justesse des effets des mauvaises réponses) à faire par Anaël.

## Revue

À faire (second avis, puis reviewer).
