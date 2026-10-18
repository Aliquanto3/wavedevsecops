---
story: "5.2"
key: 5-2-corriger-une-désignation-côté-serveur-en-un-seul-essai
title: Corriger une désignation côté serveur, en un seul essai
status: review
branch: story/5-2-designation-serveur
ad: [AD-2, AD-7, AD-14, AD-17, AD-1]
---

# Story 5.2 : Corriger une désignation côté serveur, en un seul essai

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.2 ».

## Livré

- Type d'étape `designate` (`scenarios/steps/designate.py`, un module du registre) : `question_text`, `accept` (types d'`element_id` acceptés), `slots` (`slot_id`, `label_text`, `answers` = ensemble de bonnes réponses en `@alias` du setup, `primary` = élément principal, dans `answers`). Les autres éléments de `answers` sont les équivalents. Validé au chargement : types connus, `primary` dans `answers`, alias définis par le setup (règle commune des alias).
- Marques `designable` (`engine/designation.mark_views`) : quand l'étape courante est une désignation, la projection marque `designable` tous les éléments (nœuds du graphe, étiquettes de refs, entrées de l'index) dont le type d'`element_id` est dans `accept`, `false` pour les autres, pas seulement les bonnes réponses. Hors désignation, tout reste désignable (valeur par défaut). Le projecteur du gestionnaire est enveloppé par `StepRunner.designating` (ouverture, réveil, changement externe). Quand l'étape change dans une opération (entrée ou sortie d'une désignation), le verdict porte `StepOutcome.views` et la file publie un dernier `state_projected` (avant `engine_state(repos)`) pour que les marques ne soient pas en retard d'une opération.
- Intention `answer_submit{slots: [element_id], step_id}` (`engine/designation.py`, enregistrée par l'application) : une opération `writes=False` de la file. Refus connus d'avance en 409 (`reason_text` français) et revérifiés dans la file : aucune désignation à cette étape, déjà répondu, nombre de cases, élément mal formé, type non accepté, élément absent du dépôt (commit, ref, tag ; les autres types, vérifiés par leur forme). Le corps corrige contre le `RepoState` courant, écrit `run.json["answers"][step_id]` (réponse, `correct`, charge de correction) puis émet `answer_corrected`. La validation d'étape ferme alors l'étape (`designate.check` : `passed` pour la réponse corrigée, juste ou fausse).
- Premier essai : le fait `quiz_first_attempt{correct}` (déjà géré par `progress` et le score du premier coup) est produit avec `step_validated` à partir de `run.json["answers"]` (`StepRunner._facts_of`), donc aussi au rejeu après un arrêt brutal. Aucun changement dans `progress/`.
- `GET /api/ws/<id>/resolve_sha?prefix=` (`web/workspaces.py`, logique dans `designation.resolve_sha`) : lecture seule sur la dernière projection, ne consomme pas l'essai.
- Événement `answer_corrected` typé dans le catalogue (`events/catalog.py`).
- Tests : `tests/test_designation.py` (vrai git et vrai serveur, 17 tests).

## Contrat pour 5.3 (désigner dans les vues) et 5.4 (liste ou SHA)

- **Panneau Scénario** : l'étape courante de type `designate` porte `designate: {question_text, accept: [type], slots: [{slot_id, label_text}]}` ; jamais les bonnes réponses. Hook générique `panel(step)` d'un module de type d'étape (même mécanisme que la story 4.5 : `StepType.panel`).
- **Désignables** : le front ne propose que les éléments dont `designable` vaut vrai dans `state_projected.views` (`graph.nodes[]`, `graph.nodes[].refs[]`, `staging.staged|unstaged|untracked[]`). Les lignes de diff, sorties et preuves non commit (`diffline`, `output`, `check`…) ne sont pas encore projetées : leurs vues porteront leur marque (stories suivantes) ; `accept` les nomme déjà.
- **Envoi** : `POST /api/ws/<id>/answer_submit` avec `{"slots": ["commit:<sha40>", …], "step_id": "<étape>"}`, un `element_id` par case, dans l'ordre des cases. `step_id` est obligatoire (revue) : sans lui, un double clic après la fermeture d'une étape s'appliquerait à la désignation suivante. 202 `{op_id}` ; 409 `{reason_text}` (refus ci-dessus, dont « Vous avez déjà répondu… » pour la seconde soumission) ; 422 pour un corps invalide (`slots` vide ou plus de 20, `step_id` absent).
- **Correction** : événement `answer_corrected{step_id, correct, summary_text, slots: [{slot_id, element_id, correct, equivalent, expected_element_id, accepted_element_ids, text}]}`. `correct` du total = toutes les cases justes. `equivalent` : juste mais autre que l'élément principal. `expected_element_id` est toujours l'élément principal, même après une réponse juste. Les textes (`text`, `summary_text`) sont écrits par le serveur, le front ne les compose pas. Ordre dans une même opération : `engine_state` → `op_started` → `answer_corrected` → `op_exit` → `state_projected` → `step_verdict` (`passed: true` : l'étape est close, pas « la réponse est juste ») → `step_explanation` → `progress_updated` → `state_projected` (marques de l'étape suivante, si elles changent) → `engine_state`.
- **Reprise** : après un rechargement, la correction n'est pas rejouée par le flux ; elle est dans `run.json["answers"][step_id]["payload"]` (même forme que l'événement). Le panneau ne l'expose pas encore (voir reports).
- **`resolve_sha`** : `GET /api/ws/<id>/resolve_sha?prefix=<hex, 7 à 40 caractères, casse libre>`. 200 `{element_id: "commit:<sha40>", sha, short_sha, subject, author_text, actor}` ; 422 préfixe trop court ou non hexadécimal ; 404 aucun commit ; 409 plusieurs commits. Chaque refus porte `reason_text` en français. 5.4 place `element_id` dans `answer_submit.slots`. Les commits perdus (reflog) comptent : ils sont désignables comme dans le graphe.

## Décisions

- Une seule réponse ferme l'étape, juste ou fausse : l'apprenant voit la correction et avance (« en un seul essai »). Le score du premier coup compte la désignation comme un quiz (`quiz_first_attempt`), ce que le docstring de `ScenarioProgress.first_try_score` prévoyait déjà.
- `run.json` d'abord, puis événement et faits : un arrêt entre l'écriture de la réponse et la fermeture de l'étape laisse l'étape courante avec une réponse consignée ; la soumission suivante termine la fermeture avec la correction consignée, sans corriger de nouveau (le premier essai n'est jamais remplacé).
- Le correcteur ne lit que la dernière projection publiée (la file est le seul écrivain : elle est à jour au début de l'opération).
- `answer_submit` est `writes=False` : il n'altère pas le dépôt. En `quiz_altered`, l'étape courante est le quiz (seul un mauvais choix y mène) : `_verify` refuse donc la désignation par « Aucune désignation n'est attendue ».
- Fichiers partagés touchés en ajout seulement : `StepType.panel` et la boucle du panneau (identiques à ceux de la story 4.5, pour un merge sans conflit), un champ `StepOutcome.views` et son bloc de publication dans `operations.py`, `_facts_of`/`validate` dans `steps.py`, une ligne dans `manager.py` (projecteur enveloppé), `AnswerCorrected` typé dans `catalog.py`.

## Reports

- Récupération de la correction après rechargement dans le panneau (étape `done` d'une désignation) : à exposer par 5.3 avec l'affichage de la correction.
- Recommencer (story 4.4) doit vider `run.json["answers"]` avec `validated` ; les faits du premier passage restent.
- Marques `designable` des vues Code et preuves non commit (diff, sorties d'outils, contrôles, revues, SBOM) : avec leurs vues.
- Vérification d'existence des éléments `path`, `diffline`, `pr`, `check`… à la soumission : forme seulement tant que la projection ne les porte pas.
- AD-17 (spine) nomme `answer_submit{slots}` : y ajouter `step_id`, devenu obligatoire à la revue (décision pour Anaël).

## Revue

Revue Opus du 2026-10-18, une passe, après rebase sur `origin/main` (story 4.5 incluse).

- medium · second avis M1 · corrigé · `answer_submit` sans `step_id`, parti après la fermeture d'une désignation, consommait l'unique essai de la désignation suivante : `step_id` est désormais obligatoire (422 sinon), tests mis à jour (moteur et HTTP).
- medium · second avis M2 · rejeté · `writes=False` ne contourne pas la garde `quiz_altered` en pratique : cet état n'existe qu'après un mauvais choix de quiz, l'étape courante reste le quiz et `_verify` refuse la désignation ; l'opération n'écrit que `run.json["answers"]`, jamais le dépôt.
- medium · second avis M3 · corrigé · rebase sur main : un seul conflit (`engine/steps.py`, `validate` et `panel`), résolu en gardant la version de 4.5 (`_quiz_facts`, `quiz_altered`, `restore_failed`) plus les marques de 5.2 ; `StepType.panel`, la boucle du panneau et `tests/test_steps.py` recopiés de 4.5 sont absorbés par main.
- low · second avis L4 · corrigé · test de rejeu instable : la veille précède la modification de `progress.json` et le test attend le rejeu, asynchrone dans le fil de l'espace.
- low · second avis L5 · rejeté · les assertions et le commentaire de `tests/test_steps.py` sont désormais ceux de main (4.5), le diff de 5.2 n'y touche plus.
- low · second avis L6 · corrigé · la seconde `state_projected` d'une même opération à la même empreinte relançait l'annonce du lecteur d'écran : `store.js` garde l'annonce déjà lue (même `op_id`, même empreinte) ; une commande suivante reste annoncée. Test Node ajouté.
- info · revue · rien à signaler · complexité : `mark_views` copie les vues une fois par projection (O(n)), aucun parcours de structure qui grossit à chaque événement. Complexité : 0 constat.

