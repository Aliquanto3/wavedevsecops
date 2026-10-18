---
story: "2.11"
key: 2-11-gabarits-exercice
title: Préparer les gabarits d'exercice des deux parcours
status: review
branch: story/2-11-gabarits-exercice
ad: [AD-7, AD-12, AD-13]
---

# Story 2.11 : Préparer les gabarits d'exercice des deux parcours

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.11 ».

## Livré

- `content/exercise/no_ai/` et `content/exercise/llm/` : petit projet Python « inventory » (stock d'un atelier : `Stock.add`, `remove`, `below_threshold`), chacun avec `pyproject.toml`, `uv.lock`, `tests/`, `.gitignore`, `.pre-commit-config.yaml` (hooks locaux hors ligne : ruff, pytest, gitleaks) et `README.md`. Les huit outils de la chaîne sont épinglés dans le groupe `chain`, aux versions de la table Stack, et verrouillés dans chaque `uv.lock`.
- Le code commun (`stock.py`, tests du stock, réglages) est identique octet pour octet ; seul le code d'exercice diffère. Le gabarit LLM ajoute : `llm.toml`, `llm_config.py` (lecture et refus d'un `base_url` hors `allowed_endpoints`), `llm_client.py` (`httpx` importé dans `post_json` seulement, `send` remplaçable), `__main__.py` (`python -m inventory "<question>"`, futur point d'entrée de `llmrun`), `tests/test_llm.py`, et la dépendance `httpx==0.28.1`.
- `llm.toml` : `base_url = "http://127.0.0.1:11434/v1"` (Ollama local), `allowed_endpoints` = ce seul endpoint.
- Stades du parcours LLM dans `content/exercise/llm/stages/<stade>/` : `simple_call` (appel simple), `system_prompt` (prompt système), `tools` (un tour d'outils), `loop` (boucle bornée à `MAX_STEPS`). Chaque stade apporte `src/inventory/assistant.py` et `tests/test_assistant.py`, qui remplacent ceux du stade précédent.
- Op de setup `exercise_stage {stage}` (`scenarios/ops/exercise_stage.py`) : copie le gabarit du parcours de l'espace (hors `stages/`) puis le stade demandé, en UTF-8 et LF par `wsfs`. `base` pour le parcours sans IA, un des quatre stades pour le parcours LLM ; un stade du mauvais parcours donne une `SetupError` en français.
- `Layout.track` (`wsfs`), `SetupContext.exercise_root` et paramètre `exercise_root` de `run_setup` ; `prepare_workspace` le passe depuis `Settings.content_path()` (une ligne dans `engine/workspace.py`).
- Scénarios `gabarit-llm.A` (quatre commits, un par stade) et `gabarit-sans-ia.A` (un commit) : ils portent les empreintes de référence de `content/fingerprints.json` sur les trois systèmes.
- Tests (`tests/test_exercise.py`) : fichiers requis, différence limitée au code d'exercice, outils verrouillés aux versions de la pile, `llm.toml`, chaque stade posé par l'op, erreurs, et les tests propres à chaque gabarit exécutés dans un sous-processus pytest (sans `httpx`, hors ligne, appel LLM remplacé). Ajouté à la liste `unshare -n` de la CI.

## Décisions

- Le champ `template` du scénario reste `empty` : les gabarits sont posés par l'op `exercise_stage`, comme le demande la story, pas par un second mécanisme.
- Les stades sont des surcouches de fichiers, pas des diffs : lisibles, et un scénario peut enchaîner n'importe quels stades.
- Chaque `ask` a la même signature `(question, config, stock=None, send=None)` à tous les stades, pour que `__main__.py` et les tests restent stables.
- `known-first-party = ["inventory"]` dans le `pyproject.toml` des gabarits : sans cela ruff classe `inventory.assistant` autrement selon le stade.

## Reports

- Les trois écritures du pipeline (`ci.yml`, `Jenkinsfile`, `.gitlab-ci.yml` avec balises `wds:job`) citées par AD-7 : absentes du critère de la story, à livrer avec la story du pipeline qui fixe les `job_id`.
- `httpx` (0.28.1) n'est pas dans la table Stack du spine : à y ajouter, avec une ligne pour le gabarit LLM.
- Vérification de FR-28 sur le vrai modèle et exécution de `llmrun` : hors périmètre ; aucun vrai modèle ni réseau utilisé ici.
- `uv.lock` des gabarits généré avec uv 0.12.23 en ligne ; la préchargement de `uv-cache` pour ces verrous relève de l'installeur (AD-12).

## Revue

Revue Opus, avec la liste du second avis (Haiku). Aucun constat high.

- medium · second avis 1 · corrigé : `allowed_endpoints` n'est pas une frontière de sécurité (l'apprenant édite les deux clés ; la frontière réseau est `llmrun`, AD-13). Le commentaire de `llm.toml` dit désormais ce que fait le code et invite à faire relire l'ajout d'un service distant ; l'oracle de `test_allowed_endpoints_are_loopback_only` comparait des préfixes (`http://localhost.exemple.test` passait) et compare maintenant le nom d'hôte. Le contrôle reste dans le gabarit, au niveau pédagogique.
- medium · second avis 2 · rejeté pour 2.11, reporté : les tests du gabarit lancés ici remplacent `send` et tournent sous `unshare -n` en CI Linux (AD-13, contrôle 4, sous-processus compris). L'exécution des tests du gabarit par `toolrun` (hook pre-commit, pipeline) n'existe pas encore ; la story qui la livre (station 1, hooks/`toolrun`, FR-21) doit vérifier qu'un test du gabarit ne peut pas sortir (proxy retiré ne suffit pas contre une connexion directe).
- medium · second avis 3 · corrigé : en CI (`WDS_EXERCISE_UV=1`), les tests des gabarits tournent dans leur environnement verrouillé, `httpx` 0.28.1 compris ; aucun test sauté n'est toléré, donc `test_post_json_uses_httpx_without_network` s'exécute (vérifié en local : 13 tests passés au stade `loop`).
- medium · second avis 4 · corrigé : la CI précharge le cache uv avec les deux `uv.lock` (seule étape réseau), puis `tests/test_exercise.py` crée l'environnement de l'espace (`cache/venv/`) par `uv run --offline --frozen`, comme AD-12 ; y compris sous `unshare -n`. Sans la variable (poste de dev), repli sur l'interpréteur de l'application.
- low · second avis 5 · reporté, décision à remonter : `httpx==0.28.1` absent de la table Stack du spine ; le test de cohérence AD-16 ne le couvre pas. Le spine n'est pas modifié ici.
- low · second avis 6 · corrigé : hooks `ruff` et `pytest` des deux gabarits en `uv run --offline --frozen` (un `uv run` sans `--frozen` peut réécrire `uv.lock`). Empreintes régénérées.
- low · second avis 7 · rejeté : `content/exercise/` est écrit par l'auteur, pas par l'apprenant ; un lien ou un binaire y ferait échouer `read_text` bruyamment au setup et en CI, sans effet silencieux.
- low · second avis 8 · rejeté : les scénarios `gabarit-*.A` portent les empreintes de référence des gabarits sur les trois systèmes (AD-18), comme `bac-a-sable-libre`. Leur visibilité au catalogue est à trancher par la story du catalogue.
