---
story: "7.2"
key: 7-2-lancer-ruff-et-pytest-dans-le-terminal
title: Lancer ruff et pytest dans le terminal (station 1, poste local)
status: review
branch: story/7-2-ruff-pytest-terminal
ad: [AD-1, AD-4, AD-10, AD-12, AD-13, AD-14]
---

# Story 7.2 : Lancer ruff et pytest dans le terminal

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 7.2 » ; spine AD-4, AD-10, AD-12, AD-14 ; UX-DR13, UX-DR20. Reprend le report de la story 7.1 (créer le venv à l'ouverture de l'espace) et celui de la 6.6 (`uv sync` non interruptible).

## Livré

- **Garde** (`content/terminal-allowlist.yaml`, section `tools`, modèle `ToolSpec`) : `ruff check [--fix] [--statistics] [--show-fixes] [--diff] [--select V] [--ignore V] [--no-cache] [chemins]` et `pytest [-q -v -vv -x -k V -m V --tb V --maxfail V -r V -l --collect-only --no-header --disable-warnings] [chemins]`. Un seul fichier, lu par la garde et par le texte des refus (qui cite maintenant « Outils acceptés quand l'étape les déclare : ruff, pytest »). Ni `-p`, ni `-c`, ni `--rootdir`, ni `--config`, ni `--junitxml` : aucune option ne charge un greffon ni ne change la racine ni ne sort du dépôt. Les chemins sont confinés par `wsfs.check_relative` (`.` admis, `::node` de pytest admis, `..`, absolu et `.git` refusés). `ruff format` et toute autre sous-commande : refusées avec la liste. `--fix` est la seule écriture (`writes` vrai, donc refusée en `quiz_altered`).
- **Outil déclaré par le scénario** (AD-4) : `terminal.declared_tools(engine)` lit `tools` du scénario de l'espace (`run.json` -> fichier, relu quand il change). Hors de cette liste : refus `terminal-refused` « « ruff » n'est pas disponible dans ce scénario : ses étapes ne déclarent pas cet outil. » suivi de la liste acceptée.
- **Exécution** (`terminal/tools.py`, `toolrun.spawn_tool`, `toolrun.collect`) : l'outil est résolu dans `cache/venv/` de l'espace (`resolve(..., venv=)`, version comparée au `uv.lock`), lancé hors ligne avec `offline_environment` (garde réseau comprise), cwd `repo/`, délai `Settings.tool_timeout_s` (120 s), arbre arrêtable (Ctrl+C, mise en veille : `ctx.on_interrupt(handle.terminate)`, codes 130 et 124). Outil absent ou abîmé : message en français qui reprend la raison du diagnostic (« environnement abîmé … (uv sync) »), code 127, aucune preuve.
- **Bloc `tool-output`** : la sortie est émise en un seul `terminal_output` (nouveau champ `tool`, nom de l'outil), texte verbatim (stdout puis stderr), jamais réécrit. Le front (`terminal.js`) le dessine en bloc `div.tool-output` (`role="group"`, `tabindex="0"`, `aria-label="Sortie de ruff"`, étiquette au nom de l'outil, `data-element-id="output:<op_id>"`) : un clic ou Entrée le désigne par la sélection partagée (`selectionFor`). Code non nul : « Code de sortie : n » comme les autres commandes.
- **Liens fichier:ligne tirés d'une exécution machine** (AD-10, `toolrun/findings.py`) : si l'outil échoue, il est relancé en mode machine sur le même arbre. ruff : mêmes arguments sans `--fix --statistics --show-fixes --diff`, plus `--output-format json --no-fix` (fichier et ligne exacts). pytest : mêmes arguments plus `--junitxml <cache> --tb=no -q` (les fichiers des tests en échec ou en erreur, le nom de classe étant le chemin du module). Seuls les passages `chemin:ligne` du texte humain que ces constats désignent deviennent des `spans` (fixes, jamais recalculés par la file) avec `element_id` `path:worktree:<chemin>` ; positions en unités UTF-16, séparateurs `\` ou `/`. Une exécution machine en échec garde la sortie intacte, sans lien, avec un message d'information.
- **Preuve** (AD-14) : `OpContext.submit_evidence(barrier_id)` soumet le fait `evidence_seen{barrier_id}` (nouveau `kind` de `progress.facts`, champ `barrier_id`, identité `(kind, parcours, scénario, mode, barrier_id)`, premier passage seul) quand la sortie s'est affichée et que l'outil n'a pas été arrêté. Barrière par outil dans le fichier de la liste blanche : `ruff` -> `lint`, `pytest` -> `tests` (ids de `content/chain.yaml`).
- **Environnement d'exercice à l'ouverture** (report 7.1) : `prepare_workspace` crée `cache/venv/` par `toolrun.sync_environment` si le scénario déclare un outil de résolution `uv-lock` (`toolrun.needs_environment`). Un échec est journalisé et n'empêche pas l'ouverture : la première commande de l'outil retente (secours interruptible) et dit pourquoi.
- **`uv sync` interruptible** (report 6.6) : `sync_environment(..., on_start=)` lance par `procs.spawn` et passe le `Handle` à l'appelant ; `terminate` arrête l'arbre et le résultat est `error="interrompu"`. Branché sur Ctrl+C et la mise en veille dans le terminal (secours) et dans `web/exercise.py` (`llmrun.start_exercise(..., on_sync=)`).
- **Scénarios de station 1, dans les deux parcours** : `defaut-de-lint.A` (un module `src/inventory/rapport.py` non committé qui importe `os` sans s'en servir : F401) et `test-casse.A` (un test `tests/test_rupture.py` non committé qui attend un résultat faux). `tracks: [llm, no_ai]`, `station: 1`, `tools: [git, ruff]` / `[git, pytest]`. Nouvelle valeur `stage: auto` de l'op `exercise_stage` (premier stade du parcours : `base` ou `simple_call`) pour servir les deux parcours avec le même code d'exercice. Empreintes de référence ajoutées (`content/fingerprints.json`).
- Tests : `tests/test_terminal_tools.py` (garde 27 cas, constats machine, liens et UTF-16, espace réel sur les deux scénarios avec outil remplacé : bloc, liens, preuve et son premier passage, refus hors déclaration, outil indisponible, Ctrl+C, délai, `--fix` en écriture, création du venv, secours interruptible ; vrais ruff et pytest dans les deux parcours si `WDS_EXERCISE_UV=1`, ajouté au job « Scénarios sans réseau (unshare -n) » de la CI) ; `test_terminal_dom.py` (bloc, liens, désignation, `splitSpans`) ; `test_toolrun.py` (`sync_environment` par `spawn`, `on_start`, arrêt de l'arbre).

## Décisions

- Les outils sont déclarés au niveau du scénario (`tools`, déjà dans le modèle), pas par étape : le modèle d'étape ne porte pas de liste d'outils, et la story 4.6 (moteur d'étapes) est en cours. Une déclaration par étape reste possible plus tard sans changer la garde.
- Un seul `terminal_output` par exécution d'outil, émis à la fin : les `spans` doivent venir de l'exécution machine, qui suit la sortie humaine. Pendant l'exécution, le chronomètre « En cours… n s » du terminal tient lieu de retour. L'inconvénient est connu : un pytest très long n'affiche rien avant sa fin.
- pytest n'a pas de sortie machine avec les numéros de ligne : le lien est posé sur tout `chemin:ligne` du texte dont le chemin est celui d'un test en échec (constat machine = le fichier). Les lignes d'une trace qui pointent le code applicatif ne sont pas liées.
- Le lien désigne `path:worktree:<chemin>` : la grammaire d'AD-2 n'a pas de segment ligne pour un chemin. L'ouverture à la bonne ligne dépend de la vue Code (story 2.8) ; le passage lié couvre tout `chemin:ligne`.
- Les sorties ne sont pas rejouées après un rechargement de la page (comme le reste du terminal).
- `exercise_stage: auto` plutôt que quatre scénarios (un par défaut et par parcours) : le catalogue n'a ainsi qu'un défaut de lint et qu'un test cassé, servis aux deux parcours.

## Reports

- Validation d'étape sur le contenu : les étapes des deux scénarios exigent un commit en avance sur `origin/main` et l'index propre, pas que ruff ou pytest passent. Un type d'étape qui lance l'outil (ou lit le résultat) est à écrire avec le moteur d'étapes (4.6).
- Ouverture de la vue Code à la ligne : vue Code (2.8) et segment ligne de l'`element_id`.
- `gitleaks` et `pre-commit run` dans le terminal : story 7.3 (même section `tools` du fichier de la liste blanche).
- `pytest` n'accepte pas `--lf`, `--ff` (le cache pytest est désactivé par `-p no:cacheprovider`, AD-12).

## À vérifier sur poste réel

1. Windows, macOS, Linux : `ruff check .` dans « Trouver un défaut de lint avant de committer », puis la correction (`ruff check --fix .` ou à la main) et le commit : l'étape passe.
2. `pytest` dans « Trouver un test cassé avant de committer » : l'échec affiche `tests/test_rupture.py:7` en lien ; un clic sélectionne le fichier.
3. Réseau coupé : les deux outils tournent (cache uv préchargé) ; ouverture du scénario sans cache : la première commande dit « L'environnement de l'exercice n'a pas pu être préparé ».
4. Ctrl+C pendant `pytest` (test lent) : arrêt sous 2 s, code 130, aucune preuve vue.
5. Lecteur d'écran : le bloc est annoncé « Sortie de ruff, groupe », les liens sont des boutons.
