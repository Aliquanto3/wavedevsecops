---
story: "1.1"
key: 1-1-amorcer-le-dépôt-et-la-ci-sur-trois-systèmes
title: Amorcer le dépôt et la CI sur trois systèmes
status: review
branch: story/1-1-amorce
ad: [AD-1, AD-13, AD-16, AD-18]
---

# Story 1.1 : Amorcer le dépôt et la CI sur trois systèmes

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 1.1 ».

## Livré

- `pyproject.toml` (uv, `uv_build`) : version `0.1.0.dev0`, Python `>=3.14,<3.15` (`.python-version` 3.14), dépendances, groupes `chain` (outils de la chaîne) et `dev` (ruff, pytest), extra `window` (pywebview 6.2.1), toutes épinglées `==` aux versions de la table Stack ; `uv.lock` commité.
- `.gitattributes` `* text=auto eol=lf`.
- `src/wavedevsecops/` : `config.py` (`Settings` pydantic figé, `Settings.from_env()` sur les variables `WDS_*`, `get_settings()`), `contracts/`, `events/`, `procs/` (squelettes documentés) ; `content/` (vide) ; `tests/`.
- Tests :
  - `test_architecture.py` : règles d'AD-1 (feuilles, personne n'importe `web` ni `cli` sauf `cli` → `web`, `procs` réservé à `gitio`/`toolrun`, `subprocess` réservé à `procs`) et lecture de l'environnement réservée à `config` ;
  - `test_offline_rules.py` : AD-13 contrôles (1) imports réseau et (2) URL de `web/static/` ;
  - `netguard.py` + `conftest.py` + `test_network_guard.py` : AD-13 contrôle (3), hook d'audit `socket.connect` loopback seulement ;
  - `test_stack_versions.py` : table Stack du spine ↔ `pyproject.toml` ↔ `uv.lock` ;
  - `test_seed.py`, `test_config.py`.
  Chaque contrôle statique est aussi testé sur des exemples synthétiques en violation.
- CI `.github/workflows/ci.yml` : push (toutes branches) et PR, matrice `windows-latest`, `macos-latest`, `ubuntu-latest`, `uv sync --locked`, `ruff check`, `pytest`.
- `CLAUDE.md` racine (section « Commandes ») ; contrôle rapide du cost-kit branché sur `ruff check`.

## Décisions

- `Settings` hérite de `pydantic.BaseModel` (pas de `pydantic-settings`, absent de la table Stack).
- Le test de cohérence lit directement la table Stack du spine (glob du dossier d'architecture). `tools.toml` arrive en Story 1.4, qui l'ajoutera à la comparaison.
- AD-13 (1) : `web` et `cli` ont droit à `socket` seulement (écoute) ; `llmrun` est exempté.
- AD-13 (2) : les identifiants d'espaces de noms XML du W3C (`http://www.w3.org/2000/svg`…) sont permis : jamais chargés, nécessaires à `createElementNS`. Fichiers binaires (polices, images) ignorés.

## Reports

- AD-13 contrôle (4) (`unshare -n` sous Linux) : avec la suite de scénarios et du pipeline (stories suivantes).
- AD-18 : lint de contenu, empreintes de référence, clone `autocrlf=true` sous Windows, tests de l'extra pywebview sous Windows : avec les stories qui créent ces contenus et `--window`.
- Comparaison avec `tools.toml` : Story 1.4.
- Bibliothèques vendorisées dans `static/` : leurs commentaires de licence contiennent souvent des URL ; la story qui les vendorise devra les retirer ou étendre la règle.
