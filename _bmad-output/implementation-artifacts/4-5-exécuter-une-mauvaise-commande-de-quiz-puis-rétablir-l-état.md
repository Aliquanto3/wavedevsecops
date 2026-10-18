---
story: "4.5"
key: 4-5-exécuter-une-mauvaise-commande-de-quiz-puis-rétablir-l-état
title: Exécuter une mauvaise commande de quiz, puis rétablir l'état
status: review
branch: story/4-5-quiz-retablir
ad: [AD-1, AD-4, AD-6, AD-14, AD-17]
---

# Story 4.5 : Exécuter une mauvaise commande de quiz, puis rétablir l'état

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 4.5 » ; FR-15, SM-C1, UX-DR9 à UX-DR11, UX-DR37 ; spine AD-1, AD-4, AD-6, AD-14. S'appuie sur l'API des instantanés de la 4.3 (inchangée), le terminal de la 2.4 et la validation d'étape de la 4.1.

## Livré

- **Type d'étape `quiz`** (`scenarios/steps/quiz.py`, un module de plus au registre AD-7 : ni le moteur ni le chargeur ne le citent). `choices[]` : `choice_id`, `command_text` (ligne tapée, avec `git`), `correct` (exactement une bonne réponse, `choice_id` uniques) et `effect_text` (ce que fait une mauvaise commande ; avertissement de lint s'il manque). `check` lit l'intention `quiz_choice` et `ctx.data["quiz_choice"]` : bonne réponse → `passed` (l'étape suivante s'ouvre, son explication est publiée) ; mauvaise → `failed` avec `effect_text` ; toute autre opération → `pending`. Le registre accepte une fonction `panel(step)` optionnelle : champs que le type ajoute à l'étape courante du panneau (le quiz y met `quiz.choices[{choice_id, command_text}]`, jamais `correct`).
- **Intention `quiz_choice {choice_id}`** (`terminal/quiz.py`, enregistrée avec le terminal). Refus à la soumission : étape qui n'est pas un quiz, choix inconnu, commande refusée par la liste blanche (erreur d'auteur). Dans la file, l'opération (`writes=True`, état `command`) : `take_snapshot(reason="quiz")` avant tout ; `run.json` reçoit `quiz_first[step_id]` (premier choix, jamais écrasé) et, pour une mauvaise réponse, `quiz{step_id, choice_id, command_text, explanation_text, snapshot_id}` **avant** la commande ; la commande est répétée dans le terminal (`terminal_output`, flux `input`, ajouté à `Stream`) puis exécutée par le `_run_git` de `terminal_line` (même garde, mêmes crochets, même sortie en flux). Une mauvaise réponse passe l'espace en `quiz_altered` (`set_rest_state`) et publie `quiz_altered{step_id, choice_id, command_text, explanation_text, first_attempt}`.
- **Intention `restore_state {}`** (même module). Lit `run.json.quiz`, refuse s'il n'y a rien à rétablir, sinon rend `restore_operation(snapshot_id)` de la 4.3 (`writes=False` : admise en `quiz_altered`). `_verify` de la 4.3 efface désormais aussi `quiz` (une ligne) : le rétablissement réussi, y compris la reprise au démarrage, quitte `quiz_altered` et l'empreinte égale celle d'avant le choix.
- **Moteur** (`engine/operations.py`) : `rest_state` public ; à l'ouverture, `run.json.quiz` remet l'espace en `quiz_altered` (un arrêt en plein quiz ne rend pas l'espace en `idle`) ; refus d'une écriture en `quiz_altered` par « Refusée pendant l'état modifié par le quiz : seules les commandes de lecture passent… » (terminal, et donc aussi la future vue Code, qui passe par la même file).
- **Point H2 de la 4.3 traité** : tant que `run.json.restore_failed` est posé, toute opération d'écriture est refusée (« L'état n'a pas pu être rétabli… Recommencez le scénario. »), sauf l'intention `restart` (4.4) et les opérations de `setup`. Les lectures (terminal en lecture, restauration) passent. La 4.4 n'a qu'à effacer `restore_failed` en reconstruisant l'espace.
- **Panneau Scénario** (`engine/steps.py`) : `quiz_altered` (quiz en attente, sans l'identifiant d'instantané) et `restore_failed{reason_text}` en plus des étapes ; ainsi un rechargement de page retrouve le bandeau ou l'encart d'erreur.
- **Front** (`web/static/js/quiz.js`, `store.js`, `scenario.js`, `workspace.js`, `workspace.css`) : groupe radio à une carte par commande ; « Exécuter ma réponse » inactif (`aria-disabled` + raison visible reliée) tant que rien n'est coché (« Choisissez une commande. »), pendant une action et pendant l'état modifié ; `quiz-banner` au-dessus des vues (« État modifié par le quiz — <commande> », « J'ai compris, rétablir l'état »), qui prend le focus à son apparition ; explication de la mauvaise réponse dans le panneau ; pendant `restoring` : « Rétablissement de l'état… » et vues `inert` ; à la fin, bandeau retiré, focus sur le panneau, annonce « Rétabli. » dans la région `role="status"` du panneau ; échec : `notice-card` d'erreur en `role="alert"` (texte de l'AC, seule action « Recommencer » qui poste `restart`). Le front ne juge rien : textes et verdicts viennent du serveur.
- Tests : `tests/test_quiz.py` (vrai git : panneau sans bonne réponse, mauvaise réponse puis état modifié, refus d'écritures et lectures admises, empreinte identique après rétablissement, bonne réponse, premier essai, réouverture en `quiz_altered`, `restore_failed` sans écriture, refus de choix invalides, validation du type) ; `tests/test_quiz_dom.py` (Node, doublure de DOM : bouton inactif, bandeau et focus, `inert`, annonces, échec et « Recommencer », rechargement). Réalignés : `tests/test_steps.py` (les erreurs de type d'étape portent sur l'étape entière dès qu'il y a deux types), `tests/test_terminal.py` (nouveau texte de refus).

## Décisions

- Le quiz vit dans `terminal/` (il réutilise `_run_git`, la garde et la liste blanche) : `engine` n'importe pas `terminal`, et `restore_state` n'a pas besoin d'un module à part.
- `quiz` est consigné dans `run.json` avant la commande, pas après : un arrêt entre les deux laisse un quiz à rétablir plutôt qu'un état modifié sans bandeau.
- `restore_failed` ne devient pas un état du moteur (AD-1 en fixe la liste) : c'est une clé de `run.json`, lue par la file pour refuser les écritures.
- Le premier essai (AD-14) est consigné dans `run.json.quiz_first` par le choix, porté par `quiz_altered.first_attempt`, puis enregistré comme fait `quiz_first_attempt{correct}` de `progress.json` (story 4.2) : `StepRunner.validate` ajoute le brouillon au verdict (juste ou faux), `StepRunner.replay` le rejoue au réveil depuis `run.json.quiz_first`. Le magasin garde le premier fait par étape, y compris après un Recommencer qui viderait `quiz_first`.

## Reports

- Recommencer (4.4) : enregistrer l'intention `restart` (exemptée des refus `restore_failed` et `quiz_altered`), effacer `restore_failed`, `quiz` et `quiz_first` à la reconstruction et remettre l'état de repos à `idle` (`ctx.set_rest_state("idle")`) : après un rétablissement échoué, l'espace reste en `quiz_altered`. Le bouton « Recommencer » de l'encart poste déjà `restart` ; sans l'intention, le serveur répond 404 et le texte s'affiche dans la zone d'erreur.
- Marque « Rétabli » sur les éléments des vues : la projection la porte déjà (`restored`, `a11y_name_text`) ; son rendu visuel revient aux vues concernées (graphe). Ici, l'annonce « Rétabli. » est dans le panneau.
- Terminal en lecture seule (`aria-readonly`) pendant l'état modifié (UX-DR10) : non appliqué, car l'AC de la story veut que le terminal accepte les commandes de lecture ; le serveur refuse les autres.
- Vue Code : ses écritures seront refusées par la même règle de file dès qu'elle soumettra des opérations `writes=True`.
- Aucun scénario de `content/scenarios/` ne contient encore d'étape `quiz` : les scénarios des épics suivants les déclarent.

## Revue

Reviewer (Opus), après rebase sur `origin/main` (4.2, 3.2, 6.6, 2.7, 2.5). Conflits d'ajout seulement : `store.js` (`announce` et `restored` gardés) et `workspace.js` (annonce de la 2.7 suivie du statut, où `quizStatus` passe avant le statut d'étape ; bandeau du quiz mis à jour à chaque état).

- high, second avis H1 : « Recommencer » refusée après `restore_failed` (garde `quiz_altered` toujours active). Corrigé : `restart` exemptée des deux refus (`_write_refusal`) ; test `test_un_vrai_retablissement_echoue_laisse_recommencer_seulement` sur un vrai échec (manifeste d'instantané retiré).
- high, second avis H2 : deux `quiz_choice` en file passaient la garde (vérifiée à la soumission seulement). Corrigé : la garde d'écriture est revérifiée à l'exécution (`app_error` « Refusée pendant l'état modifié par le quiz… »), et le choix a un `precheck` (étape toujours en cours, aucun quiz en attente). Couvre aussi une ligne de terminal en écriture placée derrière un mauvais choix. Tests `test_deux_choix_envoyes_d_affilee_n_en_executent_qu_un`, `test_une_ecriture_en_file_derriere_un_mauvais_choix_est_refusee`.
- medium, second avis M3 : `run.json.quiz` posé mais repos `idle` si git lève. Corrigé : `set_rest_state` avant la commande, `quiz_altered` publié dans un `finally` ; test `test_un_git_en_echec_laisse_l_etat_modifie_coherent`.
- medium, second avis M4 : « score du premier coup conservé » sans écriture dans `progress.json`. Corrigé : fait `quiz_first_attempt` (voir Décisions) ; tests dans `test_seul_le_premier_essai_est_retenu` et `test_le_premier_essai_est_rejoue_au_reveil`.
- medium, second avis M5 : vrai `restore_failed` et soumissions concurrentes non testés. Corrigé par les tests ci-dessus (les six nouveaux tests échouent sur le code d'avant la revue).
- low, second avis L6 : `restore_state` admis après `restore_failed`. Corrigé (l'AC ne laisse que « Recommencer ») : refus à la construction.
- low, second avis L7 : exemption des opérations `setup`. Rejeté : saine, l'installation reconstruit l'espace.
- low, second avis L8 : une écriture déclarée `writes=False` contournerait la garde. Rejeté : le drapeau est la déclaration de l'opération (AD-1), posé par `parse_line` pour le terminal ; pas de cas réel.
- low, Complexité, reviewer : `_write_refusal` relit `run.json` à la soumission et à l'exécution de chaque écriture (quelques Ko, O(1) par opération) ; `_quiz_facts` parcourt `quiz_first`, borné par le nombre d'étapes. Aucun parcours d'une structure qui grossit : rien à corriger. Complexité : 0 constat à impact.
