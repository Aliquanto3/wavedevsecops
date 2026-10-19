---
story: "8.6"
key: 8-6-la-clé-d-api-en-dur-le-test-de-config-llm-et-l-injection-de
title: La clé d'API en dur, le test de config LLM et l'injection de prompt
status: review
branch: story/8-6-cle-api-config-llm
ad: [AD-10, AD-13, AD-7, AD-14]
---

# Story 8.6 : La clé d'API en dur, le test de config LLM et l'injection de prompt

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 8.6 » ; FR-28. Ligne de coupe v0.2 : l'élément 2 (test de config), livré.

## Livré

- **Scénario `cle-api-en-dur`** (station 3, parcours LLM, `STATION_ORDER` après `couverture-sous-le-seuil`) : `main` exige `gitleaks` ; la branche `feature` ajoute une clé fictive (`API_KEY`, `AUTH_HEADERS`) dans `src/inventory/llm_config.py`. Étapes : pousser, ouvrir la PR, lire le blocage (`gitleaks` en échec, constat `generic-api-key`), sortir la clé vers `os.environ` (`gitleaks` et `pytest` verts), puis `sans_exception` (aucun `.gitleaksignore`, tout poussé).
- **Scénario `donnees-vers-le-cloud`** : `main` exige `pytest` ; `llm.toml` vise `api.llm-cloud.example` (domaine réservé, jamais appelé) en `base_url` et en `allowed_endpoints`. Les tests du gabarit (`test_default_endpoint_is_local_ollama`, `test_allowed_endpoints_are_loopback_only`) échouent dans le check `pytest` (constats exigés par `finding_has`). L'étape de correction est un `repo_state` : `llm.toml` redevenu local, poussé, arbre propre, et les deux tests de config toujours présents tels quels (`tree.contains`) ; puis `voir_le_vert` (`pytest` vert).
- **Job `gitleaks` durci** (`content/pipeline.yaml` et les 6 fichiers CI des gabarits, aucun job ajouté) : `--ignore-gitleaks-allow` et `--config {config}/gitleaks.toml` (nouveau `content/ci/gitleaks.toml` : règles par défaut, hors de l'arbre). Un commentaire `gitleaks:allow` et un `.gitleaks.toml` déposé n'écartent plus rien.
- **Injection de prompt** : entrée `remote.review_llm` en fin de `content/explanations.yaml` (clé ajoutée à `EXPLAIN_REFS`), citée par l'étape `voir_le_vert` ; aucun scénario ne la déclenche.
- Tests : `tests/test_llm_scenarios.py` (contrat, étapes, contournements, vrais gitleaks et pytest, sept jobs sur les états corrigés). Empreintes régénérées, stables sur deux passes.

## Décisions

- La clé vit dans `llm_config.py` seul (pas dans le client httpx) : le test `post_json` est ignoré sans httpx, ce qui ferait tomber la quality gate sur les lignes ajoutées.
- `.gitleaksignore` à la racine reste lu par gitleaks malgré `--config` (vérifié) : refusé par l'étape `sans_exception`, pas par le job.
- Le contournement du test de config (le vider, le supprimer, l'assouplir) est fermé par `tree.contains` sur le texte exact des deux tests et de `llm.toml`.

## Reports

- Une clé obfusquée (base64, découpée) échappe à gitleaks : limite de l'outil, à nommer au débrief.
- Un test de config neutralisé en gardant son texte (par exemple `return` en tête) passe la garde textuelle.
- L'entrée `remote.review_llm` n'est reliée à aucun élément de vue (la projection ne connaît pas le parcours) : elle s'affiche via l'étape `voir_le_vert`.

## À vérifier sur poste réel

1. `cle-api-en-dur` : `gitleaks` en échec avec `src/inventory/llm_config.py`, valeur masquée ; correction par `os.environ` : vert.
2. `donnees-vers-le-cloud` : `pytest` en échec sur les deux tests ; retour à la config locale : vert.
