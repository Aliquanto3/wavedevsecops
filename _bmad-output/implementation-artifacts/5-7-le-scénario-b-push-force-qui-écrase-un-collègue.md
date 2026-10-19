---
story: "5.7"
key: 5-7-le-scénario-b-push-force-qui-écrase-un-collègue
title: Le scénario B « push --force qui écrase un collègue »
status: review
branch: story/5-7-scenario-b-push-force
ad: [AD-7, AD-8, AD-2]
---

# Story 5.7 : Le scénario B « `push --force` qui écrase un collègue »

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.7 » ; FR-12. S'appuie sur `agent_push_force` (5.1), la désignation (5.2-5.5) et le scénario B de 5.6.

## Livré

`content/scenarios/push-pull.B.yaml`, `tracks: [llm, no_ai]`, même setup pour les deux parcours (empreinte `05e2098c…`).

- Setup : état propre de l'apprenant poussé ; le collègue pousse « Ajoute le guide de contribution » ; l'apprenant le récupère (`fetch`) ; l'agent force `origin/main` sur le départ avec « Ajoute les tests de bonjour » (`agent_push_force`) ; nouveau `fetch`. Résultat : `origin/main` (réelle et de suivi) porte le commit de l'agent, le commit du collègue n'est plus sur `origin` et, localement, plus aucune ref n'y mène : le graphe le projette « perdu · visible par reflog ». `main` local reste sur le départ.
- Étape `designer` (`designate`, accepte `commit`) : bonne réponse le commit du collègue (principal) ou le commit forcé de l'agent (équivalent déclaré) ; réponse fausse corrigée comme à l'ordinaire.
- Étape `restaurer` (nouveau type `origin_contains`) : validée quand le dépôt nu `origin.git` porte, sur sa branche, le commit du collègue et celui de l'agent. « Porte » : ancêtre de la branche (fusion, avance rapide) ou patch équivalent (`git cherry` : `rebase`). Jugée sur `origin.git`, pas sur la branche de suivi : seul un `push` abouti valide. Raisons d'échec écrites par le serveur (commits manquants cités, branche supprimée).
- Trois paliers d'indice par étape ; vouvoiement.

## Ajouts localisés au code partagé

- Op de setup `fetch` (module seul) : `git fetch` du dépôt de l'apprenant, rend le sommet d'`origin/<branch>` (alias de commit).
- Type d'étape `origin_contains` (module seul, lecture seule de `origin.git`).

## Reports

- Encart « Ce qui l'aurait bloqué » : non implémenté, en attente d'une décision d'Anaël (comme 5.6). Pour ce scénario : protection de branche (AD-8), station 2/3.
- Protection de `origin` (AD-8) : le scénario ne pose pas de protection ; une protection qui refuse le push forcé contredirait l'erreur de l'agent.
- `git cherry-pick` n'est pas dans la liste du terminal : la restauration enseignée passe par `git merge` (ou `rebase`).
- Un patch identique refait à la main (même fichier, même contenu) est accepté comme restauration ; un contenu différent ne l'est pas, ni un fichier du commit retiré après coup.
- Si `origin.git` était nettoyé (gc) des objets du commit écrasé, l'étape ne pourrait plus le comparer (échec fermé, jamais de validation à tort).
- Contrôle dans un navigateur réel pour Anaël : le commit en tirets dans le graphe et sa désignation.

## Tests

`tests/test_scenario_b_push_force.py` (19 tests, bout en bout en `slow`) : lint du contenu, setup dans les deux parcours (origin sans le commit du collègue, commit perdu cité par le reflog), désignation juste (principal, équivalent) et fausse, restauration par `merge` + `push` et par `rebase` + `push`, contournements refusés (push forcé de l'ancien sommet qui efface l'agent, intégration locale sans push, `fetch`/`pull` seuls, fichier refait avec un autre contenu, commit vide au même message, branche supprimée sur `origin`, fichier retiré après la fusion, lecture seule). Empreintes : `tests/test_fingerprints.py`.

## Revue

- medium · revue · corrigé : une fusion poussée suivie d'un `git rm` (ou d'un `revert`) du guide ou des tests de l'agent validait l'étape (les deux commits restaient ancêtres) ; `origin_contains` exige aussi que le sommet garde le travail de chaque commit (mêmes blobs pour les fichiers ajoutés ou modifiés, absence des supprimés). Tests `test_fusionner_puis_retirer_un_fichier_ne_valide_pas`.
- low · second avis 1 · corrigé : le test « branche supprimée » était vacueux (`git push origin :main` est refusé par `origin`, aucun verdict) ; la branche est retirée directement dans `origin.git` et le verdict « n'existe plus » est vérifié.
- low · second avis 2 · rejeté : « sans forcer » est un conseil de l'explication, pas une exigence de l'instruction ; un `push --force` d'une fusion qui garde les deux travaux laisse `origin` dans l'état demandé.
- low · second avis 3 · corrigé par le correctif medium : `git cherry` ignore les espaces, mais le contrôle des blobs refuse désormais un contenu qui diffère.
- low · second avis 4 · rejeté : `pending` silencieux et journalisé quand git est illisible, comme `history_clean` (5.6) ; un verdict d'échec sans cause apprenant serait trompeur.
- low · second avis 5 · rejeté : absence de protection AD-8 sur `origin` déclarée dans les reports (une protection contredirait le push forcé de l'agent).
- Complexité : 0 constat (contrôle borné par les commits déclarés et les fichiers qu'ils touchent).
