---
story: "7.4"
key: 7-4-faire-tourner-le-pipeline-simulé-sur-chaque-pr
title: Faire tourner le pipeline simulé sur chaque PR
status: review
branch: story/7-4-pipeline-simule
ad: [AD-1, AD-6, AD-8, AD-10, AD-12, AD-13]
---

# Story 7.4 : Faire tourner le pipeline simulé sur chaque PR

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 7.4 » ; spine AD-8, AD-10, AD-12 ; FR-22, NFR-6, UX-DR19, UX-DR20. Reprend le report de la 3.4 (`set_check_state` appelé depuis la file, déclencheur `checks_green`).

## Livré

- **`content/pipeline.yaml`** (contrat documenté en tête du fichier, pour 8.1, 8.3, 8.4 et 8.6) : `schema_version`, puis par job `job_id`, `label_text`, `tool` (id de `tools.toml`), `required`, `barrier` (id de `chain.yaml`), `human` (argv de la sortie humaine), `machine` (exécutions machine : `argv`, `parse`, `when: failure|always`), `exit_codes` (`success`, `failure` ; tout autre code, un délai dépassé ou un outil introuvable donnent `error`). Jetons `{repo}`, `{base_sha}`, `{osv_url}` et `{report}` (fichier de rapport d'une exécution machine, hors de l'arbre) ; tout autre jeton, et `{report}` dans `human`, sont refusés au chargement. Jobs de l'epic : `ruff` (`check .`, constats de `--output-format json`), `pytest` (`-q --tb=short`, constats du rapport `--junitxml` ; code 5 « aucun test » = échec), `gitleaks` (`dir --redact --exit-code 3 .` : 3 = fuite, 1 = erreur de l'outil ; constats de `--report-format json`).
- **Module `ci`** (`ci/__init__.py`, `ci/findings.py`) : modèle et chargement du pipeline, remplacement des jetons, `prepare_tree` (`git clone --shared --no-checkout` de `origin.git` dans `ci/<pr>-<sha7>/`, puis checkout du SHA de tête), `prepare_environment` (AD-12, ci-dessous), `run_job` (sortie humaine verbatim stdout puis stderr, état par `exit_codes`, exécutions machine dues, constats `Finding` règle/fichier/ligne). Une erreur de l'outil porte le constat `rule_id: tool_error` : « gitleaks s'est arrêté sans résultat (code 1). Ce n'est pas un défaut de votre code. ». `ci` n'importe que `gitio`, `toolrun`, `wsfs`, `config`, `contracts`, `registry` (AD-1) ; ses processus passent par `toolrun.spawn_tool`.
- **Environnement du run** : `toolrun.sync_environment` écrit maintenant dans l'environnement créé la marque `.wds-uv-lock.sha256` (sha256 du `uv.lock` d'origine). Le run réutilise `cache/venv/` si cette marque égale le hash du `uv.lock` du SHA testé ; sinon il crée `ci/venv-<hash12>/` par `uv sync --offline --frozen` depuis l'arbre testé (gardé pour les runs suivants du même `uv.lock`, vidé avec `ci/` au rétablissement). Seuls les jobs dont l'outil est de résolution `uv-lock` en ont besoin.
- **Runner par espace** (`engine/pipeline.py`, `PipelineRunner`) : après chaque opération de la file et après la projection d'ouverture (nouveau crochet `WorkspaceEngine.after_op`), `scan` relit `github.json` ; pour chaque PR ouverte dont un check du pipeline manque ou est `queued`/`running` pour ses SHA courants, il demande un run de clé `(pr, head_sha, base_sha)` et `epoch`. Un run actif par espace, les autres en file ; les runs d'une PR fermée, mergée ou poussée à nouveau, ou d'un autre `epoch`, sont annulés (`Handle.terminate`, donc `procs.terminate_tree`). Jobs en série dans l'ordre du fichier ; l'arbre est jeté à la fin du run.
- **Résultats par la file** (AD-1, AD-8) : chaque changement d'état (`running`, puis le résultat) est une opération `check_update` (`writes=False`, portant l'`epoch` du run) qui appelle `github_sim.set_check_state(..., duration_ms=, expected=(head_sha, base_sha))`, émet `check_updated{number, job_id, state, head_sha, element_id, duration_ms}` puis `pr_updated`. La première opération d'un run ajoute les checks manquants (`github_sim.ensure_checks`, à `queued`, `required` du pipeline). Un résultat d'un autre `epoch` est refusé par la file (`StaleOperation`), un résultat pour d'anciens SHA par `github_sim` (`StaleCheck`) ; les réactions `checks_green` du collègue simulé jouent dans la même écriture.
- **Annulation** : nouveau SHA de la même PR (le scan suivant le push), Recommencer ou rétablissement (entrée en `setup`/`restoring` : `cancel_all` attend l'arrêt de l'outil avant que `ci/` soit vidé), mise en veille de l'espace (`stop`).
- **`check_rerun{number, job_id}`** (« Relancer le check ») : refusé en 409 si le scénario n'a pas de pipeline, si le job est inconnu, la PR fermée ou le check déjà en attente ; sinon le check repasse à `queued` et le scan relance ce seul job.
- **Activation** : nouveau champ de scénario `pipeline: bool = false`. Aucun scénario livré ne l'active encore (stations 2 et 3 : 7.5, 8.x) ; les PR des scénarios existants gardent leurs checks déclarés.
- **Réglages** : `Settings.pipeline_job_timeout_s` (120 s), `Settings.pipeline_path()`. `WorkspaceManager(osv_url=)` porte le jeton `{osv_url}`.
- **Durée** : chaque check porte `duration_ms` ; chaque run aussi (`PipelineRunner.history`, journalisé).
- Tests : `tests/test_pipeline.py` (contrat du fichier, jetons, lecteurs de constats, `StaleCheck`, choix de l'environnement ; dans un espace réel avec outils remplacés : checks écrits par la file dans l'ordre `running`/résultat, sortie verbatim, constats machine, erreur de l'outil, arbre jeté, nouveau SHA qui arrête l'arbre et rejette l'ancien run, Recommencer qui l'arrête, résultat d'un ancien `epoch` refusé, relance d'un seul job, pipeline non déclaré ; vrais ruff, pytest et gitleaks si `WDS_EXERCISE_UV=1` sur une PR qui met à jour le `uv.lock` : pytest voit `httpx` de la nouvelle version, durée du run : alerte au-delà de 90 s, échec au-delà de 180 s). Ajouté au job CI « Scénarios sans réseau (unshare -n) ».

## Décisions

- Le déclencheur est l'état de `github.json` relu après chaque opération, pas un appel ajouté à chaque écrivain des refs de `origin` (terminal, changement externe, merge, ouverture de PR) : tout chemin qui remet un check à `queued` fait tourner le pipeline, y compris une reprise après un arrêt (checks restés `running`).
- Activation par un champ du scénario plutôt que par la présence de `.github/workflows/ci.yml` dans l'arbre : les trois écritures du pipeline arrivent avec 7.6.
- gitleaks en mode `dir` sur l'arbre du SHA de tête : il ne dépend pas d'un git du PATH (gitleaks `git` appelle `git`), au prix de signaler aussi un secret déjà présent sur `main`.
- Le message d'erreur de l'outil est un constat (`tool_error`) : le schéma de `github.json` reste inchangé (empreintes de référence identiques).
- Les opérations du pipeline sont `writes=False` : un résultat n'est pas refusé en `quiz_altered` ; le rétablissement qui suit change l'`epoch` et rejette les résultats en vol.
- Exécutions machine seulement en cas d'échec par défaut (`when: failure`), comme la 7.2 ; `when: always` est prévu pour la quality gate (8.4).

## Reports

- Vue Distant + PR (3.3, en intégration) : bloc `tool-output` « Voir la sortie » (sortie verbatim), ligne de détail d'un échec avec fichier:ligne en lien (constats `path`/`line`), « ⚠ Erreur de l'outil » et son texte (constat `tool_error`), bouton « Relancer le check » qui poste `check_rerun`, libellés des jobs (`label_text`). Le contrat serveur est prêt ; la preuve `evidence_seen` (champ `barrier`) se soumet à l'ouverture de la sortie.
- `{osv_url}` : `create_app` ne connaît pas le port ; 8.3 passe `Settings.osv_url(port)` à `WorkspaceManager(osv_url=)`.
- Jobs `bandit`, `pip_audit`, `quality_gate` et leurs lecteurs (`bandit_json`, `pip_audit_json`, `cyclonedx_json`, `coverage_json`, `diff_cover_json`) : 8.1, 8.3, 8.4. Le budget de 45 s du run complet se mesure en 8.4 et 9.5.
- `pipeline_runs[]` dans l'état public de l'espace (`GET /api/ws/<id>/state`) : les runs sont gardés dans `PipelineRunner.history`, pas encore exposés.
- Scénarios de station 2 qui déclarent `pipeline: true` : 7.5.

## À vérifier sur poste réel

1. Windows, macOS, Linux : une PR d'un scénario `pipeline: true` affiche ses trois checks `queued`, puis `running`, puis leur résultat ; un push pendant le run l'arrête et repart du nouveau SHA.
2. gitleaks provisionné (installeur) : `dir` sur l'arbre trouve une clé ajoutée par la PR (8.6) et passe sur l'arbre propre.
3. Réseau coupé : un run avec un `uv.lock` modifié crée son environnement depuis le cache préchargé.
4. Recommencer pendant un run long sous Windows : `ci/` est vidé sans erreur de verrou.
