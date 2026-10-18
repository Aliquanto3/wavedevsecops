---
name: 'Revue adversariale — ARCHITECTURE-SPINE WaveDevSecOps'
type: architecture-review
lens: adversary
target: ../ARCHITECTURE-SPINE.md
date: '2026-10-18'
---

# Revue adversariale du spine

**Méthode.** Pour chaque trou : deux unités du niveau inférieur (épopées ou stories écrites séparément par deux agents) qui respectent chaque AD à la lettre mais produisent des modules incompatibles. Puis la règle d'AD, nouvelle ou resserrée, qui ferme le trou. Gravité : critique (état corrompu ou résultat faux visible de l'apprenant, contenu pédagogique faux), haute (incompatibilité à l'intégration ou défaut systématique), moyenne (défaut localisé), basse.

**Verdict.** Le paradigme (un écrivain, projections) est sain, mais la file d'opérations ne couvre ni le pipeline, ni les restaurations, ni les processus multiples, et les formes de données partagées (RepoState, github.json, vues, réponses de scénario) n'ont ni propriétaire de schéma ni version : les stories divergeront à l'intégration.

## Synthèse

| # | Trou | Gravité |
|---|---|---|
| T1 | Pipeline × restauration / Recommencer : résultats périmés, clones partagés, état unique | Critique |
| T2 | Checks non liés au SHA : merge autorisé sur les résultats d'un ancien SHA | Critique |
| T3 | Deux instances de l'application sur le même dossier de données | Critique |
| T4 | Interruption pendant une restauration ; `hooks/` et `run.json` hors instantané | Haute |
| T5 | Point OSV : appel bloquant dans la boucle d'événements, port inconnu des outils | Haute |
| T6 | Aucun propriétaire de schéma pour RepoState, vues, github.json ; `events` ne peut pas typer `views` | Haute |
| T7 | Réponses de scénario en `element_id` littéraux (SHA) | Haute |
| T8 | `element_id` ambigus (diffline, path, sbom, output) | Haute |
| T9 | Surveillant de fichiers : événements auto-déclenchés, reprise après restauration | Haute |
| T10 | Plusieurs espaces, un moteur : flux, `seq`, `progress.json`, surveillants | Haute |
| T11 | Hooks : `core.hooksPath` unique, `pre-commit install`, push de setup contre `pre-receive`, événements dans le processus du hook | Haute |
| T12 | Empreinte non déterministe : `github.json`, chemins absolus, caches d'outils dans `repo/` | Haute |
| T13 | Serveur local sans jeton : une page web envoie des intentions | Haute |
| T14 | Flèches de dépendance contredites par AD-8 et AD-10 | Moyenne |
| T15 | Garde du terminal : liste noire d'options dans une liste blanche de sous-commandes | Moyenne |
| T16 | Deux fichiers d'avancement (`run.json`, `progress.json`), `step_id` non gouvernés | Moyenne |
| T17 | Clé d'un run CI : base absente, état `cancelled` absent, concurrence | Moyenne |
| T18 | Écritures de fichiers utilisateur : fin de ligne, encodage | Moyenne |
| T19 | Reprise SSE après redémarrage du processus | Moyenne |
| T20 | Arguments des ops de setup et références croisées non validés | Moyenne |
| T21 | Divers (versions en triple, balises CI, rétention, état `exporting`, llmrun) | Basse |

---

## T1 — Pipeline × restauration / Recommencer (critique)

**La paire.** Story A (épopée moteur) implémente `restoring` selon AD-6 : surveillant suspendu, renommage des dossiers, copie, empreinte. Story B (épopée CI) implémente AD-10 : le run est « hors de la file », dure plusieurs dizaines de secondes, clone `origin.git` en `--shared` dans `ci/<pr>-<sha>/` et, à la fin, soumet l'écriture à la file.

Chacune est conforme. Aucun AD ne dit :
- que la restauration annule les runs en cours (`ci/` est « hors instantanés ») ;
- qu'un résultat arrivé après la restauration est écarté : il s'écrit dans le `github.json` restauré, avec un `(pr, sha)` qui peut exister dans l'ancienne et la nouvelle histoire (même SHA de setup) ; un check « success » apparaît dans un état où l'apprenant n'a rien lancé ;
- que les clones `--shared` (alternates vers `origin.git/objects`) sont supprimés : `origin.git` part à la corbeille, les clones pointent dans le vide ;
- comment `engine_state` (une seule valeur) représente à la fois « commande en cours » et « pipeline en cours ». AD-10 veut qu'un push pendant un run l'annule ; si `pipeline` est un état exclusif qui désactive les commandes, l'apprenant ne peut pas pousser.

L'op « résultat de check » n'est pas dans la liste d'AD-1 (qui cite seulement « relance d'un check »).

**Règle de fermeture (AD-1 et AD-10).**
- `engine_state` décrit le mode exclusif (`idle|command|quiz_altered|restoring|setup`). Les runs de pipeline sont un champ orthogonal `pipeline_runs[]` du même événement.
- Chaque espace porte un `epoch` entier, incrémenté par toute restauration, Recommencer ou reconstruction. Tout run et toute op issue d'un producteur extérieur à la file (ci, surveillant) porte l'`epoch` de son lancement ; la file écarte sans effet toute op d'`epoch` périmé.
- Entrer dans `restoring` ou `setup` : annuler (arbre de processus) tous les runs et supprimer `ci/` avant la copie.
- Ajouter à la liste des opérations d'AD-1 : `check_started`, `check_result`, `check_cancelled`.

## T2 — Checks non liés au SHA (critique)

**La paire.** Story A (github_sim) calcule le droit de merge d'AD-8 : « tous les checks obligatoires sont `success` ». Story B (ci) écrit les checks d'une PR sous `(pr, job_id)` (le modèle de PR porte une liste de checks par PR ; l'`element_id` est `check:<pr>:<job_id>`). L'apprenant pousse un nouveau commit : A met à jour le SHA de tête ; B annule l'ancien run et démarre le nouveau. Entre les deux, et pour chaque job non encore terminé, les `success` de l'ancien SHA restent en place : le merge est autorisé sur du code que personne n'a vérifié. Un scénario sur la fiabilité de la quality gate enseigne alors faux, et le défaut est visible.

**Règle de fermeture (AD-8).**
- Un check porte `head_sha` et `base_sha`. `github_sim`, dans la même écriture atomique qui change le SHA de tête (ou la base), remet tous les checks de la PR à `queued` avec le nouveau couple.
- `mergeable` exige, pour chaque check obligatoire, `check.head_sha == pr.head_sha`, `check.base_sha == pr.base_sha` et `state == success`. La raison de blocage dit « résultats d'un ancien commit ».
- État `cancelled` ajouté à l'énumération : jamais compté comme succès.

## T3 — Deux instances sur le même dossier de données (critique)

**La paire.** Story A (`cli`) choisit « un port libre » et démarre. L'apprenant double-clique deux fois, ou lance le raccourci puis `--window`. Chaque processus a sa file « unique » (AD-1) : deux écrivains sur `repo/`, `github.json`, `progress.json`, `snapshots/`. Tout est conforme à l'intérieur de chaque processus ; AD-1 dit « par espace de travail » mais n'impose rien au niveau du processus.

**Règle de fermeture (AD-1 et AD-5).** Au démarrage, `cli` prend un verrou exclusif `<data>/app.lock` (PID, port, jeton). Si le verrou est tenu, la seconde instance n'écrit rien, ouvre le navigateur sur l'URL de la première et sort. Un verrou orphelin (PID mort) est repris. `engine` refuse de s'initialiser sans ce verrou.

## T4 — Interruption pendant une restauration, état hors instantané (haute)

**La paire.** Story A (moteur) : « tout écart ou toute exception passe en échec », état d'origine dans la corbeille. Story B (reprise, question UX 9 « Reprendre », AD-5 « reprend son espace s'il existe ») : au lancement, rouvre l'espace. Si le processus meurt (coupure, fenêtre fermée) entre le renommage et la copie, `repo/` manque ou est partiel ; `run.json` dit « étape 4, idle » et rien ne le détecte.

Trois états vivent hors instantané, donc ni restaurés ni empreints :
- `hooks/` (« posé au setup puis lecture seule », mais la station 1 peut activer le hook) : restaurer un état d'avant l'activation laisse le hook actif ;
- `run.json` (étape courante, état du quiz) : restaurer l'instantané « avant quiz » sans remettre l'étape à sa place ;
- la table d'alias de setup (voir T7).

**Règle de fermeture (AD-6).**
- La restauration est journalisée : `run.json` reçoit `restoring{snapshot_id, epoch, phase}` avant le premier renommage, effacé après vérification d'empreinte. Au démarrage, un `restoring` résiduel reprend la copie ou bascule en `restore_failed` + « Recommencer ».
- `hooks/` et `run.json` (hors champs d'horodatage) font partie de l'instantané et de l'empreinte. Les hooks activés par une étape sont un état déclaré (`hooks_enabled` dans `run.json`), pas une pose faite au vol.
- Au démarrage, `engine` recalcule l'empreinte de l'espace repris et la compare ; un écart ouvre `external_change` ou `restore_failed`, jamais silencieux.
- Rétention : au plus N instantanés par espace (`Settings`), le 0 et le dernier toujours conservés.

## T5 — Point OSV : boucle d'événements et port (haute)

**La paire.** Story A (toolrun) lance les outils avec `subprocess.run` synchrone, ou attend le processus dans le fil de la boucle FastAPI (sortie « verbatim », ordre strict d'AD-1). Story B (osv) sert `POST /osv/v1/query` dans le même processus uvicorn (Structural Seed : un processus). pip-audit appelle ce point pendant que la boucle attend pip-audit : interblocage jusqu'au délai d'expiration, check `error`. Les deux stories respectent AD-11 et AD-12.

Second défaut : le port est choisi au lancement (NFR-12), alors que `pipeline.yaml` (statique, AD-10) porte `http://127.0.0.1:<port>/…` sans mécanisme de substitution ; si la sortie verbatim contient l'URL (erreur de connexion), elle change à chaque lancement et casse les explications et empreintes (T12).

**Règle de fermeture (AD-11 et AD-12).**
- `toolrun` n'attend jamais dans le fil de la boucle : `asyncio.create_subprocess_exec` ou fil dédié. Test d'intégration obligatoire : pip-audit s'exécute pendant qu'un flux SSE est servi.
- Le point `osv` est en lecture seule, sans verrou, sans passage par la file, sans jeton (T13), et ne dépend que de `config`.
- `cli` lie le socket avant de figer `Settings` ; `Settings.osv_url` est la seule source ; `pipeline.yaml` utilise le jeton `{osv_url}` résolu par `ci`.
- La normalisation de la sortie (URL OSV remplacée par une valeur fixe, chemins absolus, T12) est la seule transformation permise de la sortie verbatim, déclarée dans `pipeline.yaml`.

## T6 — Schémas partagés sans propriétaire (haute)

**La paire.** Story A (projections) définit `RepoState` comme elle le juge utile pour les vues. Story B (scenarios/steps, `check(state: RepoState, ctx)`) écrit des types d'étape qui lisent `state.refs`, `state.reflog`, `state.pr[n].checks`. Story C (github_sim) définit la forme de `github.json` ; `projections` et `hooks` le lisent sans flèche vers `github_sim` et réécrivent chacun un analyseur. Story D (events) doit typer `state_projected{views}` mais `events` « n'importe rien du projet » : elle ne peut pas importer le modèle de vues, tape `views: dict`, et le front lit à l'aveugle.

**Règle de fermeture (nouvel AD « Contrats de données »).**
- Un module feuille `contracts/` (n'importe rien du projet, importable par tous, `events` compris) porte les modèles pydantic partagés : `RepoState`, `Views`, `GithubState`, `RunState`, `ProgressFacts`, `ScenarioDoc`, avec `schema_version`. Un propriétaire écrivant par modèle ; les lecteurs importent le modèle et ne réimplémentent pas l'analyse.
- Évolution additive ; tout champ supprimé ou renommé incrémente `schema_version` et ajoute une migration. Test de contrat : un exemple sérialisé par modèle, versionné, relu par chaque lecteur.
- Un seul lecteur d'état git, `gitio.read_state()`, alimente `projections` et l'empreinte d'AD-6 (deux lectures des mêmes refs, reflog et index divergeront sinon).

## T7 — Réponses de scénario en SHA littéraux (haute)

**La paire.** Story A (scénario du parcours A) déclare les bonnes réponses d'un quiz ou d'une désignation en `element_id`, donc `commit:<sha40>` (AD-2, AD-7) ; les SHA du setup sont déterministes (AD-3), l'auteur les copie d'une exécution. Story B modifie le gabarit d'exercice partagé (FR-16) ou un op de setup : tous les SHA changent, toutes les réponses sont fausses, l'empreinte de référence aussi. Pire : les commits de l'apprenant ont des SHA inconnus du YAML (dates réelles) et ne peuvent pas figurer dans « l'ensemble de bonnes réponses ».

**Règle de fermeture (AD-7).**
- Les ops de setup portent `as: <alias>` ; les réponses et gardes du YAML désignent `commit:@alias`, `ref:<nom complet>` ou un sélecteur (`commit:tip(<ref>)`, `commit:msg(<texte>)`) ; le serveur résout contre la table d'alias de `run.json`. Aucun SHA littéral dans `content/scenarios/`, vérifié par le lint de contenu (T20).
- Les `element_id` n'existent que dans les payloads ; les alias sont la seule interface de l'auteur.

## T8 — `element_id` ambigus (haute)

**La paire.** Story A (vue diff) émet `diffline:<sha|worktree>:<chemin>:<ligne>`. Story B (vue index / arbre) émet `path:<chemin>`. Conformes, mais :
- `diffline` ne dit pas de quel côté est `<ligne>` (ancien ou nouveau) ni ce qui arrive en cas de renommage ; un chemin posix valide peut contenir `:` : l'analyse est ambiguë ;
- `path:<chemin>` désigne à la fois HEAD, l'index et l'arbre de travail : la vue « préparé / non préparé » affiche deux éléments pour un identifiant, la correspondance FR-5 saute de l'un à l'autre ;
- `sbom:<paquet>` n'a pas de version : avant et après correction (station 3) donnent le même identifiant ;
- `output:<op_seq>` : `op_seq` n'est défini nulle part (il y a `seq` et `op_id`) ;
- `check:<pr>:<job_id>` ne distingue pas le SHA (T2) ; `review:<pr>:<n>` : `n` de quel compteur ?

**Règle de fermeture (AD-2).**
- Grammaire formelle unique des `element_id` (segments encodés en pourcentage, `:` jamais brut dans un segment), générateur et analyseur uniques dans `contracts/`.
- Forme précisée : `path:<zone>:<chemin>` avec `zone` dans `head|index|worktree` ; `diffline:<sha|index|worktree>:<chemin>:<old|new>:<ligne>` ; `sbom:<paquet>@<version>` ; `output:<op_id>` ; `check:<pr>:<job_id>@<head_sha7>`.
- Chaque vue déclare dans le registre des volets les types d'`element_id` qu'elle émet ; un test refuse un identifiant émis non déclaré.

## T9 — Surveillant de fichiers (haute)

**La paire.** Story A (moteur) : le surveillant pousse « changement externe » pour tout événement sous `repo/`. Story B (terminal) : `touch`, `echo >`, `git checkout` modifient `repo/`. Chaque commande de l'apprenant produit un « changement externe » fantôme après l'anti-rebond, donc après la fin de l'op : second passage de validation et seconde `step_explanation`. AD-1 ne le suspend que pendant `setup` et `restoring`. À la reprise après restauration, les événements bufferisés par l'OS pour la copie arrivent et déclenchent un faux changement externe. Sous Windows, `.git/` produit un flot d'événements (`index.lock`).

**Règle de fermeture (AD-1).**
- Le surveillant exclut `.git/` et ne regarde que l'arbre de travail. Il est aussi suspendu pendant `command`. Une op « changement externe » n'est créée que si l'empreinte de l'arbre diffère de celle de la dernière projection ; sinon rien n'est émis et ni validation ni explication ne repassent.
- La reprise après restauration attend un délai de silence, vide le tampon et réinitialise la référence d'empreinte.
- L'enregistrement de l'éditeur (FR-3) est refusé en `quiz_altered`, comme les écritures du terminal (AD-4 ne couvre que le terminal).

## T10 — Plusieurs espaces, un moteur (haute)

**La paire.** Story A (web) : `GET /api/state` et le flux SSE sans paramètre d'espace (AD-17 n'en dit rien). Story B (front) : le catalogue ouvre un second scénario dans un autre onglet. Les événements des deux espaces se mélangent ; le magasin de projection unique du front (conventions) écrase l'un par l'autre. Autres collisions :
- `seq` est global sur la vie du processus alors que `engine_state` est par espace : la désactivation des commandes de l'onglet B dépend de A ;
- `progress.json` est écrit par des ops de plusieurs files : deux lectures-modifications-écritures concurrentes, la seconde perd la première (l'écriture atomique ne l'empêche pas) ;
- un surveillant par espace actif, ou par espace existant (coût) : non dit ;
- `GIT_CONFIG_GLOBAL` unique fuit entre espaces (T15) ;
- le même scénario ouvert dans deux onglets : deux fronts, un espace, les 409 « moteur occupé » vécus comme un bug.

**Règle de fermeture (AD-1, AD-5, AD-17).**
- Toutes les routes sont sous `/api/ws/<workspace_id>/…` ; un flux SSE par espace ; le front tient un magasin par espace ; `seq` est par espace (plus `boot_id`, T19).
- `progress` sérialise toutes ses écritures par un verrou unique en processus, relit le fichier sous verrou et applique des ajouts (jamais l'écriture d'un instantané en mémoire).
- Au plus K espaces actifs (file, surveillant, runs) ; les autres sont dormants et rouverts à la demande. K dans `Settings`.
- Un espace n'est ouvert que par un onglet à la fois ; le second reçoit « déjà ouvert » avec un lien.

## T11 — Hooks (haute)

**La paire.** Story A (gitio) applique AD-3 : `core.hooksPath=<hooks de l'espace>` par `GIT_CONFIG_COUNT` pour tous les appels git, y compris sur `origin.git`. Story B (github_sim, hooks) applique AD-9 : « origin.git reçoit son propre `pre-receive` ... un dossier par dépôt ». L'environnement n'impose qu'un chemin : les deux dépôts partagent le dossier, le `pre-commit` de `repo/` est cherché dans `origin.git` et un `pre-receive` figure dans le dossier du dépôt de travail. Contradiction résolue différemment par deux agents.

Autres paires :
- Story station 1 (scénario) enseigne `pre-commit install` (outil autorisé par AD-4) ; AD-9 pose le hook à la préparation ; pre-commit refuse d'installer quand `core.hooksPath` est posé. L'étape pédagogique centrale ne peut pas se dérouler.
- Un op de setup `push` vers une branche déjà protégée par `set_protection` est refusé par le `pre-receive` : l'ordre des ops décide du succès, sans règle.
- `hooks` appelle `toolrun` et `gitio` qui émettent des événements dans le processus du hook (autre mémoire, autre `seq`) : événements perdus ou, si un agent ajoute un envoi au serveur, violation de « ne parle jamais au serveur ».
- `hooks` lit `github.json` pendant que `github_sim` le remplace : sous Windows, `os.replace` échoue (`PermissionError`) si un lecteur le tient ouvert. Les hooks tournent à l'intérieur d'un `push` de la file, mais rien n'interdit d'autres lecteurs externes (outil de l'apprenant, éditeur).

**Règle de fermeture (AD-3 et AD-9).**
- `gitio.env(kind)` fixe `core.hooksPath` selon le dépôt cible : `hooks/work/` et `hooks/origin/`, deux dossiers distincts.
- `pre-commit install` est intercepté par `terminal` et mappé sur une op applicative `install_hook` qui pose le script d'AD-9 (résultat identique pour l'apprenant, un seul mécanisme). `hooks/` est donc écrit par `scenarios` et cette op seulement, et inclus dans l'instantané (T4).
- Les ops de setup s'exécutent avec `WDS_SETUP=1` (posé par `gitio` seul, lu via `Settings`) : le `pre-receive` laisse passer.
- Dans un processus de hook, `events` est branché sur un puits nul ; la sortie visible passe par stderr.
- Les lectures de `github.json` hors processus serveur rejouent 3 essais sur `PermissionError`.

## T12 — Empreinte non déterministe (haute)

**La paire.** Story A (moteur) : l'empreinte inclut `github.json` « sérialisé de façon canonique » (AD-6). Story B (ci) : les checks stockent la sortie verbatim, des durées, l'URL OSV, des chemins absolus (`C:\Users\…\ci\3-ab12\`), des horodatages. Conséquences : (1) la comparaison Recommencer / référence d'AD-18 diffère selon la machine dès qu'un run a eu lieu ; (2) un setup qui ouvre une PR avec des checks déclarés puis lance le CI donne une empreinte variable ; (3) `.pytest_cache`, `.ruff_cache`, `.coverage`, `.pre-commit...` écrits depuis le terminal dans `repo/` modifient l'arbre de travail, donc l'empreinte, `git status` et les vues.

**Règle de fermeture (AD-6, AD-10, AD-12).**
- L'empreinte de `github.json` exclut `checks[].output`, `duration_ms` et `ts` ; elle garde état, `head_sha`, `base_sha`, `job_id` et constats structurés normalisés.
- L'empreinte de référence est prise avant tout run ; le setup ne lance jamais `ci`.
- `toolrun` redirige caches et fichiers d'outils hors de l'arbre (`RUFF_CACHE_DIR`, `PYTEST_ADDOPTS=-p no:cacheprovider`, `COVERAGE_FILE`, `PRE_COMMIT_HOME` dans `cache/`) ; le gabarit d'exercice contient un `.gitignore` couvrant le reste et l'empreinte exclut les fichiers ignorés.
- La sortie stockée normalise les chemins absolus de l'espace en `<repo>` (T5).

## T13 — Serveur local sans jeton (haute)

**La paire.** Story A (web) expose les intentions en `POST` JSON sur `127.0.0.1:<port>` (AD-17), sans authentification et sans contrôle d'`Origin` ou de `Host`. Story B (llmrun) ajoute `run_exercise_code` : « après confirmation » est une confirmation du front, pas du serveur. N'importe quelle page ouverte dans le même navigateur (ou une réassociation DNS) peut envoyer des `POST` et lancer du code Python de l'espace avec accès réseau, ou effacer des fichiers du bac à sable. Chaque story respecte les AD.

**Règle de fermeture (AD-13 et AD-17).**
- Jeton aléatoire par lancement (dans l'URL ouverte par `cli`, ensuite en cookie `HttpOnly; SameSite=Strict`), exigé sur toute route sauf `/osv/v1/query` (lecture seule, appelée par pip-audit). `Host` accepté seulement `127.0.0.1:<port>` ou `localhost:<port>` ; `Origin` vérifié sur tout `POST` ; `Content-Type: application/json` obligatoire.
- `run_exercise_code` exige un `confirm_nonce` émis par le serveur lors d'un premier appel ; l'état de la confirmation est côté serveur.

## T14 — Flèches de dépendance contredites (moyenne)

**La paire.** Story A (github_sim) applique la fin d'AD-8 : « demande au `ci` un nouveau run » ; or le diagramme n'a pas de flèche `github_sim → ci`, et `ci` ne peut pas rappeler la file du moteur (« les flèches ne remontent jamais ») pour déposer ses résultats (AD-10). Un agent ajoute un import de `ci` dans `github_sim`, un autre un rappel vers `engine` dans `ci` : cycles. De même `projections` et `hooks` lisent `github.json` sans flèche vers `github_sim`.

**Règle de fermeture (Règles de dépendance).**
- Les demandes entre modules sont des intentions retournées au moteur, jamais des appels : `github_sim` retourne `[RequestCheckRun(pr, head, base)]` dans le résultat de son op ; `engine` les transmet à `ci`. `ci` reçoit en paramètre un port `submit(op)` injecté par `engine` pour poster `check_result`.
- Ajouter `projections → github_sim.reader` et `hooks → github_sim.reader` (lecture seule, sans autre dépendance).
- Un test d'architecture (`import-linter`) lit les dépendances autorisées et échoue sur toute autre.

## T15 — Garde du terminal : liste noire dans la liste blanche (moyenne)

**La paire.** Story A (terminal) filtre : sous-commandes autorisées, options globales refusées, quelques options refusées. Story B (scénario de quiz) propose `git diff --output=../x`, `git commit -F /chemin`, `git tag -F`, `git diff --no-index`, `git blame --contents`, `git stash push --pathspec-from-file=`, `git config --global user.name`. Aucune n'est dans la liste noire ; chacune lit ou écrit hors du bac à sable, ou hors de l'espace (`--global` écrit dans `GIT_CONFIG_GLOBAL`, partagé par tous les espaces, T10).

**Règle de fermeture (AD-4).**
- La liste blanche est par sous-commande et par option (drapeaux acceptés avec arité) ; ce qui n'y figure pas est refusé. Toute valeur qui est un chemin de fichier (`-F`, `--output`, `--contents`, `--pathspec-from-file`) passe par le résolveur du bac à sable ou est refusée. `config` n'écrit qu'en portée locale et refuse `--global`, `--system`, `--file`.
- Sous Windows, le résolveur refuse noms réservés (`CON`, `NUL`...), flux de données alternatifs (`:`), noms courts 8.3, points et espaces terminaux.

## T16 — Deux fichiers d'avancement (moyenne)

**La paire.** Story A (moteur) écrit « étape courante, état du quiz » dans `run.json`. Story B (progress) enregistre « étapes validées, scénarios terminés » dans `progress.json`. Un arrêt entre les deux écritures donne une étape validée pour le suivi mais pas pour le moteur (ou l'inverse), sans arbitre. Les faits du premier passage (AD-14) sont indexés par identifiant d'étape, mais rien ne gouverne la stabilité de `step_id` : renommer une étape dans le YAML orpheline le fait ; ouvrir un espace existant avec un YAML mis à jour casse le pointeur d'étape. L'ordre « Recommencer échoué puis remise à zéro consignée » est indéfini.

**Règle de fermeture (AD-5 et AD-14).**
- Le moteur écrit d'abord `run.json`, puis soumet les faits à `progress` avec une clé d'idempotence `(workspace_id, epoch, op_id)` ; au démarrage, il rejoue les faits manquants. `progress` ignore un doublon.
- `step_id` est obligatoire, stable et unique par scénario ; renommer ou supprimer un `step_id` publié exige une table `renamed_from`. `run.json` mémorise le `content_hash` du scénario ; en cas d'écart incompatible, l'espace est proposé à Recommencer.
- Une remise à zéro n'est consignée qu'après succès de la restauration.

## T17 — Clé d'un run CI (moyenne)

**La paire.** Story A (ci) : un run porte sur `(pr, sha_tête)` et `quality_gate` fait `diff-cover` contre « la base de la PR ». Story B (github_sim) : le merge d'une autre PR déplace la base. Le résultat de la PR restante dépend d'une base qui n'est plus celle du run, et rien ne relance le run puisque seules les PR « touchées » (tête modifiée) sont relancées. Le nombre de runs simultanés est libre : deux `uv sync --offline` et des écritures de `cache/` en parallèle.

**Règle de fermeture (AD-8 et AD-10).**
- Clé de run : `(pr, head_sha, base_sha)`. Un changement de base invalide les checks (T2) et relance un run.
- Un seul run actif par espace (file FIFO de runs), les autres en `queued`.
- Après tout changement de refs de `origin`, recalcul de `mergeable` pour toutes les PR ouvertes.

## T18 — Écritures de fichiers utilisateur (moyenne)

**La paire.** Story A (terminal) : `echo`, `touch`, redirections en Python. Story B (éditeur web, FR-3) : enregistrement. AD-3 ne fixe LF que pour le setup. Sous Windows, l'ouverture en mode texte donne CRLF, et l'éditeur du navigateur peut envoyer `\r\n` ; avec `core.autocrlf=false`, les CRLF entrent dans l'index. Le `git diff` du quiz montre `^M`, les SHA et résultats divergent d'un système à l'autre.

**Règle de fermeture (AD-3 et conventions).** Toute écriture d'un fichier de l'espace par l'application : UTF-8 sans BOM, LF, `newline="\n"` ; l'enregistrement de l'éditeur normalise `\r\n` en `\n` ; un seul module `workspace_fs` porte ces écritures (terminal et web l'utilisent).

## T19 — Reprise SSE après redémarrage (moyenne)

**La paire.** AD-17 : `seq` croît sur la vie du processus, journal en mémoire, reprise par `Last-Event-ID`. Après un redémarrage de l'application, un onglet resté ouvert se reconnecte avec `Last-Event-ID: 4812` alors que le nouveau processus est à `seq` 3 : le serveur ne renvoie rien (le front garde une projection périmée) ou attend 4812. Le journal en mémoire est de plus non borné.

**Règle de fermeture (AD-17).** L'enveloppe porte `boot_id` ; `Last-Event-ID` vaut `<boot_id>:<seq>` ; si `boot_id` diffère ou si `seq` n'est plus dans le tampon (tampon circulaire de N événements, `Settings`), le serveur émet `resync_required` et le front refait `GET /api/ws/<id>/state`.

## T20 — Arguments des ops et références croisées (moyenne)

**La paire.** Story A (ops de setup) écrit `colleague_commit(files, message, author_alias)` ; story B (scénario) écrit `colleague_commit: {path: ..., msg: ...}`. AD-7 parle d'un « registre de fonctions nommées » sans modèle pydantic d'arguments par op. Même problème pour les références vers `tool` (AD-16), `job_id` (AD-10), types d'étape, types d'élément de `explanations.yaml`, `barrier:<id>`. Une faute de frappe n'apparaît qu'à l'exécution, devant l'apprenant.

**Règle de fermeture (AD-7).** Chaque op a un modèle pydantic de ses arguments (`scenarios/ops/<nom>.py`). Un lint de contenu (étape de CI, AD-18) charge tous les YAML et vérifie ops, types d'étape, outils, `job_id`, types d'explication, `barrier`, alias (T7) et `step_id` (T16). Aucun contenu n'est publié sans lint vert.

## T21 — Divers (basse)

- **Versions en triple** : tableau « Stack », `uv.lock` et `tools.toml` (version provisionnée de gitleaks) peuvent diverger. Règle : un test de CI compare la table à `uv.lock` et `tools.toml`.
- **Balises CI** `wds:job` / `wds:end` : l'apprenant modifie ces fichiers (c'est l'exercice) ; si les balises disparaissent, la plage de lignes est introuvable. Règle : `ci` lit sur le SHA de tête de la PR et renvoie « balises absentes » comme constat non bloquant, jamais une exception.
- **Rétention** des instantanés et du journal : voir T4 et T19.
- **`exporting`** comme état exclusif est inutile (l'export ne touche pas l'espace) : le retirer de l'énumération.
- **llmrun** : l'état du moteur pendant `run_exercise_code` n'est pas défini (il peut écrire dans `repo/`). Règle : état `command`, instantané préalable.
