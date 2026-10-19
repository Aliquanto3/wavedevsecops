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

- **Scénario `cle-api-en-dur`** (station 3, parcours LLM, `STATION_ORDER` après `couverture-sous-le-seuil`) : `main` exige `gitleaks` ; la branche `feature` ajoute une clé fictive (`API_KEY`, `AUTH_HEADERS`) dans `src/inventory/llm_config.py`. Étapes : pousser, ouvrir la PR, lire le blocage (`gitleaks` en échec, constat `generic-api-key`), sortir la clé vers `os.environ` (`gitleaks` et `pytest` verts), puis `sans_exception` (aucun `.gitleaksignore`, tout poussé) et `rester_au_vert` (revue : `gitleaks` et `pytest` de nouveau verts sans l'exception).
- **Scénario `donnees-vers-le-cloud`** : `main` exige `pytest` ; `llm.toml` vise `api.llm-cloud.example` (domaine réservé, jamais appelé) en `base_url` et en `allowed_endpoints`. Les tests du gabarit (`test_default_endpoint_is_local_ollama`, `test_allowed_endpoints_are_loopback_only`) échouent dans le check `pytest` (constats exigés par `finding_has`). L'étape de correction est un `repo_state` : `llm.toml` redevenu local, poussé, arbre propre, et les deux tests de config toujours présents tels quels (`tree.contains`) ; puis `voir_le_vert` (`pytest` vert).
- **Job `gitleaks` durci** (`content/pipeline.yaml` et les 6 fichiers CI des gabarits, aucun job ajouté) : `--ignore-gitleaks-allow` et `--config {config}/gitleaks.toml` (nouveau `content/ci/gitleaks.toml` : règles par défaut, hors de l'arbre). Un commentaire `gitleaks:allow` et un `.gitleaks.toml` déposé n'écartent plus rien.
- **Injection de prompt** : entrée `remote.review_llm` en fin de `content/explanations.yaml` (clé ajoutée à `EXPLAIN_REFS`), citée par l'étape `voir_le_vert` ; aucun scénario ne la déclenche.
- Tests : `tests/test_llm_scenarios.py` (contrat, étapes, contournements, vrais gitleaks et pytest, sept jobs sur les états corrigés). Empreintes régénérées, stables sur deux passes.

## Décisions

- La clé vit dans `llm_config.py` seul (pas dans le client httpx) : le test `post_json` est ignoré sans httpx, ce qui ferait tomber la quality gate sur les lignes ajoutées.
- `.gitleaksignore` à la racine reste lu par gitleaks malgré `--config` (vérifié) : refusé par l'étape `sans_exception`, pas par le job.
- Le contournement du test de config (le vider, le supprimer, l'assouplir, revue : un décorateur `skip`/`xfail` ou un `return` en tête) est fermé par `tree.contains` sur les deux tests d'un seul tenant depuis la ligne d'import, et sur les deux lignes de `llm.toml` ancrées en début de ligne (une valeur locale en commentaire ne compte pas). Un test écarté par la configuration de pytest (`pytestmark`, `conftest.py`, `--deselect`) reste possible : nommé au débrief de `voir_le_vert`.

## Reports

- Une clé découpée ou encodée échappe à gitleaks : nommée au débrief (`rester_au_vert`). Un test écarté par la configuration de pytest : nommé au débrief (`voir_le_vert`).
- L'entrée `remote.review_llm` n'est reliée à aucun élément de vue (la projection ne connaît pas le parcours) : elle s'affiche via l'étape `voir_le_vert`.

## À vérifier sur poste réel

1. `cle-api-en-dur` : `gitleaks` en échec avec `src/inventory/llm_config.py`, valeur masquée ; correction par `os.environ` : vert.
2. `donnees-vers-le-cloud` : `pytest` en échec sur les deux tests ; retour à la config locale : vert.

## Revue

Revue Opus du 2026-10-19, rebasée sur `main` (f917b1a, déjà à jour), avec la liste du second avis (Haiku).

- medium · revue · corrigé · `.gitleaksignore` : `retirer_la_cle` passait au vert grâce à l'exception, puis `sans_exception` (repo_state) passait dès l'exception retirée et poussée, sans revoir la PR : le scénario finissait sur une clé encore dans le code, check rouge. Étape finale `rester_au_vert` (pr_state, `gitleaks` et `pytest` verts sur les SHA courants), test ajouté.
- medium · second avis 1 · corrigé en partie · `skip`/`xfail` au-dessus des tests (même séparés par des lignes vides, syntaxe valide), `return` ou `pytest.skip()` en tête : fermés par un `tree.contains` d'un seul tenant depuis la ligne d'import ; valeur locale laissée en commentaire dans `llm.toml` : fermée par l'ancrage en début de ligne. Tests ajoutés, prouvés rouges sur l'ancienne garde. Vérifier les tests réellement exécutés (junit des tests passés) demanderait un nouveau contrat de constats : non retenu (ligne directrice 8.4).
- medium · second avis 2 · reporté (débrief) · `pytestmark` de module, `collect_ignore` dans un `conftest.py`, `addopts = --deselect` : la CI fait confiance au code qu'elle lance ; nommé au débrief de `voir_le_vert`. Le contournement exige en plus une astuce TOML (table annexe) pour garder la config cloud active : pas trivial.
- low · second avis 3 · corrigé · le hook pre-commit lit encore `.gitleaks.toml` et `gitleaks:allow` (7.3 inchangé) : le texte de `retirer_la_cle` dit désormais « le check de la PR ignore… » ; le scénario ne pose pas le hook.
- low · second avis 4 · noté · `{config}` en dur dans les gabarits CI, comme `bandit.ini` en 8.4.
- low · second avis 5 · vérifié · gitleaks local (cache pre-commit) : clé détectée (code 3) ; `gitleaks:allow` écarte sans `--ignore-gitleaks-allow` (0), plus avec (3) ; `.gitleaks.toml` à `[allowlist]` écarte sans `--config` (0), plus avec (3). Les tests lents gitleaks tournent en CI (`WDS_EXERCISE_DATA`).
- low · second avis 6 · noté · conflits à la fusion avec 8.5 (`STATION_ORDER`, `pr_state`) et 9.6 (`explanations.yaml`, `EXPLAIN_REFS`) ; empreintes inchangées par la revue (stables, 0 changement sur deux passes).
- low · second avis 7 · corrigé · Décisions et Reports de cette spec réécrits.
- low · revue · corrigé · indices `partial_text` sans blanc `___` (avertissement du lint de contenu) dans les deux scénarios.
- low · revue · noté · `head_files` de 8.5 (fichier au commit de tête de la PR) pourrait fermer `.gitleaksignore` dans l'étape de PR elle-même, après fusion.
- Complexité : 0 constat (scénarios déclaratifs, aucune structure qui grossit).
- Tests : ciblés et lents (340 tests, 9 skipped : gitleaks et uv absents du poste) ; 3 tests de `test_pipeline.py` en dépassement sous charge parallèle, verts relancés seuls.
