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
- Ops existantes (`switch`, `colleague_commit`, `push`, `commit`) et types d'étape `repo_state` et `quiz`.
- **Conditions ajoutées à `repo_state`** (revue, code partagé de la 4.1 ; optionnelles, rétrocompatibles, documentées dans la docstring du module) :
  - `head.contains`, `branches[].contains` : tel commit (`@alias`, ref, SHA) est accessible depuis HEAD ou la branche ;
  - `commits[].merges` : `false` = aucun commit de fusion parmi les commits comptés (historique linéaire), `true` = au moins un ;
  - `tree.markers_absent`, `tree.markers_present` : lignes de marqueurs de conflit (`<<<<<<<`, `|||||||`, `>>>>>>>` avec ou sans étiquette, `=======` seul) absentes ou présentes ;
  - `tree.contains` : `[{path, text}]`, le fichier contient le texte.
  Les conditions de contenu lisent l'arbre de travail via `ctx.layout.repo` (fins de ligne normalisées en LF, 1 Mio lu au plus, chemin relatif au dépôt imposé, cible résolue dans le dépôt) ; sans espace ou fichier absent, elles échouent (échec fermé).
- Tests `tests/test_scenarios_socle.py`, étendu aux huit scénarios : lint de contenu (consigne, explication, trois paliers dont un blanc, aucun avertissement, clés d'explication valides), chaque scénario joué de bout en bout dans les deux parcours (8 parties de plus) avec état final vérifié (fusion à deux parents, marqueurs absents, pile vide, historique de `feature` linéaire et origine réécrite, commit perdu puis plus en tirets), et les erreurs réalistes : `merge --abort`, `git add` avec marqueurs, `pull` refusé et `reset --hard` rattrapable, `stash drop`, `rebase --abort`, `push` refusé, `git log` à la place du reflog, `reset --mixed` qui laisse le fichier.

## Décisions

- Même setup pour les deux parcours (comme en 6.2) : les scénarios enseignent git sur le petit projet neutre ; les empreintes sont donc identiques pour `llm` et `no_ai`.
- Le conflit de « rebase » est provoqué par l'apprenant (`git rebase origin/main`), non par l'op `agent_rebase_conflict` : le rebase fait partie de ce qu'il apprend à lancer. Cette op reste destinée aux scénarios B.
- « stash » : le quiz joue le rôle de la mise de côté (la bonne réponse est exécutée par le quiz) ; la reprise est une étape sur état réel, pour accepter `pop` comme `apply` + `drop` (AD-7).
- « rebase » : l'étape de résolution exige deux commits depuis `@depart` sur `feature` ; un `rebase --abort` laisse un seul commit, donc n'est pas validé (foreseen dédié).
- « récupération » : pas de `push` dans le setup, sinon `origin/main` retiendrait le commit et il ne serait pas « perdu » (pas de tirets).
- Le texte du commit de fusion (`Fusionne feature`) est suggéré, jamais exigé. `git commit` exige `-m` dans le terminal (liste blanche, AD-4) ; `merge --continue` / `rebase --continue` passent sans éditeur (`GIT_EDITOR=:`).

## Reports

- **Identifiants** `conflit`, `stash`, `rebase`, `recuperation` : imposés par `SOCLE_ORDER`, en attente de validation d'Anaël ; un renommage touche les quatre fichiers, `SOCLE_ORDER`, `fingerprints.json` et `SOLUTIONS` du test.
- Les scénarios B correspondants (5.6 à 5.8) ne sont pas touchés. Relecture pédagogique du français (ton, vouvoiement, justesse des effets des mauvaises réponses) à faire par Anaël.

## Revue

Revue Opus (une passe), après rebase sur `origin/main` (sans conflit ; empreintes inchangées et stables sur deux générations : elles ne portent que sur le setup). Contournements du second avis tous reproduits par un test qui échoue sans les nouvelles conditions (8 tests « ne_valide_pas » de `tests/test_scenarios_socle.py`), conditions testées unitairement en LF et CRLF (`tests/test_steps.py`).

- High · second avis · corrigé · conflit, `resoudre` : `git add` d'un fichier encore marqué puis commit validait l'étape. `tree.markers_absent: [src/bonjour.py]` attendu, `foreseen` dédié (« contient encore des marqueurs ») ; `merges: true` en plus, car `merge --abort` puis deux commits ordinaires atteignaient aussi les trois commits.
- High · second avis · corrigé · rebase, `resoudre` : `rebase --abort` puis `merge` validait ; `commits[].merges: false` et `foreseen` qui indique le retour (`git reset --hard origin/feature`, puis rebase), chemin testé. Le cas « `git add` avec marqueurs + `rebase --continue` » existait aussi : `tree.markers_absent` et `foreseen` dédié.
- Medium · second avis · corrigé · récupération, `restaurer` : un nouveau commit au même sujet validait. Condition `head.contains: "@idee"` (le commit perdu lui-même) à la place du sujet ; `foreseen` dédié (« pas le commit perdu, toujours en tirets »).
- Medium · second avis · corrigé · stash, `reprendre` : `stash drop` puis réécriture validait. `tree.contains` exige la ligne mise de côté et le titre du collègue dans `README.md`. Réécrire exactement le même texte reste accepté : l'état est alors identique (AD-7).
- Medium · revue · corrigé · 6.2, `push-pull` / `recuperer` : un `docs/guide.md` créé et commité avec « guide » dans le message validait sans `pull` ; `head.contains: "@commit-collegue"`.
- Medium · revue · corrigé · 6.2, `pr-merge` / `recuperer_main` : un commit local « Merge pull request #1 from feature » validait ; `head.at: origin/main` (la `main` protégée de l'origine ne reçoit que le merge de la PR).
- Low · second avis · corrigé · récupération : l'explication proposait `git branch sauvetage <sha>`, que l'étape refuse (`main` doit retrouver le commit) ; remplacé par `git reset --hard <sha>`.
- Low · second avis · corrigé · premiers paliers de `perdre_le_commit` et `restaurer` reformulés (plus de sous-commande ni de syntaxe `HEAD@{n}`).
- Low · second avis · rejeté · paliers 2 `git add ___`, `git rebase ___` : la commande partielle est le principe du palier 2 (AD-7, 4.6) ; le blanc porte l'argument à trouver.
- Low · second avis · corrigé · explication du quiz `retrouver` : ne donne plus `HEAD@{1}`, réponse de l'étape suivante.
- 6.2, autres étapes `repo_state` relues (`add-commit`, `branche`, `push-pull` / `commiter_a_partager` et `pousser`, `pr-merge` / `commiter_sur_feature` et `pousser_feature`) : pas de contournement trouvé, l'état attendu y est le geste lui-même.
- Complexité : 0 constat (`contains` parcourt une fois les commits accessibles, contenu lu une fois par fichier et par jugement).
