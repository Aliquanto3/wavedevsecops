---
story: "8.5"
key: 8-5-le-scénario-llm-outil-trop-puissant-flow-4
title: Le scénario LLM « outil trop puissant » (Flow 4)
status: review
branch: story/8-5-outil-trop-puissant
ad: [AD-7, AD-8, AD-10, AD-11]
---

# Story 8.5 : Le scénario LLM « outil trop puissant » (Flow 4)

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 8.5 » ; FR-24 à FR-28 (parcours LLM), UJ-3, SM-C4. Aucun job, aucun gabarit d'exercice, aucune dépendance ni modification du moteur : un scénario de contenu, son rang dans `STATION_ORDER` et ses tests.

## Livré

- **Scénario `outil-trop-puissant.A.yaml`** (parcours LLM seul, station 3, `STATION_ORDER` après `couverture-sous-le-seuil`). Départ : gabarit LLM au stade `loop`, `main` protégée par les sept checks et **deux approbations**. La branche `feature` porte un commit : `src/inventory/query_tool.py` (un outil `run_query` qui passe l'expression écrite par le modèle à `eval`, jamais importé ni testé) et `requirements.txt` avec `h11==0.14.0` (le `uv.lock` porte la 0.16.0). Les ops de setup sont celles qui existent (`write_file`, `replace_in_file`, `colleague_reaction`) : aucun gabarit de `content/exercise/llm` n'est modifié.
- **Étapes** : pousser, ouvrir la PR, lire le blocage (`bandit: failure`, `max_approvals: 0`, `mergeable: false` : le panneau affiche « bandit en échec » et « Approbations : 0 sur 2 »), restreindre l'outil (`bandit: success`), désigner `h11@0.14.0` dans le SBOM (`designate`), mettre h11 à jour (`pip_audit` et `uv_lock` verts, `sbom_has: [h11]`), tester l'outil (`quality_gate: success` avec `finding_has: [diff_coverage]`, `bandit` et `pytest` verts), constater les approbations (les sept checks verts, `min_approvals: 2`, `mergeable: true`), merger (`merged`, `min_approvals: 2`).
- **Deux approbations** : deux réactions `checks_green` sur `feature` (le collègue commente puis approuve, l'agent B approuve). Elles jouent une fois par `head_sha` quand tous les checks obligatoires sont verts ; `count_approvals` compte des auteurs distincts, donc 2 sur 2.
- **Défauts simultanés mais indépendants** : bandit, pip-audit et la quality gate échouent dès l'ouverture de la PR (le scénario nomme l'ordre à suivre), `uv_lock` reste vert (pyproject et lock inchangés). Les étapes de correction sont monotones (« vert »), donc valides même si l'apprenant corrige plusieurs défauts d'un coup ; seule la lecture du blocage (`bandit: failure`) et celle du SBOM (étape sans état) demandent le départ.
- **Leçon 6.2** : `# nosec` refusé (`--ignore-nosec`), `.bandit` du dépôt ignoré (`--ini` hors de l'arbre), module supprimé : bandit vert mais pas de constat `diff_coverage`, donc l'étape de test reste en attente ; dépendance retirée de `requirements.txt` : pip-audit vert mais `sbom_has` refuse.
- **Tests** : `tests/test_outil_trop_puissant.py` (scénario, dépôt de départ, protection et deux approbations qui arrivent quand les sept checks sont verts, étapes, désignation) ; tests lents avec les vrais outils (bandit B307, pip-audit h11 contre l'OSV local, quality gate 0 %, lint/tests/verrou verts au départ, tout vert après correction, contournements). Aucun appel à un modèle ni au réseau (OSV loopback). Empreintes régénérées, stables sur deux passes.

## Décisions

- **Outil = `eval`** (B307, comme la 8.1 mais donné à un LLM, avec le texte de l'explication sur l'injection de prompt) plutôt que `subprocess` : un correctif en `subprocess` resterait refusé par bandit (B404/B603), et « restreindre » doit pouvoir passer le check.
- **Module non branché** dans `assistant.py` : l'objectif est une couverture à 0 % déterministe sans toucher aux gabarits (consigne du run, 8.6 modifie le même dossier).
- **h11 0.14.0 dans `requirements.txt` seul** : transitif, absent de `dependencies`, donc `uv lock --check` reste vert sans refaire le verrou.
- **Deuxième approbateur : l'agent B** (persona existante) ; une persona « relecteur » dédiée toucherait `context.py` et le contrat de `colleague_reaction`.

## Reports

- Un module de remplacement sans rapport avec l'outil, mais testé, valide l'étape de test : `finding_has` ne désigne pas de fichier (limite déjà connue de 8.4).
- Une persona de relecteur humain distincte de l'agent B, si Anaël juge l'approbation de l'agent B déroutante.
- Débrief : lien entre l'outil trop puissant et l'injection de prompt (8.6).

## À vérifier sur poste réel

1. Parcours LLM, scénario « Bloquer un outil trop puissant donné au LLM » : pousser, ouvrir la PR ; « Merger » inactif, raisons « bandit en échec » et « Approbations : 0 sur 2 ».
2. Restreindre l'outil (sans `eval`), pousser : bandit vert ; pip-audit toujours rouge ; SBOM, ligne h11 0.14.0 ; corriger à 0.16.0.
3. Ajouter `tests/test_query_tool.py` : la quality gate passe, puis les deux revues arrivent et « Merger » devient actif.
