---
story: "4.1"
key: 4-1-valider-une-étape-sur-l-état-réel-du-dépôt
title: Valider une étape sur l'état réel du dépôt
status: review
branch: story/4-1-validation-etape
ad: [AD-1, AD-2, AD-7, AD-17]
---

# Story 4.1 : Valider une étape sur l'état réel du dépôt

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 4.1 ».

## Livré

- `scenarios/steps/` (registre des types d'étape, par découverte de modules comme `scenarios/ops/`) : un module par type, avec `Args` (sous-classe de `StepArgs`, `type: Literal["<nom>"]`) et `check(state: RepoState, ctx: StepContext) -> Verdict`. `StepArgs` porte les champs communs (`step_id`, `type`, `title_text`, `instruction_text`, `explanation_text`, `explain_ref`, `unexpected_text`) et `references()` (les `@alias` de l'étape, hors champs `_text`). `Verdict{status: passed|pending|failed|unexpected, reason_text, expected_text, observed[{text, element_id}]}`. `StepContext{step, aliases, previous}`.
- Premier type `repo_state` : `expect` (toutes les conditions nécessaires) et `foreseen` (états prévus mais insuffisants, avec leur `reason_text`). Conditions : `head` (`branch`, `detached`, `at`), `branches` (`name`, `exists`, `at`), `tags` (`name`, `exists`, `annotated`), `commits` (`on`, `ahead_of`, `min`, `subject_contains`), `index` (`staged`, `unstaged`, `untracked`, `tracked`, `clean`), `tree` (`present`, `absent`), `stash` (`count`, `min`, `message_contains`), `in_progress`. Les noms, refs et commits acceptent `@alias` (résolus par `run.json.aliases`). La validation ne lit que le `RepoState` : `git switch -c`, `git checkout -b`, `git branch` puis `git switch` donnent le même état, donc le même verdict.
- `Scenario.steps` : union discriminée par `type` (`step_union()`), `StepSpec` en est l'alias. Règles entre champs : `@alias` d'une étape défini par le setup, `explain_ref` connu (si `explain_keys` est fourni), `step_id` unique ; message « type d'étape inconnu » nommant les types connus.
- `engine/steps.py` : `StepRunner.validate(ctx, projection) -> StepOutcome | None`, branché par défaut dans `WorkspaceManager` (le paramètre `validator` reste surchargeable). Étape courante = `run.json.step_id` ; une réussite le fait passer à l'étape suivante (`null` après la dernière) ; le scénario est relu quand son fichier change (`mtime`, taille). `StepRunner.panel(engine)` : panneau Scénario écrit par le serveur, ajouté à `GET /api/ws/<id>/state` sous `step_panel` (titre, mode et son texte, étapes avec consigne, état `done|current|todo`, explication des seules étapes réussies).
- `engine/operations.py` : `OpContext.before_views` (vues d'avant l'opération), `StepOutcome.explained(...)` (seule la file nomme `StepExplanation`, règle d'AD-1 préservée), paramètre `panel` du moteur. Ordre inchangé : `… op_exit → state_projected → step_verdict → step_explanation → engine_state(repos)`.
- `events` : `StepVerdict` reçoit `status` (déduit de `passed` s'il manque), `expected_text`, `observed[StepObserved{text, element_id}]`, `next_step_id` (ajouts, valeurs par défaut).
- Front : `scenario.js` (contenu du panneau : `mode-badge` + « i », `step-progress` « Étape n sur N » avec segments, consigne, `step-explanation`, `notice-card` « État inattendu » avec attendu, ce que l'étape voit (boutons liés), explication et « Continuer ») ; `store.js` garde `stepPanel` et `verdict` (applique `step_verdict`/`step_explanation` avec `next_step_id` fourni par le serveur) ; `workspace.js` monte le contenu entre le titre et la région `role="status"`, qui reprend « Étape réussie. », la raison d'un état prévu ou « État inattendu. », puis « Étape n sur N : titre ». CSS ajouté à `workspace.css` (jetons seulement).
- Tests : `test_steps.py` (vrai git : étape réussie par `switch -c` et par `checkout -b`, ordre exact des 8 événements, suite des étapes jusqu'à la fin, état prévu, état inattendu avec liens, commande de lecture sans verdict, `step_id` stable quand les étapes sont réordonnées, panneau sans explication d'étape non réussie, sandbox sans étape ; conditions sur états synthétiques ; lint de contenu : type inconnu, alias, clé d'explication, `step_id` en double et invalide ; le moteur ne nomme aucun type) ; `test_scenario_panel_dom.py` (Node sur la doublure de DOM : ordre, progression, bouton « i », réussite puis explication, segment qui rouvre sa consigne, encart et « Continuer », pas de redessin sur un événement sans rapport).

## Décisions

- Quatre issues pour `check` : `passed`, `failed` (un `foreseen` correspond : la raison de l'auteur s'affiche dans la région de statut), `unexpected` (l'état a bougé, ni attendu ni prévu : encart) et `pending` (l'état est identique à celui d'avant l'opération : `git status`, `git log`… ne produisent aucun événement). Sans cette dernière, toute commande de lecture ouvrirait l'encart.
- « Continuer » écarte l'encart côté front (choix d'affichage, rien n'est calculé) ; l'étape reste ouverte et chaque opération suivante la revalide. Rien n'est bloqué.
- Une étape sans `foreseen` ne produit jamais `failed` : un pas intermédiaire licite (`git add` avant `git commit`) qui change l'état sans être attendu ouvre l'encart. À l'auteur de déclarer ces états dans `foreseen` pour les éviter ; le lint de contenu ne peut pas le deviner.
- La progression est la seule donnée de `run.json` (`step_id`) ; l'état `done|current|todo` est dérivé de la position de l'étape courante. Les faits du premier passage (essais, indices, score) sont à la story 4.2 : le `step_id` est la clé qu'elle citera.
- Le chargeur n'importe pas `projections` (cycle) : le lint des clés d'explication reçoit `explain_keys` (`parse_scenario`, `load_scenario`) ; le test de lint les passe depuis `projections.EXPLAIN_REFS`. Il n'y a pas encore de `content/explanations.yaml` : à brancher quand il existera.
- Aucun scénario du dépôt ne déclare encore d'étape (les 3 YAML ont `steps: []`) : le comportement est exercé par des scénarios de test. Les 8 scénarios du mode A sont écrits avec l'Epic 5.

## Reports

- `content/explanations.yaml` et la vérification de `explain_ref` contre ce fichier (aujourd'hui : `EXPLAIN_REFS`, via le test de lint).
- Boutons « Recommencer » et « Ouvrir un indice » de l'encart : avec leurs stories (4.4, 4.5) ; `onSelect` des liens de l'encart est branché sur la sélection d'éléments de la 2.7 (aujourd'hui sans effet dans l'application).
- Faits du premier passage et score (4.2), types `quiz_choice` et désignation (4.3 et suivantes), bilan de fin de scénario.
- Écart 2.6 toujours ouvert : `store.js` `acceptViews` attend `views[pane].elements` ; le panneau Scénario n'en dépend pas (il lit `step_panel`, `step_verdict`, `step_explanation`). À aligner en 2.7.
- Redessin du panneau : seulement quand `stepPanel` ou `verdict` change (le focus d'un segment survit aux événements sans rapport).

## À voir dans un vrai navigateur

- Mise en page du panneau de 440 px (segments qui passent à la ligne, encart, bouton « i »), contraste des jetons `warning`, focus visible sur les segments et « Continuer », annonce de la région `role="status"` au lecteur d'écran.
