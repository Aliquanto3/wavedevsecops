---
story: "8.4"
key: 8-4-bloquer-une-pr-quand-la-couverture-du-nouveau-code-passe-sou
title: Bloquer une PR quand la couverture du nouveau code passe sous 80 %
status: review
branch: story/8-4-quality-gate
ad: [AD-10, AD-14]
---

# Story 8.4 : Bloquer une PR quand la couverture du nouveau code passe sous 80 %

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 8.4 » ; FR-26, FR-27, FR-33, NFR-6. Plus deux arbitrages d'Anaël du 2026-10-19 : bandit lu hors de l'arbre de l'apprenant, et un contrôle `uv lock --check`. pytest-cov 7.1.0, coverage 7.16.2 et diff-cover 10.6.0 sont déjà épinglés (`pyproject.toml`, `uv.lock`, `tools.toml`, les deux gabarits) et installés en CI (`uv sync --locked --group chain`) : aucune dépendance ajoutée, un test le vérifie.

## Livré

- **Job `quality_gate`** (`content/pipeline.yaml`, dernier job ; outil `diff-cover`, barrière `coverage`, obligatoire). Nouveau champ de job `before` (modèle `ci.Step`) : commandes lancées avant la sortie humaine, qui doivent finir par 0, sinon le check est en échec (constat `before_failed`, la sortie de pytest reste affichée). Ici : `pytest -o addopts= --cov --cov-config={config}/coverage.ini --cov-report=term-missing:skip-covered --cov-report=xml:{reports}/coverage.xml -q --tb=short`, puis `diff-cover {reports}/coverage.xml --compare-branch={base_sha} --fail-under=80`. Constats : `diff-cover --format json:` (`diff_cover_json`) et `coverage json` (`coverage_json`, nouveau champ `tool:` d'une exécution machine), lus à chaque run, vert compris.
- **Affichage** : constat `diff_coverage`, « Couverture du nouveau code n % · seuil 80 % · ✓ » (ou ✗), puis un constat `uncovered_lines` par fichier (lignes sans test, fichier:ligne lié) et un constat `total_coverage` (information : couverture de tout le dépôt). Le pourcentage est celui de diff-cover (entier, arrondi vers le bas) : 79,9 % reste ✗. Diff sans ligne mesurée : « aucune ligne à mesurer » (règle `diff_coverage_none`, jamais `diff_coverage`). Le seuil 80 est une constante (`ci.findings.QUALITY_GATE_THRESHOLD`) qu'un test rapproche de `--fail-under`.
- **Réglages hors de l'arbre** : nouveaux jetons `{config}` (`content/ci/`, `Settings.ci_config_path()`) et `{reports}` (`ci/<pr>-<sha7>.reports/`). `content/ci/coverage.ini` : `source = .`, `include_namespace_packages` (un module jamais importé vaut 0 %, sinon `src/` sans `__init__.py` l'échapperait), `exclude_lines` remplacé (donc `# pragma: no cover` ignoré). `-o addopts=` retire les `addopts` du dépôt (`--no-cov`) ; le rapport XML est écrit hors de l'arbre (un `coverage.xml` déposé est sans effet). diff-cover ne lit pas `[tool.diff_cover]` sans `--config-file` : rien à fermer.
- **Bandit hors de l'arbre** : `--ini {config}/bandit.ini` dans l'exécution humaine et machine du job `bandit` (ferme `src/.bandit` avec `skips = B307`). `content/ci/bandit.ini` : section `[bandit]` vide.
- **Job `uv_lock`** (avant `quality_gate`, outil `uv`, barrière `dependencies`, obligatoire) : `uv lock --check`, code 1 = verrou périmé. Décision : l'exercice utilise uv (`uv.lock`, `uv sync --frozen`), donc la forme la plus simple qui garantit « un pyproject modifié sans lock à jour fait échouer le pipeline » est ce contrôle, sans installation ni écriture, hors ligne. Il passe sur les deux gabarits tels quels.
- **Scénario `dependance-vulnerable` réaligné** : son commit déclare aussi jinja2 3.1.6 comme dépendance du projet dans `uv.lock` (nouvelle op de setup `replace_in_file`, deux ajouts identiques à ceux de `uv lock`). `uv_lock` échoue tant que `pyproject.toml` demande 3.1.2 et passe à 3.1.6 ; l'étape finale exige maintenant `uv_lock: success` en plus de `pip_audit`, ce qui clôt la piste signalée en revue 8.3 (corriger seulement `requirements.txt`).
- **Scénario `couverture-sous-le-seuil.A.yaml`** (parcours sans IA, station 3, `STATION_ORDER` après `dependance-vulnerable`) : `main` exige `quality_gate` ; la branche `feature` ajoute `src/inventory/alertes.py` sans test. Étapes : pousser, ouvrir la PR, lire le blocage (`quality_gate` en échec, constat `diff_coverage`), ajouter `tests/test_alertes.py` et pousser (`quality_gate` vert **et** `diff_coverage` présent). Nouveau champ `finding_has` de l'étape `pr_state` (`{job_id: [rule_id]}`, SHA courants) : supprimer le module non testé donne un check vert mais pas une étape validée (leçon 6.2).
- **Gabarits** : jobs `uv_lock` et `quality_gate` balisés `wds:job` / `wds:end` dans les 6 fichiers CI ; ligne bandit mise à jour ; en-têtes « sept tâches ». `pr-sans-revue` attend `uv_lock` et `quality_gate`. Glossaire : `quality-gate` renvoie à `couverture-sous-le-seuil` et à la barrière `coverage`. diff-cover reçoit le git du registre dans son PATH (`toolrun.with_tools_on_path`). Empreintes régénérées, stables sur deux passes.
- **Tests** : `tests/test_quality_gate.py` (contrat des trois jobs, versions épinglées, lecteurs, scénario, étape, op `replace_in_file`) et ses tests lents avec les vrais outils : refus à 0 % puis acceptation, contournements (`omit` dans pyproject, `.coveragerc`, `setup.cfg`, `tox.ini`, `[tool.diff_cover]`, `addopts = --no-cov`, `coverage.xml` déposé, `# pragma: no cover`, module supprimé), tests en échec, bandit contre `src/.bandit`, `.bandit` racine et `[tool.bandit]`, `uv lock --check` (pyproject modifié, scénario 8.3 avant/après correction), et le **test de performance** (pipeline des sept jobs avec les vrais outils : avertissement pytest au-delà de 90 s, échec au-delà de 180 s ; gitleaks seulement s'il est posé, comme en CI). `test_pipeline*.py`, `test_stations_pr.py`, `test_dependance_vulnerable.py` réalignés sur sept jobs.

## Décisions

- **Options de pytest en `--option=valeur`** : pytest prend une valeur détachée (`--cov-config PATH`) pour un chemin à collecter et en déduit sa racine, ici le dépôt de la plateforme ; cause trouvée par un test lent.
- **Périmètre de couverture `source = .`** (tests compris, rien d'omis) : déplacer du code hors de `src/` ou dans `tests/` ne le soustrait pas à la mesure.
- **Verrou de `dependance-vulnerable`** : une op de plus (`replace_in_file`) plutôt que d'inclure les 770 lignes du verrou dans le scénario.
- **Un seul rapport XML pour diff-cover** : le JSON de pytest-cov n'est pas utilisé, `coverage json` relit le fichier de données.

## Reports

- Budget de 45 s : à mesurer sur le poste de référence d'Anaël avant la release v0.2.0 (story 9.5) ; le test ne garde que 90 s (alerte) et 180 s (échec).
- Scénario du parcours LLM (quality gate sur `httpx`) : story 8.5.
- Un fichier Python changé que coverage n'a pas pu analyser n'est pas un constat `unscanned_file` de la quality gate (ruff et pytest échouent déjà sur une syntaxe illisible).
- Un test sans assertion qui exécute le code fait passer le seuil : c'est la limite connue de la couverture, à nommer dans le débrief, pas à corriger ici.
- **Décision pour Anaël — couverture falsifiable depuis l'arbre testé** : le code de l'apprenant s'exécute dans le processus de pytest, qui mesure la couverture. Un `conftest.py` peut réécrire `<arbre>.reports/coverage.xml` (`pytest_unconfigure`) ou, plus court, ajouter des lignes à la mesure en cours (`coverage.Coverage.current().get_data().add_lines(...)`, prouvé en revue : 33 % → 100 %, que le XML soit écrit par pytest ou ensuite par `coverage xml`). Ni un chemin de rapport imprévisible (lisible dans `config.option`) ni un rapport produit hors de pytest ne ferment la seconde voie ; seule une mesure hors du processus de l'apprenant le ferait, ce qui n'existe pas pour Python. C'est aussi la limite d'une vraie CI. Le geste enseigné (ajouter un test) reste de loin le chemin le plus court ; option : nommer la limite au débrief avec celle du test sans assertion.

## À vérifier sur poste réel

1. Pousser `feature`, ouvrir la PR : `quality_gate` passe à « Échec · Obligatoire », le détail affiche « Couverture du nouveau code 0 % · seuil 80 % · ✗ » et les lignes de `src/inventory/alertes.py` ; « Merger » est inactif.
2. Ajouter `tests/test_alertes.py` (un test par fonction), committer, pousser : le check repasse au vert avec « … n % · seuil 80 % · ✓ ».
3. `dependance-vulnerable` : `uv_lock` échoue avec `pip_audit` au départ, les deux repassent au vert avec la correction de `pyproject.toml` et `requirements.txt`.
4. Temps du pipeline complet sur le poste (alerte à 90 s) ; sortie lisible de `uv_lock` (message de uv, hors ligne).

## Revue

Revue Opus du 2026-10-19, rebasée sur `main` (5394451), avec la liste du second avis (Haiku).

- high → medium · second avis 1 · reporté (décision Anaël) · `conftest.py` qui falsifie la couverture : confirmé, mais une seconde voie (`Coverage.current()` + `add_lines`) contourne aussi un rapport produit hors de pytest ; parade fiable impossible en Python, limite consignée dans Reports.
- medium · second avis 4 · corrigé · `test_vrais_outils_dans_le_pipeline` attendait les sept jobs réels 60 s (`WAIT`) alors qu'il tolère 180 s : `Box.wait_settled(timeout)`, ce test attend `LIMIT_S + 30`.
- low · second avis 2 · reporté · fichier au nom pointé (`calc.v2.py`) jamais importé : hors mesure, comme dans coverage réel ; dans le scénario, `finding_has: diff_coverage` refuse un diff sans ligne mesurée.
- low · second avis 3 · rejeté · diff sans ligne mesurée vert : comportement de diff-cover, constat `diff_coverage_none` affiché, et l'étape du scénario l'exclut (`finding_has`).
- low · second avis 5 · rejeté · `bandit -r src` en dur : antérieur (8.1), les deux gabarits ont `src/`.
- low · second avis 6 · rejeté · première étape de `dependance-vulnerable` sans `uv_lock: failure` : l'échec est garanti par le setup, l'étape porte sur pip-audit.
- low · second avis 7 · rejeté · glossaire : la quality gate est désormais la barrière `coverage`, `tests` garde « Intégration continue ».
- low · second avis 8 · reporté · test sans assertion : déjà dans Reports (débrief).
- low · revue · reporté · `uv lock --check` hors ligne sur une version absente du cache sort 1 (donc `failure`, vérifié) mais avec « No solution found … network was disabled » plutôt que « needs to be updated » : texte à juger sur poste (point 4 de « À vérifier »).
- vérifié · revue · `replace_in_file` confiné (`../x`, absolu, `a/../../x`, `.git/config` refusés) ; arrondi de diff-cover (entier tronqué) identique pour `--fail-under` et l'affichage ; scénarios à merge (`check-en-echec`, `pr-sans-revue`) : diff de tests seulement, donc couvert.
- Complexité : 0 constat (sorties `before` concaténées sur une ou deux commandes, lecteurs linéaires).
