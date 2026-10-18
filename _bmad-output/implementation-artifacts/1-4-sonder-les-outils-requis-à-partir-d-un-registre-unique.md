---
story: "1.4"
key: 1-4-sonder-les-outils-requis-à-partir-d-un-registre-unique
title: Sonder les outils requis à partir d'un registre unique
status: review
branch: story/1-4-registre-outils
ad: [AD-1, AD-3, AD-12, AD-15, AD-16, AD-17]
---

# Story 1.4 : Sonder les outils requis à partir d'un registre unique

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 1.4 ».

## Livré

- `tools.toml` (racine) : registre unique. Par outil : `id`, `usage`, `milestone`, `resolution` (`host-or-provisioned`, `host`, `provisioned`, `uv-lock`), `min_version` (git 2.38, uv 0.11.0, gitleaks 8.20.0), `provisioned_version` (valeur unique, ou table `windows`/`posix` pour git), `paths` dans `<data>/tools/`, `probe` + `version_regex`, `network` et `network_switch`. Outils : git, uv, gitleaks, pixi (installeur seulement, jalon `install`), et les huit outils Python de la chaîne.
- `registry.py` : lecture et validation pydantic de `tools.toml`, comparaison de versions (`at_least`, `parse_version`).
- `procs.run` / `terminate_tree` : lanceur bloquant avec délai, sans shell, entrée fermée, arrêt de l'arbre (taskkill `/T` sous Windows, groupe de processus sous Unix). Un échec de lancement ou un délai rend un `ProcResult`, jamais une exception.
- `toolrun.resolve` : git du poste s'il atteint la version minimale, sinon `<data>/tools/` ; sous macOS, `xcode-select -p` avant d'appeler `/usr/bin/git` ; paquets Python comparés à la version du registre (`importlib.metadata`) ; `offline_environment` (AD-12) et `run_tool`.
- `gitio.probe_language` : sonde `fr_FR.UTF-8` puis `fr_FR.utf8` (message d'un `git rev-parse` hors dépôt comparé à celui de `LC_ALL=C`).
- `diagnostic.run_diagnostic` : un `DiagnosticCheck` (`contracts`) par outil, plus la ligne de langue de git (informative, jamais bloquante, seulement si git est trouvé) et le proxy (URL sans identifiants, présence de `127.0.0.1` et `localhost` dans `NO_PROXY`, état de `UV_SYSTEM_CERTS`). Chaque résultat peut être émis par un callback `emit("diagnostic_check", payload)` (`events.DIAGNOSTIC_CHECK`).
- `content/diagnostic.yaml` : textes « Que faire ? », libellés d'état et gabarits.
- `config.py` (ajouts) : `tools_file`, `content_dir`, `probe_timeout_s`, `data_path()`, `read_proxy_environment()`, `inherited_environment()` (seul module qui lit l'environnement).
- Test de cohérence étendu (`tests/test_stack_versions.py`) : `tools.toml` ↔ table Stack ↔ `uv.lock` ↔ groupe `chain` de `pyproject.toml`, minimums d'AD-16.
- CI : `uv sync --locked --group chain` (report de la revue de la Story 1.1).

## Décisions

- Le registre vit dans `wavedevsecops/registry.py` (importe seulement `config`), pour que `toolrun`, `diagnostic` et les scénarios le partagent sans dépendance croisée.
- `DiagnosticCheck` est dans `contracts`, le `kind` dans `events` ; l'enveloppe complète d'événements (`boot_id`, `seq`, …) reste à la Story qui construit le flux SSE.
- Une sonde en échec ne bloque jamais le diagnostic : l'état `missing`/`too_old` porte la raison (délai dépassé, sortie illisible, fichier absent).
- La langue de git se détecte par comparaison du message avec celui de `LC_ALL=C` : fiable sans analyser de texte français.
- Les tests des sondes utilisent de faux outils (`sys.executable` ou un script) et ne dépendent pas de gitleaks ; ceux qui lancent le vrai git sont ignorés si git est absent.

## Reports

- `procs.spawn -> Handle` non bloquant et Job Object Windows : avec les stories qui exécutent des commandes longues (terminal, CI). `run` suffit aux sondes.
- Environnement hermétique complet de git (`GIT_CONFIG_COUNT`…) et contextes d'appel apprenant/interne : stories du terminal et du moteur.
- Page Diagnostic, route SSE et enveloppe d'événements : Story 1.5.
- Lecture de `tools.toml` par `install.ps1` et `install.sh` : stories des installeurs.
- Disponibilité des scénarios (outil requis absent) : story du catalogue.
