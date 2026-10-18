---
story: "6.6"
key: 6-6-execution-llm
title: Exécuter, en option, le code d'exercice du parcours LLM
status: review
branch: story/6-6-execution-llm
ad: [AD-1, AD-6, AD-12, AD-13, AD-19]
---

# Story 6.6 : Exécuter, en option, le code d'exercice du parcours LLM

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 6.6 ». Reprend le report de la story 7.1 (`llmrun` lance sans `WDS_NETGUARD`, avec les proxy de l'apprenant).

## Livré

- **`llmrun`** (nouveau composant, seul autorisé à lancer un processus qui peut sortir sur le réseau) :
  - `exercise_environment` : `toolrun.offline_environment` sans `WDS_NETGUARD`, variables de proxy de l'apprenant rétablies par `config.read_proxy_environment` (majuscules, plus minuscules hors Windows). `NO_PROXY` garde les exclusions de l'apprenant et ajoute `127.0.0.1,localhost` (Ollama local ne passe jamais par un proxy).
  - `start_exercise(layout, settings)` : `python -m inventory "<question>"` dans `cache/venv/`, cwd `repo/`, délai `Settings.llm_run_timeout_s` (180 s), par `toolrun.spawn_module` → `procs.spawn` (sortie au fil de l'eau, Job Object, arrêt d'arbre). Rend le `Handle` ; si le venv manque, il est créé hors ligne par `toolrun.sync_environment`. Rien de lancé : `ExerciseUnavailable`.
  - Environnement réduit (revue) : des variables héritées, seules `PASSED_VARIABLES` passent (système, `TEMP`, `HOME`, locale, certificats) ; jetons, clés d'API et `PYTHONPATH` ne sont pas transmis.
  - `llmrun` ne parle qu'à `toolrun` (spine) : il n'importe ni `procs` ni `subprocess`, ni aucune bibliothèque réseau (le code d'exercice, lui, tourne dans un autre processus).
- **`toolrun`** : `venv_python`, `spawn_module(venv, module, args, env=, cwd=, timeout=) -> Handle` (l'environnement est explicite, il n'impose pas la garde), `offline_environment(settings, base=None)` et `Handle` / `ProcResult` ré-exportés pour `llmrun`.
- **Intention `run_exercise_code`** (`web/exercise.py`, enregistrée par `create_app`, idempotent) :
  - corps `{confirmed: bool}` (`extra="forbid"`) ; sans `confirmed: true` : 409 avec `reason_text` (AD-19, vérifié côté serveur) ; autre champ ou type faux : 422 ; parcours `no_ai` : 409.
  - sans cookie `wds_session` : 401, `Origin` étranger : 403 (intergiciel de `web/app.py`, inchangé).
  - opération de la file en état `command` (`writes=True`, refusée en `quiz_altered`, `validate=False`) : instantané, puis ligne `$ python -m inventory "…"` (flux `app`), puis stdout et stderr au fil de l'eau dans `terminal_output`. Code de sortie dans `op_exit` (124 au délai, 130 à l'interruption).
  - `interrupt` (Ctrl+C) et la mise en veille de l'espace arrêtent l'arbre (`ctx.on_interrupt(handle.terminate)`).
  - échecs en `app_error` en français : instantané impossible (rien n'est lancé), venv indisponible ; délai dépassé et arrêt : ligne dans le terminal.
- **Instantanés** : API de la story 4.3 (`take_snapshot(layout, git, settings, reason="exercise", expected=fingerprint(...))`), avant tout lancement. L'instantané 0 reste celui du setup ; l'empreinte est calculée sur la copie et contrôlée contre celle de l'espace. La version propre à 6.6 (`fingerprint.txt`, `wsfs.copy_entries` sans réessais) est retirée au rebase.
- **Lint de contenu** (`scenarios/model.py`) : une étape qui nomme `run_exercise_code` (type, clé ou valeur, à toute profondeur) est refusée avec la ligne du champ.
- **Front** (`js/network-run.js`, monté par `workspace.js` pour le parcours `llm` seulement) : `network-run-button` « Exécuter le code (réseau possible) » dans le panneau Scénario, confirmation en ligne « Ce code peut appeler un service en ligne. Continuer ? » (focus sur « Annuler », Échap ferme et rend le focus), envoi seulement après « Continuer ». Bouton inactif avec sa raison (`bindAction`) tant que l'espace n'est pas au repos ; le refus du serveur s'affiche dans la zone d'erreur du panneau.
- Tests : `test_llmrun.py` (environnement réduit, vrai sous-processus sans garde et avec proxy, délai, interruption de l'arbre, venv absent), `test_exercise_intent.py` (vrai serveur, lancement remplacé par un faux `Handle` : confirmation, 409/422/401/403, parcours, instantané `exercise` avant le lancement, état `command`, ordre des événements, échecs, `interrupt`), `test_step_lint.py`, `test_network_run_dom.py` (Node, `minidom`). Les contrôles AD-13 existants (`test_offline_rules.py`, `test_architecture.py`) couvrent « seul `llmrun` peut importer une bibliothèque réseau » ; aucun test n'appelle un modèle ni le réseau.

## Décisions

- La question posée est fixe (`DEFAULT_QUESTION`) : le point d'entrée du gabarit exige un argument et l'intention ne porte que la confirmation. Une saisie libre demanderait un champ de plus dans l'intention et dans l'interface.
- `llmrun` n'importe pas `engine` : l'opération (instantané, sortie dans le terminal) est assemblée dans `web/exercise.py`, conformément aux flèches du spine (`web` → `engine`, `web` → `llmrun`, `llmrun` → `toolrun`).
- Les écritures de l'instantané vont dans `wsfs` (règle « seul `wsfs` écrit dans le bac à sable »).
- Le venv est créé à la demande s'il manque (hors ligne) ; la story 7.2 le créera à l'ouverture de l'espace et ce chemin ne servira plus que de secours.

## Reports

- Création du venv à la demande (`uv sync`, jusqu'à 600 s) : pas encore interruptible. La story 7.2 crée le venv à l'ouverture de l'espace ; ce chemin ne sert alors que de secours.
- Bouton « Rétablir » après l'exécution : l'instantané `exercise` est pris ; l'action de restauration relève de 4.4/4.5.
- Saisie libre de la question et choix de l'endpoint depuis l'interface : hors périmètre.

## À vérifier sur poste réel (vrai modèle)

1. Ollama lancé (`llama3.2`), parcours LLM : le bouton, la confirmation, puis la réponse du modèle dans le terminal.
2. Ollama arrêté : le message d'erreur du code d'exercice s'affiche dans le terminal, l'espace revient au repos.
3. Derrière un proxy d'entreprise, `base_url` distant autorisé dans `llm.toml` : l'appel passe par le proxy de l'apprenant.
4. Le même code, lancé depuis le terminal de l'application ou par un test du gabarit, reste refusé hors loopback (garde réseau).

## Revue

Rebase sur `main` (6860667, après 4.3, 2.4, 4.1). Second avis (Haiku) repris un par un.

- HIGH, second avis : instantané 0 pris après les éditions (contraire à AD-6). Confirmé sur la version propre à 6.6. Corrigé : API 4.3, le 0 est celui du setup, l'exécution prend un instantané `exercise` en plus.
- MEDIUM, second avis : instantané non vérifié par empreinte. Confirmé. Corrigé : empreinte calculée sur la copie et contrôlée contre `fingerprint(layout, git)` (`expected`), `SnapshotError` sinon. Test : empreinte de l'instantané `exercise` = celle du setup.
- MEDIUM, second avis : 780 s sans interruption possible. Confirmé (180 s d'exécution + 600 s de `uv sync`). Corrigé pour l'exécution (`procs.spawn`, `ctx.on_interrupt`). Reporté pour `uv sync` (voir Reports).
- MEDIUM, second avis : processus orphelin à l'arrêt de l'application. Confirmé (`procs.run` bloquant, sans arrêt lié à la file). Corrigé : `request_stop` interrompt l'opération, donc l'arbre ; Job Object `KILL_ON_JOB_CLOSE` sous Windows.
- MEDIUM, second avis : environnement complet transmis au processus qui peut appeler le réseau. Confirmé. Corrigé : `PASSED_VARIABLES` seulement (+ proxy, + variables des outils) ; test avec `GITHUB_TOKEN`, `PYTHONPATH` et une variable `WDS_*` non transmis.
- MEDIUM, revue : `toolrun.run_module` lançait par `procs.run` (bloquant, sortie d'un bloc). Corrigé : `spawn_module` → `procs.spawn` (AD-1 : seul `procs` crée des processus, appelé par `toolrun`).
- LOW, revue : code de sortie `None` au délai. Corrigé : 124 / 130 comme le terminal (2.4).
- LOW, revue : lint d'étape (`_mentions`) aussi sur les textes ; avec les types d'étape fermés (4.x), un champ ajouté est déjà refusé par le schéma. Gardé (défense en profondeur) ; tests adaptés.
- LOW, revue : le refus du serveur (409) reste affiché dans le panneau jusqu'à la prochaine relecture de l'état (`store.fail`). Rejeté : même comportement que les autres refus du panneau.
- LOW, revue : la question est fixe (`DEFAULT_QUESTION`). Rejeté : décision de la story.
- Complexité : 0 constat (aucune structure qui grossit ; la sortie est émise morceau par morceau).

À vérifier par Anaël sur poste réel (Ollama) : la liste « À vérifier sur poste réel » ci-dessus, plus Ctrl+C pendant une réponse lente du modèle (arrêt sous 2 s, code 130, espace au repos).
