---
story: "7.6"
key: 7-6-lire-le-même-pipeline-en-github-actions-jenkins-et-gitlab-ci
title: Lire le même pipeline en GitHub Actions, Jenkins et GitLab CI
status: review
branch: story/7-6-pipeline-trois-ci
ad: [AD-1, AD-2, AD-7, AD-10, AD-13]
---

# Story 7.6 : Lire le même pipeline en GitHub Actions, Jenkins et GitLab CI

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 7.6 » ; spine AD-10 (trois écritures dans le gabarit) et AD-7 ; FR-23, UX-DR21. Reprend le report de la 2.11 (les trois écritures « à livrer avec la story du pipeline qui fixe les `job_id` »).

## Livré

- **Les trois écritures dans les gabarits** (`content/exercise/no_ai/` et `content/exercise/llm/`, identiques) : `.github/workflows/ci.yml`, `Jenkinsfile`, `.gitlab-ci.yml`. Trois tâches l'une après l'autre (`ruff`, `pytest`, `gitleaks`), chacune encadrée par deux commentaires seuls sur leur ligne, `wds:job <job_id>` puis `wds:end` (`#` en YAML, `//` en Groovy). GitLab : une étape par tâche, car les tâches d'une même étape tournent en parallèle. Aucune URL, rien ne s'exécute. Les empreintes de référence des six scénarios qui posent le gabarit sont régénérées (`scripts/update_fingerprints.py`).
- **Module `ci.pipeline_files`** : `PIPELINE_FILES` (onglets GitHub Actions | Jenkins | GitLab CI), `job_ranges(file, texte, job_ids)` (plage de lignes de chaque tâche, balises exclues, « lignes x à y »), `read_pipeline_files(git, layout, head_sha, pipeline)` (contenu lu au SHA de tête dans `origin.git` par `git cat-file blob`, lecture seule). Une balise absente, non fermée, en double, une tâche vide, un fichier absent au SHA donnent un `Finding` (`pipeline_mark_missing`, `pipeline_mark_broken`, `pipeline_file_missing`, gravité `info`), jamais une exception. Une balise est un commentaire qui ne contient qu'elle : la phrase d'en-tête qui cite « wds:job » n'en est pas une.
- **Route `GET /api/ws/<id>/code/pipeline?pr=<n>`** (`web/code.py`, `pipeline_view`) : les trois fichiers au SHA de tête de la PR, la plage de chaque tâche de `pipeline.yaml` par onglet (`range_text`, `a11y_name_text`), les constats et une note non bloquante, « Lecture seule » et la phrase « rien ne s'exécute » (textes du serveur, AD-2). PR inconnue : 404 avec raison.
- **`CheckRow.in_pipeline`** (contrat, `projections.project(pipeline_jobs=)`, posé par `repo_projector` depuis `pipeline.yaml`) : « Voir dans le pipeline » n'est proposé que pour les checks dont le `job_id` est dans `content/pipeline.yaml`.
- **Front** : bouton « Voir dans le pipeline » sur le check (`remote.js`) ; `pipeline-focus.js` (lien Distant + PR → Code, sans file ni intention : le front ne fait que montrer) ; vue Code (`code.js`) : un mode « Pipeline » (ajouté au premier clic) avec `pipeline-tabs` (GitHub Actions | Jenkins | GitLab CI, `role="tablist"`), étiquette « Lecture seule », une pastille par tâche, les lignes de la tâche surlignées (fond et trait, pas la couleur seule), « lignes x à y » dans chaque onglet. Changer d'onglet ou de tâche ne relit rien et garde l'autre choix ; survoler ou focaliser un check éclaire ses lignes dans l'onglet ouvert. Styles dans `code.css`.
- **Rien ne s'exécute** : le fichier n'est lu que par `cat-file` ; la vue n'a ni éditeur ni saisie ; le terminal refuse `./Jenkinsfile`, `bash`, `sh`, `python`, `jenkins`, `gitlab-runner`, `act`, `gh workflow run` ; aucune intention ne prend un chemin ou une commande à lancer, le code d'exercice se lance sans argument.
- Tests : `tests/test_pipeline_files.py` (balises du gabarit pour les deux parcours, **chaque tâche de `pipeline.yaml` retrouvée dans les trois fichiers avec son libellé et la commande exacte `outil + argv humain` que `ci` lance, dans le même ordre**, plages, constats, SHA de tête contre `main`, `in_pipeline`, terminal et intentions, module en lecture seule, route sur le vrai serveur) et `tests/test_pipeline_tabs_dom.py` (Node : du check à l'onglet, tâche gardée entre onglets, survol et focus, balises absentes, PR inconnue, feuille de style).

## Décisions

- Les trois fichiers sont écrits à la main dans le gabarit, vérifiés par un test contre `pipeline.yaml` (plutôt que générés) : ce sont des fichiers que l'apprenant lit comme de vrais pipelines, avec leurs idiomes (`needs`, `stage`, `sh`).
- Les lignes de la tâche excluent les balises : « lignes 12 à 18 » désigne le contenu de la tâche.
- « Voir dans le pipeline » n'est ni une sélection ni une intention d'AD-17 : un canal de front à front (`pipeline-focus.js`), sans écriture ni file.
- Le bouton « Pipeline » du mode Code n'existe qu'après le premier « Voir dans le pipeline » (pas de bouton masqué dans l'ordre de tabulation).
- Les commandes citent `uv run …` pour ruff et pytest et `gitleaks …` tel quel : l'outil et les arguments du pipeline simulé s'y retrouvent mot pour mot.

## Reports

- Les volets repliés (petite fenêtre) ne s'ouvrent pas d'eux-mêmes sur « Voir dans le pipeline » : même limite que les liens fichier:ligne vers Code.
- Explication (`explanations.yaml`, 2.10) : aucune entrée ajoutée ici, à ajouter dans une story de contenu (2.10 est maintenant sur `main`, aucun critère de la 7.6 ne l'exige).
- Jobs `bandit`, `pip_audit`, `quality_gate` (8.1, 8.3, 8.4) et `secret_scan` (8.6) : chacun devra ajouter ses balises `wds:job` / `wds:end` dans les trois fichiers ; le test échoue tant qu'un `job_id` du pipeline manque dans l'un d'eux.
- Les empreintes de référence changent avec le gabarit : une story parallèle qui les régénère doit relancer `scripts/update_fingerprints.py` après fusion.
- La vue Code relit le pipeline à chaque changement de vues tant que le mode « Pipeline » est ouvert (comme le diff). Le survol d'un check retiré par un redessin est remis à zéro depuis la revue.

## À vérifier sur poste réel

1. Dans un navigateur : le surlignage (fond et trait à gauche) est lisible en thème clair et sombre ; « Lecture seule » est annoncé au lecteur d'écran à l'ouverture.
2. Clavier : Tab/flèches parcourent les onglets, les pastilles de tâche et le panneau de lignes (focalisable) ; le focus d'un check éclaire ses lignes.

## Revue

Rebasée sur `main` (36 commits : 2.10, 6.3, 5.4, 7.3, outillage des tests) ; conflits dans `code.js` (imports et état de `renderCode` : 2.10 et 7.6 gardés tous deux) et `fingerprints.json` (régénéré, stable sur deux passes).

- low · second avis 1 · corrigé · `code/pipeline` : un `content/pipeline.yaml` illisible (`PipelineError`) répond 409 avec sa cause, plus 404 comme une PR absente (test de route ajouté).
- low · second avis 2 · corrigé · `remote.js` : un check survolé retiré par un redessin (sans `mouseout`) éteint son éclairage à la fin de `draw` (test DOM ajouté).
- low · second avis 3 · corrigé · `Jenkinsfile` : un commentaire dit que uv doit être installé sur l'agent, comme gitleaks (GitHub Actions et GitLab CI l'installent).
- low · second avis 4 · corrigé · concordance : la commande `outil + human` doit figurer sur une ligne non commentée de la tâche (test du filtre ajouté).
- low · revue · corrigé · contrat des jobs à venir (8.1, 8.3, 8.4, 8.6) : message d'échec du test de concordance qui dit la règle (6 fichiers, ordre de `pipeline.yaml`, balises, libellé, commande) et rappel dans l'en-tête de `content/pipeline.yaml`.
- low · revue · rejeté · `repo_projector` relit `pipeline.yaml` à chaque projection : petit fichier, même coût que les autres lectures de la projection ; pas de structure qui grossit.
- Complexité : 0 constat (le surlignage parcourt les lignes du fichier affiché, plafonné à 200 Ko ; aucun historique qui grossit).
