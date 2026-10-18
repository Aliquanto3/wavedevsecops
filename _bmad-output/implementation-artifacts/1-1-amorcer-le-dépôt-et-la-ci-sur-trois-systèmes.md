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

## Revue

Revue unique (Opus) de 08f41f5, avec la liste du second avis (Haiku). Critères d'acceptation : tous couverts.

- medium · revue · corrigé : le test `connect(("example.org", 443))` lançait une vraie requête DNS avant l'événement d'audit (résolution en C dans `sock.connect`) et échouait hors ligne sur `gaierror`. Le hook refuse maintenant les événements `socket.getaddrinfo`/`gethostbyname*` pour un nom non loopback ; le test passe par `create_connection`. La limite restante (`sock.connect` avec un nom) est documentée dans `netguard.py` et relève du contrôle (4).
- medium · second avis 1 · corrigé : `misplaced_static_dirs` fait échouer la suite si un dossier `static` existe ailleurs que `web/static/` ; l'absence de `web/static/` reste normale tant que `web` n'existe pas (Story 1.2).
- medium · second avis 2 · corrigé : création de processus hors `procs` détectée aussi via `os.system/popen/spawn*/exec*/fork/posix_spawn/startfile`, `asyncio.create_subprocess_*`, `asyncio.subprocess`, `pty`, `ProcessPoolExecutor`.
- medium · second avis 3 · corrigé : lecture de l'environnement suivie à travers les alias (`import os as o`) ; `from os import environ` était déjà détecté.
- low · second avis 4 · corrigé (une ligne) : `_socket`, `urllib3`, `ftplib`, `smtplib`, `poplib`, `imaplib`, `xmlrpc.client` ajoutés à la liste d'AD-13 (1). `asyncio.open_connection` écarté : interdire `asyncio` n'a pas de sens, et le hook (3) couvre la connexion.
- low · second avis 5 · rejeté : le critère accorde à `web` et `cli` l'écoute par `socket` ; distinguer écoute et connexion statiquement dépasse un garde-fou de test, le hook (3) refuse toute connexion sortante.
- low · second avis 6 · corrigé (même correctif que le constat medium de revue).
- low · second avis 7 · corrigé en partie : `ws://` et `wss://` ajoutés. `//hôte` rejeté : indiscernable des commentaires `//` en JS.
- low · second avis 8 · reporté : la CI n'installe que `dev`. Le lock universel et `--locked` garantissent la résolution du groupe `chain` ; son installation sur les trois OS sera vérifiée en Story 1.4 (`tools.toml`), en ajoutant `--group chain` à `uv sync` dans la CI.
