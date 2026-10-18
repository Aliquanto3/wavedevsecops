# Revue de l'ARCHITECTURE-SPINE WaveDevSecOps contre la grille « bonne colonne vertébrale »

Date : 2026-10-18. Cible : `ARCHITECTURE-SPINE.md` (draft), PRD `prd-wavedevsecops-2026-10-18`.
Gravités : critical (une capability du PRD est inatteignable ou une garantie centrale est fausse), high (divergence quasi certaine entre stories ou défaut de sécurité/fiabilité), medium (trou à combler avant le découpage), low (précision utile).

## Verdict

Colonne solide sur le cœur (un écrivain, projections, hermétisme git, instantanés par empreinte, registre d'outils), mais elle n'est pas prête pour le découpage : un mécanisme central (éditeur sentinelle) bloque des commandes que les scénarios exigent, l'API locale n'est pas protégée alors qu'elle déclenche des exécutions, la garde du terminal repose sur une liste noire d'options, et toute l'enveloppe opérationnelle après la première installation (mise à jour, instance unique, reprise sur incident) n'est ni décidée ni différée.

## Synthèse par critère de la grille

| Critère | État |
|---|---|
| Fixe les vrais points de divergence du niveau inférieur | Partiel : bons AD sur git, événements, scénarios ; manquent alias de SHA dans les scénarios, contrat d'enregistrement de fichier, modèle de concurrence, schéma `github.json` versionné |
| Chaque Rule est applicable et empêche sa divergence | Partiel : AD-3 (éditeur), AD-4 (options), AD-6 (impasse), AD-13 (contrôle 3) ont des failles |
| Rien dans Deferred ne peut faire diverger deux unités | Presque : station 4 (voir M-9) et invocation de pip-audit (voir M-6) touchent déjà des invariants posés |
| Couvre les capabilities | Oui sur FR/NFR ; trous : ouverture de l'éditeur externe (FR-3), mesure des temps d'indice (FR-13), carte (FR-32) sans contenu déclaré |
| Enveloppe opérationnelle | Insuffisant : installation décidée, mise à jour, désinstallation, instance unique, reprise sur incident, intégrité des téléchargements et test des installeurs absents |
| Cohérence interne | Plusieurs flèches manquantes et deux contradictions (voir H-7, M-1) |

---

## Constats critiques

### C-1 — L'éditeur sentinelle (code 1) rend inutilisables `revert`, `rebase --continue` et probablement `merge --continue` (AD-3)

- **Problème.** AD-3 : « Aucune commande ne lance d'éditeur » ; l'éditeur sentinelle écrit un marqueur et sort en code 1, puis `terminal` affiche « Ajoutez -m ». Or `git revert <c>` (liste blanche d'AD-4, indispensable au scénario de reflog/reset), `git rebase --continue` après résolution de conflit (scénarios rebase et « rebase laissé en conflit », FR-12) et `git merge --continue`/`git commit` sans `-m` après conflit (UJ-2) ouvrent l'éditeur et n'ont pas d'équivalent `-m`. `GIT_MERGE_AUTOEDIT=no` ne couvre ni `revert` ni `cherry-pick` ni `rebase --continue`. L'apprenant est bloqué sur la forme canonique de la commande que le scénario veut lui apprendre ; la validation sur l'état (FR-11) ne se déclenche jamais.
- **Correctif.** Remplacer la règle unique par une politique par commande, dans le fichier de données de la liste blanche (AD-4) :
  - sentinelle « échec + message » seulement pour `commit` sans `-m`/`-F`/`--no-edit`/`--amend` et `tag -a` sans `-m` ;
  - pour `revert`, `merge`, `pull`, `rebase --continue`, `merge --continue`, `cherry-pick --continue`, `commit` en cours de merge (MERGE_MSG présent) : `GIT_EDITOR=:` (l'éditeur « accepte » le message préparé), éventuellement `--no-edit` injecté et affiché dans une ligne `terminal-app-message`.
  - Ajouter un test de scénario par commande « continue ».

---

## Constats élevés

### H-1 — API locale sans authentification : exécution de code déclenchable depuis n'importe quelle page web (AD-17, AD-13, NFR-12)

- **Problème.** Le serveur écoute sur `127.0.0.1:<port>` et accepte des `POST` JSON qui lancent des sous-processus (terminal, outils, `run_exercise_code` qui exécute le code du dépôt d'exercice avec le réseau). Une page ouverte dans le même navigateur peut cibler `127.0.0.1:<port>` (formulaires cross-origin, rebinding DNS, ports balayés). Combiné à l'intention d'enregistrement de fichier, c'est une exécution arbitraire. Pour un produit qui enseigne la sécurité, c'est incohérent avec NFR-9 et le modèle de menace (« erreur de l'apprenant ») ne couvre pas ce vecteur. Même défaut pour `POST /osv/v1/query` (inoffensif) et la route de téléchargement des exports.
- **Correctif.** Nouveau AD « Surface HTTP » : jeton aléatoire par lancement (dans l'URL ouverte, puis cookie `HttpOnly; SameSite=Strict`), vérification de `Host` (`127.0.0.1:<port>` / `localhost:<port>`) et de `Origin` sur tout `POST` et sur le flux SSE, pas de CORS, `Content-Type: application/json` obligatoire. L'OSV local accepte aussi le jeton (passé à pip-audit via `--osv-url` avec jeton dans le chemin) ou n'accepte que les requêtes sans `Origin` venant de `toolrun`. Test de CI qui vérifie le refus.

### H-2 — La garde du terminal est une liste noire d'options sur une liste blanche de sous-commandes (AD-4)

- **Problème.** La règle interdit `-c`, `-C`, `--git-dir`, etc., mais laisse passer des options qui lisent ou écrivent hors du bac à sable ou lancent un programme :
  - `git fetch|pull|push --upload-pack=<cmd>` / `--receive-pack=<cmd>` / `--exec` ;
  - `git log|diff|show --output=<fichier>` (écriture arbitraire), `git diff --no-index <a> <b>` (lecture hors bac à sable), `--ext-diff`, `--textconv` ;
  - `git commit -F <fichier>`/`--template`, `git tag -F`, `git blame --contents`, `git apply`-like via `--patch` ;
  - `git rebase --exec` est interdit mais pas `git merge --strategy-option`/`-s` externes ni `git pull --rebase=interactive`.
  La Prevents annonce pourtant « un --exec ou une URL ». Une liste noire ne peut pas être exhaustive.
- **Correctif.** Passer à une liste blanche d'options par sous-commande dans le fichier de données (par exemple `commit: [-m, -a, --amend, --no-edit, ...]`), refuser tout le reste avec le texte de refus généré depuis ce fichier, et valider les arguments positionnels (chemins résolus sous la racine, refs sans `:` ni `@{`... selon la commande). Ajouter au jeu de tests de confinement un corpus d'options hostiles.

### H-3 — Aucun contrat de mise à jour de l'application ni de migration des données (opérations, release, AD-5, AD-14, AD-17)

- **Problème.** L'installation est décidée (AD-15) ; la mise à jour ne l'est pas, ni différée. Pourtant NFR-11 prévoit une release par jalon (v0.1 → v0.3 → v1.0) et les apprenants gardent `<data>/` entre versions. Conséquences non traitées : `progress.json` (`schema_version` sans règle de migration), `github.json` (modèle de PR figé en v0.1 mais étendu par les stations 2 à 4), `run.json` et `snapshots/` d'un espace commencé avec une version précédente alors que le YAML du scénario, son setup et son empreinte de référence ont changé (« Ouvrir un scénario déjà commencé reprend son espace »), outils provisionnés (`tools.toml`) dont les versions changent, cache uv à régénérer.
- **Correctif.** Ajouter un AD « Cycle de vie des versions » :
  - chaque espace porte dans `run.json` `app_version`, `scenario_hash` et l'empreinte de référence utilisée ; si le hash du scénario diffère, l'espace est proposé en « Recommencer » avec avertissement, jamais repris silencieusement ;
  - migrations ordonnées et idempotentes pour `progress.json` et `github.json` (`schema_version` → fonction), copie de sauvegarde `progress.json.bak` avant migration ;
  - procédure de mise à jour dans les installeurs (`install.* --update` : récupérer le tag, `uv sync`, recharger le cache, reprovisionner les outils dont la version change, relancer le diagnostic) ;
  - désinstallation (`install.* --uninstall` ou documentation) et emplacement des données à supprimer.

### H-4 — Pas d'instance unique : le « seul écrivain » ne tient qu'à l'intérieur d'un processus (AD-1, AD-5, AD-14)

- **Problème.** Rien n'empêche un second lancement (double clic, raccourci, fenêtre pywebview plus navigateur) de démarrer un second serveur sur `<data>/` : deux files, deux écrivains de `github.json`, `progress.json`, `run.json`, restaurations concurrentes. Absence aussi de règle sur l'arrêt (fermeture de l'onglet, Ctrl+C du terminal de lancement, sous-processus orphelins, nettoyage des verrous `.git/*.lock`).
- **Correctif.** Verrou d'instance exclusif sur `<data>/app.lock` (`msvcrt.locking` / `fcntl.flock`, ou un module dédié), écrit avec port et PID ; un second lancement ouvre le navigateur sur l'instance existante. Règle d'arrêt : `cli` possède le cycle de vie, arrête proprement la file, tue l'arbre des sous-processus restants, supprime le verrou. Au démarrage : nettoyer les verrous git périmés d'un espace dont aucun processus n'est actif.

### H-5 — Reprise après incident pendant une restauration, et impasse « Recommencer » (AD-6, AD-17)

- **Problème.**
  1. La restauration renomme `repo/` et `origin.git/` vers une corbeille, copie l'instantané, vérifie. Un arrêt du processus entre ces étapes (coupure, Ctrl+C, kill) laisse un espace sans `repo/` ; AD-17 dit que la reprise passe par « l'état sur disque et `run.json` » sans écrire la procédure ni consigner l'état `restoring`/`quiz_altered` de façon durable avant l'opération.
  2. `restore_failed` propose uniquement « Recommencer ». Si l'instantané 0 manque, on rebâtit par setup puis on compare à l'empreinte de référence ; si l'empreinte diffère (version de git, EOL, fichiers de cache), aucune sortie n'est prévue : boucle sans fin.
  3. Les instantanés ne sont jamais purgés (un par choix de quiz).
- **Correctif.** Journal d'intention écrit dans `run.json` avant toute restauration (`restoring{from, trash}`) ; au démarrage, un état `restoring` ou `quiz_altered` déclenche une reprise automatique (terminer la restauration depuis l'instantané, sinon depuis la corbeille). Définir la dernière issue : après échec de comparaison de Recommencer, accepter l'état reconstruit, journaliser l'écart d'empreinte dans le journal des remises à zéro et dans `app.log`, et afficher un `app_error` avec action « Exporter le diagnostic ». Purger les instantanés de quiz une fois la restauration confirmée (garder le 0 et le dernier).

### H-6 — Déterminisme cassé par la conversion CRLF à l'installation et sur les gabarits (AD-3, AD-7, AD-9, AD-18, NFR-3)

- **Problème.** `core.autocrlf=false` n'est posé que pour les dépôts de l'apprenant. L'application elle-même est installée par `git clone` ou zip : avec le réglage par défaut de Git for Windows (`autocrlf=true`), `content/exercise/**`, `content/scenarios/*.yaml`, `hooks` générés et scripts sh sont checkoutés en CRLF. Le setup copie les gabarits tels quels : SHA différents sous Windows (donc empreintes de référence fausses), et un hook `#!/bin/sh` en CRLF échoue (`sh\r`). « Écrivent les fichiers en LF » ne vaut que pour `write_file`.
- **Correctif.** `.gitattributes` dans le dépôt de l'application (`* text=auto eol=lf`, `*.sh text eol=lf`, `*.png binary`) ; installeur qui clone avec `-c core.autocrlf=false` ; l'op de copie de gabarit normalise en LF et écrit en mode binaire ; les hooks sont écrits en `newline="\n"` ; test de CI « aucun CRLF dans `content/` et dans les hooks générés ». Bit exécutable des hooks posé explicitement sous Unix.

### H-7 — Le dépôt d'exercice et les environnements de test sont sous-spécifiés (AD-12, AD-10, AD-9, AD-4)

- **Problème.**
  - Station 1 : `pytest` et `ruff` tapés dans le terminal tournent dans quel environnement ? Les paquets de l'exercice (httpx, la dépendance vulnérable) ne sont pas dans l'environnement de l'application. Un `.venv` dans `repo/` ferait exploser les instantanés (copie par quiz) et l'empreinte.
  - AD-12 : « préchargées dans le cache uv » sans dire où est ce cache (`UV_CACHE_DIR` absent de l'environnement hermétique, donc cache du poste ou jamais atteint), quel interpréteur (`UV_PYTHON_DOWNLOADS=never`, `UV_PYTHON_PREFERENCE=only-managed` manquent : `uv sync --offline` peut chercher un Python), ni si le gabarit d'exercice fournit un `uv.lock` (sans lock, la résolution hors ligne dépend du cache et peut varier).
  - Hardlinks uv impossibles si le cache et `ci/` sont sur des volumes différents (copie lente, NFR-6).
  - Chemins longs sous Windows : `workspaces/<parcours>/<scenario>.<mode>/ci/<pr>-<sha40>/.venv/Lib/site-packages/...` dépasse facilement 260 caractères ; `core.longpaths` n'est pas posé.
  - `pre-commit install` tapé par l'apprenant est refusé par pre-commit lorsque `core.hooksPath` est défini ; la station 1 doit le prévoir.
- **Correctif.** Décider : (a) cache uv unique `<data>/cache/uv` + variables `UV_CACHE_DIR`, `UV_PYTHON_DOWNLOADS=never`, `UV_PYTHON_PREFERENCE=only-managed` ; (b) environnement d'exercice unique par espace dans `cache/venv/`, hors instantanés, référencé par `toolrun` pour les commandes de station ; (c) `uv.lock` obligatoire dans chaque gabarit ; (d) `ci/<pr>-<sha7>` et `core.longpaths=true` ; (e) le pre-commit de la station 1 est fourni par le setup, la commande `pre-commit install` est expliquée ou remplacée par un message.

### H-8 — Spécification insuffisante de l'annulation et de l'arrêt des sous-processus sous Windows/Unix (AD-4, AD-10, AD-6)

- **Problème.** « Ctrl+C termine l'arbre de processus » sans mécanisme : sous Windows il faut un Job Object (ou `CREATE_NEW_PROCESS_GROUP` + `taskkill /T`), sous Unix `start_new_session` + `killpg`. `psutil` n'est pas dans la pile. Pas de délai maximal par commande (test à boucle infinie, git qui attend un verrou), pas de règle sur les verrous `index.lock` laissés après un kill. Même besoin pour l'annulation de run CI (« un nouveau SHA annule le run en cours ») et pour les hooks (git → sh → python → pre-commit → gitleaks).
- **Correctif.** Fixer dans `toolrun`/`gitio` une abstraction unique `spawn(argv, env, cwd, timeout) -> Handle` avec `terminate_tree()` implémentée par plateforme, un délai par défaut dans `Settings`, et une réparation d'espace après kill (supprimer `index.lock` périmé, relancer la projection). Test de confinement qui vérifie l'absence de processus orphelin sur les trois systèmes.

### H-9 — Le contrôle réseau de CI ne couvre pas les sous-processus (AD-13 contrôle 3, NFR-1, NFR-9)

- **Problème.** Le crochet d'audit `socket.connect` ne voit que le processus pytest. git, uv, pip-audit, gitleaks, pytest de l'exercice et les hooks sont des processus enfants : aucune garantie « hors ligne de bout en bout » (NFR-1) ni « aucune télémétrie » (NFR-9) n'est testée sur la chaîne réelle (pip-audit sans `--osv-url` correct irait chez osv.dev ; un outil qui vérifie sa version appelle un serveur).
- **Correctif.** Étape de CI sur Linux qui exécute toute la suite de scénarios dans un espace de noms sans réseau (`unshare -n` ou règle iptables après installation), plus sous Windows/macOS la vérification des variables d'environnement (`UV_OFFLINE`, `PIP_NO_INDEX`, `PRE_COMMIT_...`, drapeaux d'outils : `--no-version-check` etc.). Consigner la liste des appels réseau possibles par outil dans `tools.toml`.

### H-10 — Alias de SHA absents : les ensembles de bonnes réponses ne peuvent pas être écrits dans les YAML (AD-2, AD-7)

- **Problème.** AD-7 place les « ensembles de bonnes réponses » dans le YAML et AD-2 les identifie par `commit:<sha40>`. Un auteur ne connaît le SHA qu'après exécution du setup ; chaque auteur de scénario (agents distincts) inventera sa solution (SHA collés après coup, motifs, requêtes). Idem pour les cibles `diffline` et `ref`.
- **Correctif.** Ajouter à AD-7 un mécanisme d'alias : chaque op de setup peut porter `as: <alias>` ; le contexte `ctx.aliases` résout `commit:@agent-env`, `ref:@feature`, `path:@secret-file` en `element_id`, ceux du YAML sont symboliques, et le validateur de scénarios (en CI) vérifie que chaque alias existe après le setup.

---

## Constats moyens

### M-1 — Diagramme de dépendances incohérent avec les règles

- `progress` n'est importé que par `web`, alors qu'AD-14 le lie à `engine` (enregistrement des faits de premier passage, indices, remises à zéro). Soit l'engine pousse des événements que `progress` consomme (à écrire), soit ajouter la flèche `engine → progress`.
- `github_sim → ci` (AD-8 « demande au ci un nouveau run ») et `ci → github_sim` (lecture des PR, SHA de tête, enregistrement des résultats) sont tous deux nécessaires et absents ; fixer le sens (par exemple `github_sim` émet `pr_updated` / demande via l'engine, `ci` ne connaît pas `github_sim`, l'engine relie les deux).
- `projections → github_sim` (lecture de `github.json`), `scenarios → projections` (les types d'étape reçoivent `RepoState`), `diagnostic → gitio` (sonde git, avec le cas macOS `xcode-select`) et `web → scenarios` (catalogue) manquent. Le « catalogue » est cité dans AD-16 sans module propriétaire : indiquer qui assemble `scénarios + progress + disponibilité diagnostic`.
- `hooks` s'exécute dans un processus séparé mais importe `toolrun → events` : préciser que `events` ne publie rien hors du serveur ; garder l'import de `hooks` léger (latence de chaque `git commit` sous Windows).
- La règle « seuls `gitio` et `toolrun` lancent des sous-processus » est violée en pratique par l'ouverture de l'éditeur externe (FR-3, bouton) et par `webbrowser`/pywebview : l'ajouter à `toolrun` ou en exempter explicitement `cli`/`web`.
- `llmrun → toolrun` mais `toolrun` retire les variables de proxy : l'option « rétablir le proxy de l'apprenant » doit être un paramètre de `toolrun` explicite.

### M-2 — Contexte git : réglages manquants et variables d'environnement oubliées (AD-3)

- Pas de `GIT_OPTIONAL_LOCKS=0` pour les lectures internes : `git status` réécrit l'index, le surveillant voit le changement, ce qui déclenche une opération « changement externe », donc une nouvelle lecture. Il faut aussi dire comment les écritures de l'application sont distinguées des écritures externes (fenêtre de silence pendant l'opération + comparaison d'empreinte de l'arbre, ou surveillance limitée à l'arbre de travail et à `.git/HEAD`, `refs/`, `index`).
- Réglages à figer pour que les versions de git 2.38 à 2.56 se comportent pareil : `pull.rebase=false`, `pull.ff` ou `merge.ff`, `merge.conflictstyle=merge` (le contenu des marqueurs de conflit que l'apprenant édite est validé), `push.default=simple`, `push.autoSetupRemote`, `advice.*=false`, `core.quotepath=false`, `core.abbrev=7`, `core.longpaths=true`, `color.ui=never`, `rerere.enabled=false`, `core.ignorecase`/`core.precomposeunicode` selon l'OS, `fetch.prune`, `rebase.autoStash`, identité par défaut dans `gitconfig` (sinon « Please tell me who you are » en anglais).
- Vérifier que `GIT_CONFIG_COUNT` est bien transmis à `receive-pack` lors d'un push local (git nettoie plusieurs variables de configuration pour les transports locaux) : le comportement de `core.hooksPath` sur `origin.git` doit être testé, pas supposé. Si la valeur forcée atteint `origin.git`, `pre-receive` doit se trouver dans le même dossier que les hooks de `repo/`, ce qui contredit « un dossier par dépôt » (AD-9). Décider : un seul dossier `hooks/` avec des scripts dispatchant sur le dépôt, ou retirer `core.hooksPath` pour `origin.git`.
- `LC_ALL=fr_FR.UTF-8` n'a aucun effet sur glibc si la locale n'est pas générée (le `LANGUAGE` est alors ignoré) : la sonde du diagnostic est correcte, mais prévoir `LC_ALL=C.UTF-8` en repli pour garder la sortie UTF-8.
- `git config` autorisé en écriture pour `user.name`/`user.email` : préciser la portée (`--local`) et interdire `--global`/`--system`/`--file`/`--worktree`.
- Le hook `pre-receive` doit retrouver `github.json` et les réglages : variable d'environnement posée par `gitio` (non listée en AD-3) ou chemin écrit dans le script ; décider.

### M-3 — Concurrence du pipeline, de la file et des restaurations (AD-1, AD-6, AD-10)

- États annoncés `pipeline` et `exporting`, mais le pipeline tourne « hors de la file ». Que se passe-t-il si l'apprenant déclenche un choix de quiz, un Recommencer ou une restauration pendant un run CI ? `git clone --shared` crée des alternates vers `origin.git/objects` : renommer `origin.git` vers la corbeille casse les clones en cours. Règle à poser : toute opération de restauration annule d'abord les runs (arbre de processus tué), les résultats d'un run annulé ou périmé (`(pr, sha)` plus courant ou espace restauré) sont rejetés par un `run_epoch` comparé à l'écriture.
- Modèle de concurrence du serveur non décidé : file `asyncio`, threads ? Un sous-processus bloquant dans la boucle de uvicorn stoppe le SSE. Fixer : file consommée par un thread ou une tâche avec `asyncio.create_subprocess_exec`/`to_thread`, battement SSE (`: ping` toutes les 15 s).
- Surveillant suspendu : sous Windows, un répertoire surveillé ne peut pas être renommé si le descripteur est ouvert. « Suspendu » doit signifier fermé (arrêt de l'observateur), pas filtré.
- Écriture atomique par `os.replace` : sous Windows, échec `PermissionError` si un lecteur (hook, antivirus) a le fichier ouvert ; prévoir la même boucle de reprises que la restauration.

### M-4 — Flux SSE : reprise et bornage (AD-17)

- Après redémarrage du serveur, `seq` repart de zéro : un client avec un `Last-Event-ID` supérieur doit forcer un `GET /api/state` complet. Ajouter un `epoch`/`server_id` dans l'enveloppe ou le premier événement.
- Journal en mémoire sans borne : fixer une taille (par exemple 5 000 événements) et la règle « `Last-Event-ID` hors fenêtre → resynchronisation complète ».
- Plusieurs onglets/fenêtres (navigateur plus pywebview) : le flux est-il par espace ou global ? Préciser l'abonnement (`?workspace=`) et la limite de six connexions HTTP/1.1 par origine.

### M-5 — Contrat d'enregistrement de fichier et d'édition externe absent (AD-1, Deferred « composant d'édition », FR-3)

- L'intention d'enregistrement n'a pas de forme : pas de hash de base (écrasement silencieux d'une modification externe survenue entre-temps), pas de règle de fin de ligne (CRLF d'un éditeur externe contre LF de l'éditeur intégré avec `autocrlf=false` : diff entier), encodage et BOM, fichiers binaires ou volumineux refusés.
- **Correctif.** `save_file{path, content, base_sha256}` → refus 409 si le hash du disque diffère ; conservation des fins de ligne d'origine du fichier ; liste d'extensions éditables ; ce contrat est indépendant du composant d'édition (qui reste différé).

### M-6 — pip-audit : AD-10 et AD-11 se contredisent, le différé ne suffit pas

- AD-10 tire les constats de `pip-audit -f json` et AD-11 le SBOM de `-f cyclonedx-json` « dans le même job » ; pip-audit n'émet qu'un format par exécution. Il y a donc trois exécutions (humaine verbatim, JSON, CycloneDX) avec des codes de sortie distincts, que `pipeline.yaml` (un `argv` + une « commande machine ») ne sait pas décrire. La date et le `serialNumber` du SBOM sont non déterministes.
- Le paragraphe « Invocation exacte de pip-audit » est différé alors que les options (`--osv-url`, `--no-deps`, `--disable-pip`) et la dépendance à un serveur local en cours d'exécution sont déjà des invariants : le différé est acceptable seulement si `pipeline.yaml` admet une liste de commandes par job (`display`, `machine`, `artifacts[]`).
- Le port du serveur doit parvenir à `toolrun` (variable `Settings.osv_url`), y compris pour les commandes tapées dans le terminal (AD-4 autorise pip-audit).
- Les constats de gitleaks, ruff et pytest n'ont pas de « sortie machine » listée en AD-10 (`gitleaks --report-format json`, `ruff --output-format json`, `pytest --junitxml`) ; les ajouter.

### M-7 — Intégrité des téléchargements et compatibilité avec les postes verrouillés (AD-15)

- Seul gitleaks est vérifié par somme de contrôle. Le script d'installation de uv, le PortableGit, pixi et le package conda-forge de git ne sont pas épinglés ni vérifiés ; l'installeur « clone ou zip » ne dit pas quelle référence (tag de release, pas `main`).
- Incohérence : `pixi global install git` place git sous `~/.pixi`, pas dans `<data>/tools/` ; `gitio` doit savoir où chercher (« mode de résolution » dans `tools.toml` : poste, tools, pixi). Dire aussi comment `gitio` résout `git` (le registre ne parle que de `toolrun`).
- Postes d'entreprise : AppLocker/WDAC peut bloquer l'exécution depuis `%LOCALAPPDATA%` ; l'antivirus peut mettre en quarantaine `gitleaks.exe` ou les faux secrets du dépôt d'exercice. Le diagnostic doit tester l'exécution réelle de chaque binaire (pas seulement sa présence) et distinguer « bloqué par la politique du poste ». Les faux secrets ne doivent pas figurer en clair dans le dépôt de l'application (alertes de la protection de push de GitHub, scanners d'entreprise) : les générer au setup à partir d'un motif.
- L'affirmation « MinGit n'a ni bash ni messages traduits » est à vérifier ; MinGit embarque un `sh`. La décision (PortableGit) tient peut-être pour d'autres raisons (locales) : consigner la raison exacte.
- Aucun test de CI ne lance `install.ps1`/`install.sh` sur un runner propre, sans droits administrateur, ni derrière un proxy ; or SM-2 et SM-5 en dépendent. Ajouter une tâche de CI par jalon.

### M-8 — Placement du graphe : règle de stabilité non testable (AD-2)

- « Déterministe et stable d'un état au suivant » sans algorithme : deux stories (projections et vue) divergeront. Fixer les clés : ordre topologique stable par (date de committer, sha), affectation de colonne par chaîne de premiers parents des refs dans un ordre de priorité (`main`, `origin/main`, autres refs triées), colonne conservée tant que le commit existe, et un test propriété (ajouter un commit ne déplace aucun commit existant).
- `element_id` `diffline:<sha|worktree>:<chemin>:<ligne>` est ambigu : un chemin peut contenir `:`, la ligne doit préciser le côté (ancien/nouveau) et la version du fichier. Encoder en pourcentage ou en structure (`diffline:<sha>:<side>:<ligne>:<chemin-encodé>`).
- Performance : une projection complète lance plusieurs processus git ; sous Windows un processus git coûte plusieurs dizaines de millisecondes. Définir un budget (par exemple moins de 800 ms pour un dépôt d'exercice) et privilégier `cat-file --batch` et un seul `for-each-ref`.

### M-9 — Station 4 différée : ce qui est déjà figé suffit presque, mais il manque le schéma

- `github.json` est « prêt pour les stations » (FR-8) mais le schéma des environnements, des approbations de livraison et des tags n'a pas de `schema_version`/règle d'extension (voir H-3). Si la story v0.1 fige le modèle sans cet espace, la station 4 le modifiera sans migration.
- Le refus d'un tag non SemVer (FR-29) n'a pas de lieu : garde de terminal sur `git tag`, ou `pre-receive` sur le push du tag ? Les deux cas existent (tag local puis push) ; choisir (recommandé : garde du terminal, avec test d'état, et `pre-receive` en défense).
- Le service de staging/prod simulée passera par le serveur unique : annoncer dès maintenant que ces routes vivent sous `/serve/<env>/` et sont soumises aux contrôles de H-1.

### M-10 — Mesure des indices et disponibilité calculée côté front (AD-2, FR-13, AD-14)

- AD-2 interdit au front de calculer la disponibilité, mais FR-13 impose « quelques secondes passées sur le palier » et un « temps de lecture avant l'action suivante » : le chronomètre est local au front selon AD-2 (« tenir un chronomètre local »), la disponibilité est serveur. Décider : le serveur horodate l'ouverture du palier et calcule la disponibilité du palier suivant (`hint_available_at`), le front rapporte seulement la visibilité (`hint_read{duration_ms}`) comme fait enregistré par `progress`. Sinon deux stories (indices et suivi) divergeront.
- FR-13 n'apparaît pas dans la table capability → architecture sous un AD précis.

### M-11 — Opérations, journalisation et support (convention « Journalisation »)

- `app.log` est décidé (rotation) mais sans taille, niveau, contenu minimal (op_id, workspace_id, argv des sous-processus, codes de sortie, durées), ni redaction. Les traces Python n'apparaissent qu'au journal (NFR-7) : le dire.
- Pas d'export de diagnostic (journal + `tools.toml` + versions + sonde + empreintes) que l'apprenant peut joindre à une demande d'aide, utile à SM-2/SM-5 et à l'issue de H-5.
- Pas de réglage documenté pour le niveau de journal ni pour conserver les sorties d'outils d'un run CI en échec (`ci/` est jetable : durée de conservation ?).

### M-12 — Armes de test du contenu : vérifications automatiques absentes (AD-7, AD-18)

- La CI vérifie les empreintes de référence mais pas : la validité du schéma YAML des scénarios, l'existence des alias (H-10), la présence de tous les `job_id` dans les trois fichiers de CI (AD-10 le prévoit), la couverture explication par type d'élément (NFR-13), les liens glossaire → barrière → éléments (FR-33), le fait qu'un scénario qui déclare un outil requis existe dans `tools.toml`. Une tâche « lint du contenu » dans AD-18 évite des régressions silencieuses par des agents travaillant en parallèle.
- La matrice `*-latest` n'est pas épinglée (changement d'architecture macOS, version de git préinstallée) : épingler les images et fixer la version de git testée, plus une exécution avec le git minimal (2.38) et un git récent.

---

## Constats faibles

- **L-1.** `workspaces/<parcours>/<scenario>.<mode>/` : le mode est déjà dans l'identifiant du scénario (« un YAML par scénario et par mode ») ; simplifier.
- **L-2.** Systèmes de fichiers insensibles à la casse (Windows, macOS) : `element_id` `path:` et branches `Feature`/`feature` ; poser `core.ignorecase` par détection et interdire dans les scénarios deux chemins qui ne diffèrent que par la casse.
- **L-3.** `rm`/`mv`/`cp` avec jokers : interdire explicitement la racine du bac à sable et `.git`, refuser `rm -r .`, ne pas suivre les liens symboliques ni les jonctions Windows.
- **L-4.** Ordre `stdout`/`stderr` sans PTY : l'interleaving n'est pas garanti ; indiquer que l'affichage ordonné par horodatage de lecture est suffisant, et que les outils reçoivent `NO_COLOR`/`TERM=dumb`.
- **L-5.** Ports : `cli` choisit « un port libre » ; préférer lier le port 0 dans uvicorn et lire le port réel (course entre libération et liaison).
- **L-6.** Le code d'exercice du parcours LLM appelle `httpx` : l'exception à l'analyse statique d'AD-13 vise `src/`, pas `content/exercise/` ; dire que ce dossier est contrôlé par le test de la liste d'endpoints autorisés (FR-28) et exclu du contrôle (1).
- **L-7.** Carte de la chaîne (FR-32) et vocabulaire (FR-33) : la définition des stations, de la frontière CI/CD et des liens terme → barrière → `element_id` n'a pas de fichier de contenu déclaré (`stations.yaml`) ; `glossary.yaml` est listé, pas `stations`.
- **L-8.** `op` `agent_push_force` en setup doit contourner `pre-receive` (écriture directe par `update-ref` ou hook désactivé) : le dire, sinon la protection posée avant le setup bloque le scénario B.
- **L-9.** Entretien RSSI (FR-34) : il désigne des preuves (`check:`, `tag:`, `review:`) qui n'existent qu'après les stations 2 à 4 ; le setup du scénario doit pouvoir fabriquer ces états (ops `set_check_result`, `record_approval`, `create_tag`) sans dépendre des scénarios précédents (FR-9). Les ajouter au registre d'ops.
- **L-10.** Dépendance de pywebview : sous Linux elle demande GTK/Qt (sans droits administrateur, probablement indisponible) ; documenter que le repli ne vaut que pour Windows/macOS.

---

## Ce qui est bien tenu (à conserver)

- Un écrivain par espace, séquence fixe sortie → projection → validation → explication, états explicites du moteur.
- Séparation des contextes git apprenant/interne, sorties jamais analysées, plumbing stable (`-z`, porcelain v2).
- `GIT_CONFIG_COUNT` / `GIT_CONFIG_*` : le niveau « command » prime bien sur la configuration du dépôt ; `GIT_CONFIG_GLOBAL` est disponible depuis git 2.32, antérieur à la version minimale 2.38.
- `git merge-tree --write-tree` (≥ 2.38), `commit-tree`, `update-ref` avec ancienne valeur : méthode correcte pour un merge sans arbre de travail, avec code de sortie 1 en cas de conflit à gérer comme verdict.
- Hooks en `#!/bin/sh` à une ligne : fonctionne avec le sh embarqué de Git for Windows (sous réserve de H-6).
- Empreinte canonique plutôt que « octet pour octet » littéral ; restauration avec reprises sous verrou Windows.
- Registre d'outils unique (`tools.toml`) pour installeur, diagnostic, disponibilité des scénarios.
- Analyse statique des imports réseau, recherche d'URL dans `static/`, polices et bibliothèques vendorisées.
- La plupart des items du Deferred sont réellement sans invariant entre unités (mode formateur, anglais, GitHub réel, hébergement) ou bornés par des contraintes déjà posées.

## Ordre de traitement conseillé avant le découpage en stories

1. C-1, H-1, H-2 (modifications de règles existantes : AD-3, AD-4, nouvel AD « Surface HTTP »).
2. H-3, H-4, H-5 (nouvel AD « Cycle de vie : version, instance, reprise »).
3. H-6, H-7, H-10, M-2 (correctifs d'AD-3, AD-7, AD-12 et `.gitattributes`).
4. M-1 (corriger le diagramme) puis M-3, M-4, M-5, M-6.
5. Le reste peut être traité dans les stories correspondantes si la story porte la règle.
