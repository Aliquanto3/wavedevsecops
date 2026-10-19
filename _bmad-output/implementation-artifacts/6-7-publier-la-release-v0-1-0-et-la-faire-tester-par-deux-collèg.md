---
story: "6.7"
key: 6-7-publier-la-release-v0-1-0
title: Publier la release v0.1.0 et la faire tester par deux collègues
status: review
branch: story/6-7-release-v0-1-0
ad: [AD-13, AD-18]
---

# Story 6.7 : Publier la release v0.1.0 et la faire tester par deux collègues

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 6.7 ». Type mixte : l'agent prépare, l'orchestrateur publie après la revue, Anaël et deux collègues font la recette.

## Préparé (dans la branche)

- `pyproject.toml` et `uv.lock` : `0.1.0` (`uv lock --offline`, `uv sync --locked` vérifié) ; `tests/test_seed.py` aligné. `__version__` vient des métadonnées du paquet ; aucun autre endroit ne porte la version.
- `README.md` : bandeau v0.1.0, énoncé AD-13 (« aucune télémétrie, aucun appel réseau, sauf l'exécution facultative du code LLM »), lancement, emplacement de la mesure du temps d'installation.
- `docs/releases/v0.1.0.md` : contenu, limites, temps d'installation et recette SM-1 à SM-4 à remplir.
- `CURRENT_MILESTONE` reste `v0.1`. La v0.1.0 montre pourtant la section « stations » du catalogue (7 scénarios), la carte de la chaîne et `/api/glossary` ; Vocabulaire et Fiche sont masqués. Signalé dans les notes de release.

## Reste humain ou à publier après la revue

1. Publier : tag annoté `v0.1.0`, release GitHub avec `docs/releases/v0.1.0.md` pour notes, description du dépôt, topics `ai-portfolio` et `status-test`, entrée `portfolio.json` (orchestrateur, après revue et CI verte sur trois OS).
2. Mesurer le temps d'installation (`install.json`, `duration_s`) et le consigner dans les notes (AD-18).
3. SM-1 : Anaël finit les scénarios du socle sans indice (quiz ≥ 80 % du premier coup). Sans tiers : « non validé par un tiers ».
4. SM-2 à SM-4 : deux collègues installent chronomètre en main (< 10 min), font branche, PR, conflit, récupération en 1 h au plus, expliquent le mode B ; consigner dans les notes.
5. Vérifier sur poste réel les points restés ouverts : 1.6 (Windows non admin, proxy), 1.7 (macOS, Linux), 6.6 (Ollama réel).

## Tests

Version : `tests/test_seed.py`. Aucune autre modification de code.
