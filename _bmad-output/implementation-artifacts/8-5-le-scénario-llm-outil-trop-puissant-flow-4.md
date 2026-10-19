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
- **Deux approbations** (revue, arbitrage B) : deux réactions `checks_green` sur `feature`, deux relecteurs humains distincts : Sacha (le collègue) commente puis approuve ; Noé Lefèvre (persona `reviewer`, nouvelle, revues seulement) lit `query_tool.py` au commit de tête (`when_files`) et n'approuve que si l'outil ne nomme plus `eval`, `exec`, `getattr`, `__import__`, `builtins`, `__builtins__` ni `importlib` ; sinon il demande des changements (`otherwise`). Elles jouent une fois par `head_sha` ; `count_approvals` compte des auteurs distincts, donc 2 sur 2. L'agent B n'approuve plus (il approuvait sur checks verts sans lire).
- **Défauts simultanés mais indépendants** (critère reformulé, arbitrage A) : bandit, pip-audit et la quality gate échouent dès l'ouverture de la PR ; l'apprenant les corrige dans l'ordre bandit → pip-audit → quality gate, ordre que le texte des étapes guide (le critère d'origine « bandit passe, puis pip-audit échoue » se lit ainsi), `uv_lock` reste vert (pyproject et lock inchangés). Les étapes de correction sont monotones (« vert »), donc valides même si l'apprenant corrige plusieurs défauts d'un coup ; seule la lecture du blocage (`bandit: failure`) et celle du SBOM (étape sans état) demandent le départ.
- **Leçon 6.2** : `# nosec` refusé (`--ignore-nosec`), `.bandit` du dépôt ignoré (`--ini` hors de l'arbre), module supprimé : bandit vert mais pas de constat `diff_coverage`, donc l'étape de test reste en attente ; dépendance retirée de `requirements.txt` : pip-audit vert mais `sbom_has` refuse. Revue : condition `head_files` des étapes `restreindre_l_outil` et `tester_l_outil` (le fichier existe au commit de tête et ne nomme aucun identifiant interdit, mot entier) ; les contournements que bandit ne voit pas (`builtins.eval`, `getattr(builtins, "ev" + "al")`, `__builtins__["eval"]`) laissent les étapes en attente et font demander des changements par Noé.
- **Tests** : `tests/test_outil_trop_puissant.py` (scénario, dépôt de départ, protection et deux approbations qui arrivent quand les sept checks sont verts, étapes, désignation) ; tests lents avec les vrais outils (bandit B307, pip-audit h11 contre l'OSV local, quality gate 0 %, lint/tests/verrou verts au départ, tout vert après correction, contournements). Aucun appel à un modèle ni au réseau (OSV loopback). Empreintes régénérées, stables sur deux passes.

## Décisions

- **Outil = `eval`** (B307, comme la 8.1 mais donné à un LLM, avec le texte de l'explication sur l'injection de prompt) plutôt que `subprocess` : un correctif en `subprocess` resterait refusé par bandit (B404/B603), et « restreindre » doit pouvoir passer le check.
- **Module non branché** dans `assistant.py` : l'objectif est une couverture à 0 % déterministe sans toucher aux gabarits (consigne du run, 8.6 modifie le même dossier).
- **h11 0.14.0 dans `requirements.txt` seul** : transitif, absent de `dependencies`, donc `uv lock --check` reste vert sans refaire le verrou.
- ~~Deuxième approbateur : l'agent B~~ remplacé en revue (arbitrage B) par un second relecteur humain, Noé Lefèvre (`PERSONAS["reviewer"]`, exclu des `ACTORS` de commit).

## Reports

- ~~Un module de remplacement sans rapport avec l'outil valide l'étape de test~~ : traité en revue, l'étape exige `query_tool.py` au commit de tête (`head_files`). Limite restante, dite au débrief de l'étape : `diff_coverage` est un total ; un outil gardé mais peu testé, compensé par beaucoup de nouveau code testé ailleurs, franchit encore le seuil.
- ~~Persona de relecteur humain distincte~~ : livrée en revue (Noé).
- Débrief : lien entre l'outil trop puissant et l'injection de prompt (8.6).

## À vérifier sur poste réel

1. Parcours LLM, scénario « Bloquer un outil trop puissant donné au LLM » : pousser, ouvrir la PR ; « Merger » inactif, raisons « bandit en échec » et « Approbations : 0 sur 2 ».
2. Restreindre l'outil (sans `eval`), pousser : bandit vert ; pip-audit toujours rouge ; SBOM, ligne h11 0.14.0 ; corriger à 0.16.0.
3. Ajouter `tests/test_query_tool.py` : la quality gate passe, puis les deux revues arrivent et « Merger » devient actif.

## Revue

Revue Opus (une passe), 2026-10-19, sur `a0d3733` rebasé sur `main` (`f917b1a`, à jour). Arbitrages d'Anaël A à F appliqués.

| Sévérité | Source | Constat | Issue |
|---|---|---|---|
| high | second avis 1 | `restreindre_l_outil` validée par `bandit: success` seul ; `builtins.eval(...)`, `getattr(builtins, "ev"+"al")(...)`, `__builtins__["eval"](...)` passent bandit sans constat (prouvé par le test lent) | Corrigé : `HeadFile` (`contracts/github.py`), `github_sim.head_files_ok` (lecture de `origin.git` au `head_sha`, identifiants interdits en mots entiers), condition `head_files` de `pr_state` sur les deux étapes, relecteur Noé conditionné au même critère. Limite documentée (explication de l'étape et docstring) : tout critère textuel reste contournable (`importlib` évité par `sys.modules["built" + "ins"]`…) ; la relecture humaine est la dernière barrière. |
| medium | second avis 2, arbitrage B | Deuxième approbation donnée par l'agent B, persona IA qui approuve sur checks verts sans lire | Corrigé : persona `reviewer` (Noé Lefèvre) dans `context.py`, `colleague_reaction.author` accepte `reviewer`, `Reaction.when_files`/`otherwise` (ajout optionnel, absent de l'empreinte quand vide : aucune autre empreinte ne bouge). Tests : deux auteurs humains distincts ; contournement → `changes_requested`, 1 sur 2, bloqué ; outil restreint au commit suivant → 2 sur 2. |
| medium | second avis 3, arbitrage D | Un module sans rapport, testé, valide l'étape de test | Corrigé : `tester_l_outil` exige `query_tool.py` au commit de tête (`head_files`). Limite (total de couverture) dite à l'apprenant et en Reports. |
| medium | arbitrage A | Critère « bandit passe, puis pip-audit échoue » alors que les trois défauts échouent ensemble | Reformulé dans « Livré » (ordre guidé par le texte), comportement gardé. |
| medium | arbitrage E | Limites de la quality gate non nommées | Corrigé : débrief de `couverture-sous-le-seuil.A` (`ajouter_les_tests`) et de `tester_l_outil` : test sans `assert`, code de la CI qui réécrit sa mesure, d'où la revue humaine. |
| medium | arbitrage F | Échec de `uv_lock` sans phrase française | Corrigé : lecteur `uv_lock_check` (`ci/findings.py`, constat `lock_mismatch` sur `uv.lock`), exécution machine `when: failure` dans `content/pipeline.yaml` ; sortie brute de uv gardée. Tests : lecteur (rapide), vrai `uv lock --check` (lent), contrat du job. |
| low | second avis 4 | Contournements « dépendance déplacée vers pyproject » et « # noqa » non testés | Corrigé : test lent (`# noqa` laisse bandit rouge ; h11 déplacé dans `pyproject.toml` fait échouer `uv_lock`). |
| low | second avis 5 | Pas d'entrée de glossaire pour le scénario | Rejeté : aucun terme nouveau (SAST, SCA, SBOM, quality gate, quatre yeux existent) ; `sast` attend `code-vulnerable` (8.1, `tests/test_glossary.py`), et 9.6 modifie le glossaire en parallèle. |
| — | revue | Complexité : 0 constat (`_react` lit au plus un fichier par réaction due et non jouée ; `head_files` évalué en dernier, après les conditions d'état) | — |

Tests de la revue : ruff vert ; 296 tests rapides ciblés (20 fichiers : scénario, github_sim, collègue, agent, projections, pipeline, quality gate, empreintes, glossaire, architecture) ; lents : `test_outil_trop_puissant` (vrais outils, contournements, angles morts de bandit) et `test_uv_lock_check_refuse_un_pyproject_sans_verrou_a_jour`, verts. Empreintes : seule `llm/outil-trop-puissant.A` change, stable sur deux passes.
