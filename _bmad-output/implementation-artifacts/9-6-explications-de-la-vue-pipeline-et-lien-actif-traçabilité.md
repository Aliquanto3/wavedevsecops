---
story: "9.6"
key: 9-6-explications-de-la-vue-pipeline-et-lien-actif-traçabilité
title: Explications de la vue pipeline et lien actif Traçabilité
status: review
branch: story/9-6-explications-pipeline
ad: [AD-2, AD-7]
---

# Story 9.6 : Explications de la vue pipeline et lien actif Traçabilité

Source : `epics.md`, section « Story 9.6 » ; FR-5, FR-33, UX-DR33 ; complète 9.4 (critère « traçabilité ») et 2.10 (`explain-popover`).

## Livré

- Contenu (AD-7) : sept entrées `pipeline.<job_id>` (ruff, pytest, gitleaks, bandit, pip_audit, uv_lock, quality_gate) en bloc contigu à la fin de `content/explanations.yaml`, de deux ou trois phrases, avec `barrier_id` de la barrière que le job prouve et des termes `[[…]]` du vocabulaire. `pipeline.yaml` et les gabarits ne bougent pas : la clé se déduit du `job_id`.
- Projection (AD-2) : `pipeline_explain_ref(job_id, défaut)` (`projections/views.py`) ; `PIPELINE_JOB_IDS` et les sept clés rejoignent `EXPLAIN_REFS`. `annotate` (`links.py`) porte la clé sur le check et sur son bloc de sortie (`output:check-…`, nommé « sortie <job> (PR n°N) ») ; un check hors pipeline garde `remote.check`. `GET …/code/pipeline` ajoute `explain_ref` à chaque tâche.
- Lint : `test_links` exige déjà que le catalogue couvre exactement `EXPLAIN_REFS` (une clé projetée sans entrée, ou l'inverse, échoue) ; `test_pipeline_explain` aligne `PIPELINE_JOB_IDS` sur `content/pipeline.yaml`.
- Front : `explain.js` pose un « i » à la suite de chaque tâche de la vue pipeline (`data-explain-ref` posé par `code.js`, `.pipeline-job-item` en flex). Le texte vient du catalogue, écrit en `textContent` (aucun `innerHTML`).
- Traçabilité (`web/glossary.py`, `glossary.js`) : `trace_link_text` et `trace_none_text` rejoignent `trace_text` (les trois vont ensemble). `GET /api/glossary` donne `trace` : lien `/espace/<id>` si le dernier scénario ouvert est de station (1 à 4) et que son espace existe encore, sinon `link: null` et la phrase qui invite à ouvrir un scénario de station. Jamais de lien mort.
- Tests : `tests/test_pipeline_explain.py` (clés, lien et phrase, route sans espace), `test_pipeline_tabs_dom` (« i » des tâches, clé de check et de sortie), `test_glossary` (rendu du lien et de la phrase sous Node).

## Décisions

- Une seule entrée par job sert la tâche, le check et la sortie : elle dit ce que le job vérifie et comment lire son échec. Trois familles d'entrées par job (21) auraient dupliqué le texte.
- « Espace ouvert » = dernier scénario ouvert (`progress.json`, `last_opened`) dont l'espace existe sur disque. Seul un scénario de station a des PR et des checks ; un scénario du socle donne la phrase.
- Le lien mène à `/espace/<id>?vue=remote` : l'espace s'ouvre sur la vue Distant + PR (réaffichée si masquée ou repliée, titre au focus ; `mountWorkspace({ initialPane })`, lu par `main.js`). Arbitrage d'Anaël du 2026-10-19, appliqué en revue.
- Seul un scénario de station avec `pipeline: true` donne le lien (station 1 et `push-direct-main` n'ont ni PR ni checks) ; sinon la phrase.

## Reports

- À vérifier dans un navigateur : « i » à côté des pastilles de tâche (vue Code, onglet Pipeline), popover au-dessus du panneau, lien et phrase de « Traçabilité » sur la page Vocabulaire avec et sans espace de station ouvert, arrivée sur la vue Distant + PR (titre au focus, aussi sous 1280 px), lecture NVDA.
- Fusion avec 8.6 : son entrée « revue humaine » en fin d'`explanations.yaml` s'ajoute après le bloc `pipeline.*` ; sa clé doit aussi rejoindre `EXPLAIN_REFS`.

## Revue

Revue Opus du 2026-10-19, une passe, sur la branche rebasée sur `main` (f917b1a).

- medium · second avis 1 · corrigé : le lien était posé pour tout scénario de station, y compris ceux sans PR ni checks (`bac-a-sable-libre`, `defaut-de-lint`, `secret-dans-un-commit`, `test-casse`, `push-direct-main`). Condition `station and pipeline` ; `trace_none_text` reformulé en conséquence (« Aucun espace ouvert n'a de PR ni de checks… »).
- medium · arbitrage d'Anaël / second avis 2 · corrigé : le lien menait à l'espace, pas à la vue Distant + PR. `?vue=remote` et `initialPane` dans `workspace.js` (`showById`, déjà utilisé par les puces) ; test DOM sous 1280 px, vue masquée et vue inconnue.
- medium · second avis 3 · corrigé : `progress.json` illisible ou parcours invalide faisait lever `UnreadableDataError` ou `WorkspaceNotFound`, donc `/api/glossary` en 500 et la page Vocabulaire vide. `open_station_workspace` rattrape `AppError` (journalisée) et rend `None` ; test par la route (JSON cassé, parcours inconnu).
- low · second avis 4 · corrigé : test par la route avec un espace à pipeline réellement ouvert (`check-en-echec`), puis un scénario de station sans pipeline.
- low · second avis 5 · rejeté : dériver `PIPELINE_JOB_IDS` de `pipeline.yaml` ferait lire le contenu par `projections` ; le test d'alignement attrape la dérive, et `test_links` refuse une clé sans entrée.
- low · second avis 6 · rejeté : `tabindex="-1"` est le focus itinérant des vues (`rovingItems` prend tous les boutons du volet) ; le « i » d'une tâche s'atteint aux flèches comme les autres.
- low · second avis 7 · reporté à la fusion : conflits attendus avec 8.6 (fin d'`explanations.yaml`, `EXPLAIN_REFS`) ; garder les deux.
- Complexité : 0 constat (sept tâches décorées par passe, une lecture de `progress.json` et du catalogue par requête `/api/glossary`).
