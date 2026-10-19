---
story: "6.2"
key: 6-2-les-scénarios-a-add-commit-push-pull-branche-et-pr-merge
title: Les scénarios A « add / commit », « push / pull », « branche » et « PR / merge »
status: review
branch: story/6-2-scenarios-a-socle
ad: [AD-7, AD-8, AD-18]
---

# Story 6.2 : Les scénarios A « add / commit », « push / pull », « branche » et « PR / merge »

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 6.2 » ; FR-9, FR-11, FR-15, FR-16, UJ-1, SM-C1 ; spine AD-7, AD-8, AD-18. S'appuie sur le format des scénarios (2.1), la validation d'étape (4.1), le quiz (4.5), les indices (4.6), le bilan (4.7), la PR et le collègue simulé (3.1, 3.2, 3.4) et le catalogue (6.1).

## Livré

- Quatre scénarios `content/scenarios/<id>.A.yaml`, aux identifiants de `SOCLE_ORDER` (`add-commit`, `push-pull`, `branche`, `pr-merge`), `tracks: [llm, no_ai]`, sans `section` (socle git) ni `station`. Chaque étape a sa consigne, son explication (et, quand le graphe a un mot à dire, sa clé `explain_ref`) et ses trois paliers d'indice, dont une commande partielle avec `___`.
  - **add-commit** (4 étapes) : indexer un fichier neuf, commiter, quiz « corriger le message » (`--amend` contre `reset --hard` et `revert`), second commit sur un fichier suivi.
  - **push-pull** (4 étapes) : quiz « voir sans intégrer » (`fetch`), `git pull` du commit du collègue simulé (`colleague_commit` posé par le setup), commit local, `git push`.
  - **branche** (5 étapes, trois quiz) : créer `feature`, commiter dessus, quiz « revenir sur main » (où `git reset --hard HEAD~1` est l'erreur réaliste du Flow 1), quiz « fusionner », quiz « supprimer la branche ».
  - **pr-merge** (5 étapes) : commit sur `feature`, `git push -u origin feature`, ouverture de la PR, merge, `git switch main` + `git pull`. Le setup protège `main` (une approbation requise) et déclare la réaction du collègue (commentaire puis approbation à l'ouverture de la PR de `feature`).
- Nouveau type d'étape `pr_state` (`scenarios/steps/pr_state.py`) : l'état d'une PR n'est pas dans le `RepoState`, aucun type existant ne pouvait valider « PR ouverte » ni « PR mergée ». Il lit le GitHub simulé de l'espace (`head`, `base`, `pr_state: open|merged`, `min_approvals`) ; sans PR correspondante, `pending` (jamais d'échec).
- Ajout localisé au code partagé : `StepContext.layout` (champ optionnel, `None` par défaut) renseigné par `engine/steps.py` (une ligne), pour que `pr_state` atteigne l'espace sans que le moteur connaisse le type.
- `content/fingerprints.json` : huit empreintes de plus (`scripts/update_fingerprints.py`), deux par scénario.
- Tests `tests/test_scenarios_socle.py` : lint de contenu (consigne, explication, trois paliers dont un blanc `___`, aucun avertissement, clés d'explication valides, identifiants dans `SOCLE_ORDER`), exigences propres à chaque scénario (collègue, trois quiz et `reset --hard HEAD~1`, PR/revue), et chaque scénario joué de bout en bout dans les deux parcours (8 parties) : setup, commande ou choix par la file, verdict `passed` de chaque étape, étape suivante, état final, bilan sans indice et score. Trois cas d'erreur : mauvaise réponse du Flow 1 puis `restore_state`, `pull` mauvaise réponse du premier quiz, PR approuvée avant le merge.

## Décisions

- Le setup est le même pour les deux parcours : un scénario n'a qu'un `setup`, et l'op `exercise_stage` refuse le stade d'un autre parcours. Les scénarios enseignent git sur un petit projet neutre (README, `bonjour.py`) ; le code d'exercice des gabarits sert les scénarios des stations. Les deux parcours ont donc les mêmes empreintes.
- Un scénario sans `station` ni `section` : il reste dans « Socle git » (6.1), l'ordre venant de `SOCLE_ORDER`.
- Le verdict de l'étape « ouvrir la PR » ne dit rien tant que la PR manque (comme `repo_state` sans changement) : l'apprenant lit la consigne et les indices.
- La revue du collègue n'a pas d'étape propre : elle arrive à l'ouverture de la PR (réaction `pr_opened`) et la consigne du merge demande de la lire ; la protection de `main` rend l'approbation nécessaire.
- Clés YAML : `on` s'écrit `"on"` (YAML 1.1 en fait un booléen).

## Reports

- **Texte de l'interface de PR** : les consignes et indices des étapes « ouvrir la PR » et « merger » parlent de la « vue Distant » (story 3.3, en intégration). À réaligner sur les libellés réels des boutons une fois 3.3 fusionnée.
- **Identifiants** `add-commit`, `push-pull`, `branche`, `pr-merge` : imposés, en attente de validation d'Anaël ; un renommage touche les quatre fichiers, `SOCLE_ORDER`, `fingerprints.json` et `SOLUTIONS` du test.
- **Setup par parcours** : si le contenu doit un jour s'appuyer sur le code d'exercice dans ces scénarios, il faudra une op conditionnelle au parcours (modèle partagé) : hors périmètre.
- Les scénarios B correspondants et les quatre suivants (6.3) ne sont pas livrés ici.
- Relecture pédagogique du français (ton, vouvoiement, justesse des effets des mauvaises réponses) à faire par Anaël ; les effets décrits ont été vérifiés en jouant les mauvaises réponses de `reset --hard` et `pull`.
