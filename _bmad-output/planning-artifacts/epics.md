---
status: final
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-wavedevsecops-2026-10-18/prd.md
  - _bmad-output/planning-artifacts/prds/prd-wavedevsecops-2026-10-18/addendum.md
  - _bmad-output/planning-artifacts/architecture/architecture-wavedevsecops-2026-10-18/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-wavedevsecops-2026-10-18/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-wavedevsecops-2026-10-18/EXPERIENCE.md
  - _bmad-output/specs/spec-wavedevsecops/scenarios.md
  - _bmad-output/specs/spec-wavedevsecops/milestones.md
---

# WaveDevSecOps - Découpage en epics

## Vue d'ensemble

Ce document découpe en epics et stories les exigences du PRD, de l'UX (DESIGN.md, EXPERIENCE.md) et de l'architecture (spine, AD-1 à AD-20). Le découpage suit les jalons v0.1, v0.2, v0.3 et v1.0. Chaque story cite les AD qu'elle doit respecter.

## Inventaire des exigences

### Exigences fonctionnelles

FR-1 (v0.1) : l'apprenant tape des commandes git dans le terminal intégré, et elles s'exécutent sur le bac à sable. La sortie affichée est celle de git (stdout et stderr), sans réécriture. `push`, `pull` et `fetch` agissent sur `origin`, réseau coupé.
FR-2 (v0.1) : le terminal accepte aussi une courte liste de commandes de fichiers (fixée par AD-4). Toute commande hors liste est refusée avec une explication en français. Aucune commande acceptée ne lit ni n'écrit hors du bac à sable et de `origin`.
FR-3 (v0.1) : l'apprenant édite un fichier dans la vue Code et l'enregistre, ou l'ouvre dans son éditeur externe. Après un enregistrement, `git status` voit le changement. Après une modification externe, les vues se mettent à jour seules, dans un délai chiffré fixé au découpage.
FR-4 (v0.1) : les vues sont fidèles à l'état réel. Après chaque commande ou enregistrement, le graphe est conforme à `git log --all` et l'index à `git status`. Les vues sont à jour avant l'explication. La vue Distant montre les refs de `origin` et les PR.
FR-5 (v0.1) : sélectionner un élément (commit, fichier, PR…) met en évidence ses correspondants dans les autres vues (table de correspondances de l'UX).
FR-6 (v0.1) : l'apprenant ouvre une PR depuis une branche poussée, la fait relire et la merge. Le merge met à jour `main` sur `origin`, et le graphe le montre.
FR-7 (v0.1) : un scénario fait apparaître sur `origin` le commit d'un collègue simulé, récupérable par `git pull`.
FR-8 (v0.1) : dès v0.1, le modèle de PR porte checks, approbations et protection de branche. Un scénario de test qui active un check bloquant empêche le merge, sans modifier le modèle.
FR-9 (v0.1) : le catalogue présente les scénarios dans l'ordre conseillé (add/commit → push/pull → branche → PR/merge → conflit → stash → rebase → reflog/reset), avec accès libre. Chaque scénario prépare son propre état. Le catalogue indique l'état terminé.
FR-10 (v0.1) : « Recommencer » remet le scénario à son état initial (même empreinte). Chaque remise à zéro est journalisée, sans pénalité. Le score du premier coup et le compte d'indices restent ceux du premier passage.
FR-11 (v0.1) : en mode A, chaque étape donne une consigne et une explication. La validation porte sur l'état réel, jamais sur le texte tapé. Un état inattendu est expliqué, sans plantage.
FR-12 (v0.1) : en mode B, un agent scénarisé a déjà agi, erreurs réalistes comprises. Le rejeu donne le même état. Il y a un scénario pour chaque erreur : `.env` committé, `push --force` qui écrase un collègue, stash oublié, rebase laissé en conflit. Le scénario `.env` annonce les barrières qui l'auraient bloqué. À la question « qu'a fait l'agent ? », l'apprenant désigne l'élément dans les vues ou tape un SHA, en un seul essai. La correction est automatique et compte dans le score du premier coup (SM-4).
FR-13 (v0.1) : trois paliers d'indice (piste, commande partielle, solution), ouverts dans l'ordre. Chaque palier ouvert compte pour un indice, sans pénalité. La solution s'ouvre après un essai ou un délai de lecture, et l'apprenant la tape lui-même. Le suivi enregistre le palier, le temps avant la demande et le temps de lecture.
FR-14 (v0.1) : un scénario s'écrit en YAML, sans modifier le code, tant qu'il utilise des types d'étape existants. Un nouveau type d'étape ne modifie pas les scénarios existants.
FR-15 (v0.1) : une mauvaise commande de quiz s'exécute pour de vrai, son effet est expliqué, puis il est annulé. Après l'annulation, l'état est identique : commits, refs, index, arbre, stash, refs de `origin` et PR. Si la restauration échoue, l'application le signale et propose « Recommencer ».
FR-16 (v0.1) : l'apprenant choisit entre le parcours LLM et le parcours sans IA, qui suivent la même progression ; seul le code d'exercice change. Le code LLM évolue : appel simple → prompt système → outils → boucle. Aucun scénario n'exécute le code LLM. Chaque parcours a sa propre progression.
FR-17 (v0.1) : l'apprenant peut, en option, exécuter le code d'exercice du parcours LLM. Aucun scénario n'en dépend.
FR-18 (v0.1, complétée en v1.0) : installation par une commande unique (PowerShell, ou sh) ou depuis un clone ou un zip, sans droits administrateur, en moins de 10 min, sur Windows 10/11, macOS et Linux, y compris derrière un proxy. En v0.1, elle couvre git et l'application ; en v1.0, tous les outils de la chaîne, puis un usage entièrement hors ligne.
FR-19 (v0.1) : la page de diagnostic donne la présence et la version de chaque outil requis par le jalon, avec la marche à suivre. Un outil absent ou trop ancien rend ses scénarios indisponibles. La page détecte le proxy et rappelle les certificats et `NO_PROXY`.
FR-20 (v0.1) : pour chaque scénario terminé, l'apprenant voit son score du premier coup et le nombre d'indices. Ces données sont gardées dans un fichier local lisible, survivent au redémarrage et portent les horodatages d'installation et de premier lancement. Le score de l'entretien RSSI se mesure de la même façon.
FR-21 (v0.2) : station 1. L'apprenant lance ruff et pytest ; un hook pre-commit gitleaks refuse un commit qui contient un secret, avec la sortie de gitleaks. Le défaut de lint et le test cassé prévus échouent visiblement.
FR-22 (v0.2) : station 2. Le pipeline simulé tourne sur chaque PR, avec un check par outil. Une PR qui a un check obligatoire en échec, ou à qui manque la revue obligatoire, ne peut pas être mergée. Un push direct sur `main` est refusé.
FR-23 (v0.2) : le même pipeline est écrit pour GitHub Actions, Jenkins et GitLab CI, en lecture seule. Chaque tâche renvoie à ses lignes dans les trois fichiers.
FR-24 (v0.2) : SAST avec bandit. Le code vulnérable bloque la PR, en désignant le fichier, la ligne et la règle. Une fois le défaut corrigé, le check repasse au vert.
FR-25 (v0.2) : SCA avec pip-audit, et SBOM consultable. La dépendance vulnérable bloque la PR, en désignant la dépendance et sa vulnérabilité, réseau coupé.
FR-26 (v0.2) : la quality gate échoue sous 80 % de couverture du nouveau code, en affichant la valeur mesurée et le seuil.
FR-27 (v0.2) : chaque barrière de FR-24 à FR-26 a au moins un scénario dans chaque parcours.
FR-28 (v0.2) : barrières propres au code LLM. Une clé d'API en dur est bloquée par gitleaks. Un outil trop puissant est bloqué par bandit, avec deux approbations exigées. Un test de config (locale par défaut, endpoints sur liste autorisée) échoue sur une config non conforme. L'injection de prompt est nommée et reliée à la revue humaine, sans scénario.
FR-29 (v0.3) : l'apprenant pose un tag SemVer annoté, visible dans le graphe et sur `origin`. Un tag non SemVer est refusé avec explication. Le build produit un artefact au numéro du tag, celui que servent staging puis la prod simulée.
FR-30 (v0.3) : la promotion de staging vers la prod simulée est refusée sans approbation.
FR-31 (v0.3) : sur une version défaillante en prod simulée, le rollback fait servir la version précédente.
FR-32 (v0.2) : la carte de la chaîne met en évidence la station courante et montre la frontière CI | CD. Elle s'ajoute sans refonte de la disposition.
FR-33 (v0.2) : chaque terme du vocabulaire mène à sa barrière : secrets scanning → gitleaks ; SAST → bandit ; SCA/SBOM → pip-audit et SBOM ; quality gate → seuil ; quatre yeux → revue obligatoire et deux approbations ; protection de branche → `main` protégée ; traçabilité → PR et checks (plus tag et approbation de livraison en v0.3). DAST est seulement nommé.
FR-34 (v0.3 au plus tôt, v1.0 au plus tard) : l'entretien RSSI est un quiz. Chaque réponse désigne une preuve dans les vues ; sans preuve, elle n'est pas acceptée. Le score du premier coup est mesuré.
FR-35 (v0.3 au plus tôt, v1.0 au plus tard) : la fiche barrière → risque → preuve, avec ISO 27001, NIS2, DORA et CRA, s'exporte en HTML autonome imprimable et en CSV UTF-8 avec BOM. Elle a une ligne par barrière ; chaque correspondance porte « explicite » ou « interprétation ». Les contrôles ISO sont cités par numéro et intitulé court.
FR-36 (v0.1) : l'apprenant exporte lui-même un rapport de progression (scores, indices, remises à zéro, horodatages). C'est la seule sortie des mesures.

### Exigences non fonctionnelles

NFR-1 : hors ligne de bout en bout ; seul FR-17 peut utiliser le réseau.
NFR-2 : vrai git, jamais simulé ; les messages affichés sont ceux de git.
NFR-3 : déterminisme. Aucun LLM ne pilote git ; l'agent B est scénarisé ; un scénario rejoué donne le même état.
NFR-4 : outils réels et légers (ruff, pytest, pre-commit, gitleaks, bandit, pip-audit), sans serveur lourd, disponibles sur les trois systèmes.
NFR-5 : Windows 10/11, macOS et Linux, avec un comportement identique pour les scénarios.
NFR-6 : séances courtes. Le socle git tient en 1 h ; les stations 1 et 2 en 1 h ; la station 3 en 1 h ; la station 4 en séance courte.
NFR-7 : échecs pédagogiques. Une erreur donne une explication, jamais un plantage.
NFR-8 : interface et contenus en français ; identifiants du code en anglais.
NFR-9 : confidentialité. Aucune télémétrie ni aucun appel réseau, sauf FR-17. Les mesures ne sortent que par FR-36. L'absence d'appel réseau est vérifiée en CI et énoncée dans le README.
NFR-10 : points d'ancrage dès v0.1 : YAML extensible, modèle de PR complet, gabarits avec `pyproject.toml` et `tests/`, disposition qui accepte une vue en plus.
NFR-11 : une release SemVer par jalon (manifeste, tag annoté, release GitHub avec notes) ; open source, topic `ai-portfolio`.
NFR-12 : application web servie par Python et `uv`, ouverte dans le navigateur, sur `127.0.0.1` et un port libre ; pywebview en repli.
NFR-13 : chaque élément affiché porte une explication courte en français, accessible depuis l'élément.

### Exigences complémentaires (architecture)

**Amorce du projet (pas de starter externe)** : la Story 1.1 crée le dépôt selon le Structural Seed du spine :
- `pyproject.toml` (uv, version SemVer, groupes `chain` et `dev`, extra `window`) ;
- `.gitattributes` `* text=auto eol=lf` ;
- `src/wavedevsecops/` avec les modules feuilles `config` (`Settings` unique), `contracts`, `events` ;
- `procs`, `content/` et `tests/` ;
- la CI GitHub Actions sur `windows-latest`, `macos-latest` et `ubuntu-latest`.

Stack exacte : table Stack du spine (Python 3.14 géré par uv, FastAPI 0.144.0, uvicorn 0.54.0, pydantic 2.14.1…).

- AR-1 (règles de dépendance) : les flèches du schéma ne remontent jamais. `contracts`, `events` et `config` sont des feuilles. Seul `procs` crée des processus, et seuls `gitio` et `toolrun` l'appellent. Seul `wsfs` touche aux fichiers du bac à sable. Seul `llmrun` sort sur le réseau.
- AR-2 (AD-1) : moteur à un seul écrivain. Chaque espace a une file d'opérations typées et des états `idle|command|quiz_altered|restoring|setup|exporting`. L'ordre est fixe : sortie → projections → validation → explication. Un `epoch` rejette les opérations périmées. Le surveillant `watchfiles` est suspendu pendant les commandes et filtré par empreinte. Un `base_hash` accompagne chaque enregistrement. `Settings.max_active_workspaces` borne les espaces actifs.
- AR-3 (AD-2) : `RepoState` et ses projections sont calculés par le serveur. Le placement du graphe est déterministe et testé. La grammaire `element_id` est unique. Annotations (`new`, `restored`, `lost`, `designable`, `a11y_name_text`, `links`, `explain_ref`, `announce_text`, raisons de blocage) et `spans` liables du terminal sont fournis par le serveur. Le front ne calcule ni score, ni correspondance, ni texte d'annonce.
- AR-4 (AD-3) : `gitio` a deux contextes. Le contexte apprenant tourne en locale française sondée ; le contexte interne en `LC_ALL=C` avec des commandes plumbing. Un environnement hermétique (`GIT_CONFIG_*` forcés, éditeur `:`, sans prompt ni proxy) et un setup déterministe (dates et identités fixes, LF) garantissent les mêmes SHA sur les trois OS.
- AR-5 (AD-4) : terminal sans shell, avec un découpeur POSIX et des métacaractères refusés. Les commandes de fichiers sont écrites en Python sur `wsfs` ; `cd` est refusé. Git passe par une liste blanche de sous-commandes et d'options. Les outils de station ne sont acceptés que si l'étape les déclare. En `quiz_altered`, seules les commandes de lecture passent. Les listes blanches tiennent dans `content/terminal-allowlist.yaml`. Ctrl+C arrête l'arbre de processus.
- AR-6 (AD-5) : disposition des données `<data>/` (platformdirs) avec `workspaces/<parcours>/<scenario_id>.<mode>/`, et un propriétaire unique par fichier.
- AR-7 (AD-6) : instantanés par copie et empreinte canonique sha256. L'instantané 0 est pris à la fin du setup, puis un instantané avant chaque quiz. La restauration est atomique et journalisée dans `run.json`, avec trois essais sous Windows et `restore_failed` comme repli. Recommencer restaure l'instantané 0, sinon reconstruit l'espace.
- AR-8 (AD-7) : scénarios YAML validés par pydantic. Un registre d'ops de setup et un registre de types d'étape (`check(state, ctx) -> Verdict`) ; des alias `@`. Un `step_id` stable ; trois indices ; un ensemble de bonnes réponses. `content/explanations.yaml`. Les gabarits d'exercice par parcours vivent dans `content/exercise/`. Un lint de contenu tourne en CI.
- AR-9 (AD-8) : `github.json` n'a qu'un écrivain, `github_sim`. Le modèle de PR est complet dès v0.1. Les checks sont liés à `head_sha`/`base_sha` et remis à `queued` quand le SHA change. Le merge passe par `merge-tree --write-tree`/`commit-tree`/`update-ref`. Un vrai hook `pre-receive` protège la branche. Les réactions du collègue sont déclarées par le scénario.
- AR-10 (AD-9) : hooks `#!/bin/sh` d'une ligne, générés par `install_hooks`, vers `python -m wavedevsecops.hooks`. Un seul `hooks/` par espace, désigné par `core.hooksPath`. pre-commit tourne en `repo: local` / `language: system`.
- AR-11 (AD-10) : `content/pipeline.yaml` est la seule description du pipeline. Un run par `(pr, head_sha, base_sha)` et `epoch`, cloné dans `ci/`. La sortie humaine est affichée verbatim ; les constats viennent d'une exécution machine (json). La quality gate combine `pytest --cov` et `diff-cover --fail-under=80`. Les balises `wds:job`/`wds:end` délimitent les trois écritures.
- AR-12 (AD-11) : pip-audit est le vrai outil, pointé sur `osv`, un point local `POST /osv/v1/query` servi depuis `content/osv/` (extrait daté). Trois exécutions : humaine, json, cyclonedx.
- AR-13 (AD-12) : `procs.spawn`/`terminate_tree` (Job Object sous Windows). `toolrun` résout chaque outil par le registre et lance avec un env hors ligne (`UV_OFFLINE`, `PIP_NO_INDEX`, `NO_PROXY`…). Le `uv-cache` est préchargé ; les environnements viennent de `uv sync --offline --frozen`.
- AR-14 (AD-13) : aucun appel réseau sauf `llmrun`, sur l'intention `run_exercise_code{confirmed}`. Le front est entièrement vendorisé. Quatre contrôles en CI : imports interdits, URL dans `static/`, hook d'audit `socket.connect`, et `unshare -n` sous Linux.
- AR-15 (AD-14) : `progress.json` n'a qu'un écrivain. Il ne reçoit que des ajouts, avec une clé d'idempotence ; le premier passage fait foi. Les scores sont dérivés. Les exports sont rendus par Jinja2 en HTML autonome et en CSV UTF-8 avec BOM (séparateur `;`). La fiche lit `content/barriers.yaml`.
- AR-16 (AD-15) : `install.ps1` et `install.sh` sans droits administrateur. Ils installent uv dans le profil, clonent avec `autocrlf=false`, précachent les dépendances, puis installent git (PortableGit sous Windows, pixi conda-forge ailleurs) et gitleaks (archive vérifiée par `checksums.txt`). Ils respectent le proxy (`UV_SYSTEM_CERTS`) et écrivent `install.json`. Le test `xcode-select` est fait sous macOS.
- AR-17 (AD-16) : `tools.toml` est le registre unique (versions minimales : git ≥ 2.38, uv ≥ 0.11.0, gitleaks ≥ 8.20.0 ; les outils Python à la version du `uv.lock`). `content/diagnostic.yaml` porte les textes. Un test de CI compare le registre, la table Stack et `uv.lock`.
- AR-18 (AD-17) : enveloppe d'événements `{boot_id, seq, ts, workspace_id, epoch, op_id, kind, payload}` et catalogue des `kind`. Intentions par `POST /api/ws/<id>/…`, avec un 409 et un `reason_text` en cas de refus. Flux SSE avec `Last-Event-ID`, tampon circulaire et `resync_required`.
- AR-19 (AD-18) : CI sur trois OS : ruff, pytest, contrôles AD-13, lint de contenu et empreintes de référence (`content/fingerprints.json`), y compris un clone `autocrlf=true` sous Windows. Tests de confinement et d'arrêt d'arbre sur les trois OS. Mesure du temps d'installation et release à chaque jalon.
- AR-20 (AD-19) : écoute sur `127.0.0.1` et un port libre. Un jeton de lancement est échangé contre un cookie `HttpOnly SameSite=Strict`. Vérification de `Host` et d'`Origin`, sans CORS. `/osv/` reste public, en POST et en lecture.
- AR-21 (AD-20) : instance unique (`app.lock`), `schema_version` et migrations numérotées, `content_hash` du scénario dans `run.json`, mise à jour par l'installeur, journaux en rotation, console de lancement (adresse, diagnostic, rappel `NO_PROXY`, `--window`).
- AR-22 (conventions) : textes en `_text` écrits par le serveur ; vouvoiement ; chemins posix relatifs ; dates ISO 8601 et `duration_ms` ; exceptions typées converties en `app_error` ou en 409 ; écritures atomiques ; front en modules ES sans build ni framework, avec un registre des volets.
- AR-23 (différé, à fixer au découpage) : délais chiffrés dans `Settings` (mise à jour après une modification externe, déblocage de la solution, délai des commandes, tailles des tampons) ; composant d'édition et rendu SVG du graphe, choisis par leur story ; forme de l'artefact et de « servir » en station 4 ; options exactes de pip-audit.

### Exigences de design UX

UX-DR1 : jetons de couleur clairs et sombres de DESIGN.md, sous forme de propriétés CSS. Ils comprennent les ajouts `terminal-*` et `focus-on-ink`. Le `theme-picker` propose Système (par défaut), Clair et Sombre, dans le menu « Affichage ▾ ».
UX-DR2 : typographie Fredoka, Atkinson Hyperlegible et JetBrains Mono, servie en WOFF2 local. La rampe a 10 rôles ; aucun texte sous 12 px.
UX-DR3 : espacements, arrondis (sm/md/lg/full), relief plein sans flou (4, 1 et 6 px), fond à pois derrière les vues seulement, et jetons propres à WaveDevSecOps (`scenario-panel-width` 440 px, `chain-band-height`, `graph-row-height`, `diff-line-height`…).
UX-DR4 : `site-nav`. Liens selon les jalons, page courante soulignée, `diagnostic-badge`, `path-menu`, « Volets ▾ » (`pane-menu`) et « Affichage ▾ » (thème, « Réduire les animations »).
UX-DR5 : disposition principale à 1920×1080. Panneau Scénario de 440 px ; rangée haute à 40 % (Dépôt local 55 %, Distant + PR 45 %) ; Code à 33 % ; Terminal à 27 %. Chaque vue a un `pane-step` numéroté, un sous-titre fixé et un défilement interne avec en-tête fixe. Les vues sont déclarées dans un registre des volets.
UX-DR6 : masquage et redimensionnement. « — » transforme une vue en puce « + Nom » ; ⛶ l'agrandit (Échap pour revenir) ; la poignée se déplace au clavier par pas de 16 px (double-clic pour les proportions par défaut) ; le menu Volets propose Élargir et Réduire. Une vue au moins reste visible, d'au moins 240×160 px. La configuration est mémorisée dans le navigateur. Le panneau Scénario ne se masque pas.
UX-DR7 : quatre états visuels, focus, lié, sélectionné (contour encre et ●) et désignable (tirets primary), avec la préséance verdict > sélection > désignable > lié. L'estompage ne change jamais l'opacité du texte. `focus-ring` est décalé de 2 px, en `focus-on-ink` sur fond encre.
UX-DR8 : `scenario-panel`. Titre, `mode-badge` avec son « i », `step-progress` (segments cliquables qui rouvrent la consigne), consigne en `chat`, zone de question, `step-explanation` (variantes correction et « Ce qui l'aurait bloqué », avec « Arrive en v0.2 »), `hint-tabs`, puis « Recommencer » ; le bilan à la fin.
UX-DR9 : `quiz-choice` en groupe radio, une carte par commande. « Exécuter ma réponse » reste inactif tant que rien n'est coché et l'affiche (« Choisissez une commande. »).
UX-DR10 : `quiz-banner`. Il s'affiche au-dessus des vues avec « État modifié par le quiz — <commande> » et « J'ai compris, rétablir l'état ». Il prend le focus à son apparition, et le terminal passe en lecture seule (`aria-readonly`). Pendant le rétablissement, « Rétablissement de l'état… 1 s » s'affiche et les vues sont `inert`. Ensuite, « Rétabli » marque les éléments et le focus revient au panneau.
UX-DR11 : `notice-card`, encart en ligne jamais modal, avec un filet info, avertissement ou erreur, une cause, une explication et une à trois actions. Il sert aux cas État inattendu, Bac à sable indisponible, Rétablissement échoué et Export impossible.
UX-DR12 : `score-summary` selon le gabarit « 3 sur 4 du premier coup · 1 indice » (accords 0/1/2 indices), avec « Scénario suivant », « Catalogue » et « Recommencer ».
UX-DR13 : terminal. Composants `terminal-prompt` (branche courante), `terminal-stderr` (jamais rouge), `terminal-exit-error`, `terminal-app-message` (« › ») et `terminal-refused`. Touches Entrée, ↑/↓, Ctrl+C et Ctrl+L ; Tab sort du terminal ; Échap rend le focus au titre ; pas de complétion en v0.1. Au-delà de 5 000 lignes, les plus anciennes sont masquées. « En cours… n s » s'affiche après 1 s. La région a `role="log"`, un préfixe masqué « erreur standard : » et `lang="en"` sur une sortie anglaise.
UX-DR14 : graphe. Composants `graph-commit`, `graph-edge`, `graph-head` (et « HEAD détachée »), `graph-branch` (pilule, icône poste), `graph-remote-ref` (double bord, icône serveur), `graph-tag` (encoche), `graph-commit-lost` (tirets, « perdu · visible par reflog ») et les badges « Collègue » et « Agent ». Le nom accessible suit un gabarit. La zone de clic couvre le disque, le SHA et le message. `commit-list` est l'alternative texte, accessible par le bouton Liste/Graphe.
UX-DR15 : `new-mark` « Nouveau » posé par la dernière commande, et « Rétabli » après un quiz.
UX-DR16 : `staging-index` en trois groupes (Indexé, Modifié non indexé, Non suivi), avec la lettre d'état git. Un clic sélectionne sans indexer.
UX-DR17 : `code-editor` avec arbre de fichiers, marque « non enregistré », Ctrl+S, « Ouvrir dans mon éditeur » et marqueurs de conflit éditables. `external-change-notice` affiche « Modifié hors de l'application », ou « Garder ma version » / « Recharger » en cas de conflit.
UX-DR18 : `diff-view` et `diff-file-header`. Le diff suit la sélection (commit, PR ou arbre de travail). Chaque ligne et chaque en-tête sont liables, focalisables et désignables.
UX-DR19 : Distant + PR. `pr-card` (ordre : checks en échec, `merge-blocked`, checks réussis, `review-log`). `pr-check` a cinq états : réussi, échec avec ligne de détail, en cours (seul élément animé), erreur de l'outil (« Relancer le check ») et l'étiquette « Obligatoire ». `review-log` affiche le compteur « Approbations : 1 sur 2 ». `merge-blocked` donne une raison par ligne, liée à son élément.
UX-DR20 : `tool-output`. Sortie réelle dans un bloc, étiquette au nom de l'outil, fichier:ligne liés à Code. Le bloc est focalisable et désignable.
UX-DR21 : `pipeline-tabs` (GitHub Actions | Jenkins | GitLab CI), « Lecture seule ». Les lignes de la tâche sont surlignées avec « lignes x à y ». Changer d'onglet garde la tâche ; le survol d'un check éclaire ses lignes.
UX-DR22 : `sbom-view` en lecture seule (composant, version, licence, vulnérabilités). Une ligne vulnérable est marquée ✗ ; chaque ligne est liable et désignable.
UX-DR23 : `network-run-button` « Exécuter le code (réseau possible) », avec la confirmation en ligne « Ce code peut appeler un service en ligne. Continuer ? ».
UX-DR24 : `explain-popover` déclenché par « i », au clic, à Entrée ou à Espace, jamais au survol. Échap rend le focus au « i ». Il tient en deux ou trois phrases.
UX-DR25 : correspondances entre vues, selon la table de l'UX. `terminal-lit` éclaire les lignes liées du terminal. Une vue masquée qui contient un correspondant montre la puce « + Nom · lié ». Le défilement vers un correspondant se fait au clic, jamais au survol. Le résumé « n éléments liés : … » est relié par `aria-describedby`, avec « Voir les éléments liés ».
UX-DR26 : désignation. `designate-button` armé (`aria-pressed`, curseur crosshair, Échap pour désarmer) ; `designable` ; `answer-slot` avec ✕ ; `designate-list` groupée par vue et filtrable ; `sha-field` (7 caractères au moins, aperçu, SHA inconnu sans consommer l'essai). « Valider ma réponse » porte « 1 seul essai ». `verdict-mark` affiche « ✓ Attendu », « ✓/✗ Votre choix » et « ≡ Accepté aussi ».
UX-DR27 : entretien RSSI à deux cases, Réponse (`quiz-choice`) et Preuve (désignation). « Valider » reste inactif et dit « Il manque la preuve. Désignez-la dans les vues. ».
UX-DR28 : `hint-tabs` en `tablist`. Un onglet verrouillé montre un cadenas et sa condition (« Disponible après un essai ou un moment de lecture. »), sans décompte. Son déblocage est annoncé. Aucun compteur n'apparaît pendant l'étape. La commande partielle porte des blancs. La solution est sélectionnable, sans bouton Copier ni Exécuter.
UX-DR29 : catalogue. Au premier passage, `path-picker` pose seul la question du parcours. Puis trois `catalogue-section` (Socle git, Stations, Savoir en parler), où une section d'un jalon non livré est masquée. `scenario-card` porte les colonnes Mode A et Mode B et les états À faire, En cours et Terminé avec le score. « Reprendre » apparaît sur le dernier scénario ouvert, avec un encart « ne peut pas reprendre » si besoin. Une carte indisponible affiche « ⊘ Indisponible · Nécessite <outil> · Voir le diagnostic ». Le pied propose « Exporter mon rapport ».
UX-DR30 : page Diagnostic. Elle s'ouvre d'office au premier lancement et propose « Relancer ». Une synthèse en `role="status"` résume l'état. Chaque ligne passe par « En cours » puis prend son état (✓ OK, ⚠ Trop ancien, ✗ Absent). Le tableau est groupé par jalon, avec « Que faire ? » dépliable et les scénarios indisponibles nommés. La section Proxy montre la valeur masquée, `NO_PROXY` et les certificats. Sans git, un encart d'erreur s'affiche et tout le catalogue est grisé. Le pied propose « Continuer vers le catalogue ».
UX-DR31 : `report-preview` (contenu, phrase de confidentialité, « Exporter en HTML » et « Exporter en CSV ») et `barrier-sheet` (colonnes Barrière | Risque | Preuve | ISO 27001 | NIS2 | DORA | CRA ; étiquettes « explicite » et « interprétation » ; « Preuve pas encore vue : scénario <nom> » ; version impression).
UX-DR32 : `chain-band`, avec quatre « Station n · Nom », la station courante et « Vous êtes ici » (`aria-current="step"`), la frontière « CI | CD » et « Carte ▾ ». `chain-map` se pose par-dessus les vues, qui deviennent `inert`. Ses nœuds d'outil et de barrière sont liés aux checks, aux hooks et aux termes ; « Bientôt » marque un jalon non livré.
UX-DR33 : page Vocabulaire et `glossary-term` (souligné en pointillés). « Voir la barrière » sélectionne la barrière, ou déplie la carte avec « La voir jouer : scénario <nom> ». DAST porte « Nommé seulement ».
UX-DR34 : Livraison. Onglet « Livraison » dans Distant + PR ; `build-artifact` ; `env-card` Staging et Prod simulée ; `promotion-gate` ; Rollback en `button-danger` avec confirmation en ligne ; refus d'un tag non SemVer par `terminal-refused`.
UX-DR35 : états vides et transitoires. Textes des vues vides ; « Préparation du bac à sable… » sans spinner muet ; bandeau « WaveDevSecOps ne répond plus… » avec actions inactives ; outil disparu pendant un scénario signalé, le reste continuant.
UX-DR36 : clavier. Tab suit l'ordre de lecture et saute les vues masquées. Chaque vue est un seul arrêt, avec focus itinérant par flèches. F6 passe d'une zone à l'autre. Échap ferme dans l'ordre fixé. Sont bannis : modales bloquantes, information au seul survol, auto-défilement qui reprend la main, troncature sans accès au texte entier, exécution d'une commande par clic.
UX-DR37 : annonces. Une seule région `role="status"` suit l'ordre de FR-4. `role="alert"` sert au refus, au hook, à l'échec de restauration et à l'application arrêtée. Les chronomètres ne sont jamais dans une région live.
UX-DR38 : à 400 % de zoom (320 px CSS), le panneau, le catalogue et les annexes passent sur une colonne. `prefers-reduced-motion` et « Réduire les animations » coupent les transitions.
UX-DR39 : repli responsive. Sous 1920×1080, les vues passent en puces selon l'ordre fixé. Sous 1280 px, il reste le panneau et une vue agrandie. À 640 px ou moins, tout passe sur une colonne.
UX-DR40 : boutons `button-primary`, `button-secondary`, `reset-button` et `button-danger`. Un bouton inactif dit pourquoi, dans un texte visible et relié (`aria-disabled`). Recommencer a sa confirmation en ligne et son message « Scénario remis à zéro. ».
UX-DR41 : Voice and Tone. Phrases courtes, sans « ! » ni emoji ; le message nomme qui décide ; gabarits de l'UX ; les sorties de git et des outils ne sont jamais traduites.

### Carte de couverture des FR

FR-1 : Epic 2 - vraies commandes git dans le terminal
FR-2 : Epic 2 - commandes de fichiers et confinement
FR-3 : Epic 2 - édition dans la vue Code et changements externes
FR-4 : Epic 2 - vues fidèles à l'état réel
FR-5 : Epic 2 - correspondances entre vues
FR-6 : Epic 3 - cycle de PR
FR-7 : Epic 3 - commits d'un collègue
FR-8 : Epic 3 - modèle de PR prêt pour les stations
FR-9 : Epic 6 - catalogue en ordre conseillé, accès libre
FR-10 : Epic 4 - Recommencer
FR-11 : Epic 4 - étapes du mode A validées sur l'état réel
FR-12 : Epic 5 - scénarios du mode B et désignation
FR-13 : Epic 4 - indices à paliers
FR-14 : Epic 4 - scénarios déclaratifs, types d'étape extensibles
FR-15 : Epic 4 - quiz à exécution réelle et rétablissement
FR-16 : Epic 2 (gabarits d'exercice des deux parcours), Epic 6 (choix du parcours) - deux parcours
FR-17 : Epic 6 - exécution facultative du code LLM
FR-18 : Epic 1 (git et application, v0.1), Epic 7 (outils des stations, v0.2), Epic 12 (installation complète vérifiée, v1.0)
FR-19 : Epic 1 - page de diagnostic
FR-20 : Epic 4 - score et indices par scénario
FR-21 : Epic 7 - station 1, poste local
FR-22 : Epic 7 - station 2, pipeline simulé sur PR
FR-23 : Epic 7 - trois écritures du pipeline
FR-24 : Epic 8 - SAST avec bandit
FR-25 : Epic 8 - SCA avec pip-audit, et SBOM
FR-26 : Epic 8 - quality gate
FR-27 : Epic 8 - scénarios dans les deux parcours
FR-28 : Epic 8 - barrières propres au code LLM
FR-29 : Epic 10 - tag et build
FR-30 : Epic 10 - promotion après approbation
FR-31 : Epic 10 - rollback
FR-32 : Epic 9 - carte de la chaîne
FR-33 : Epic 9 - vocabulaire lié aux barrières
FR-34 : Epic 11 - entretien RSSI
FR-35 : Epic 11 - fiche barrière → risque → preuve
FR-36 : Epic 6 - rapport de progression exporté

## Décisions de découpage (PRD §10)

Validées par Anaël le 2026-10-18.

### Jalon de l'entretien RSSI et de la fiche

**v0.3** (Epic 11). Le scénario commence par des étapes de préparation où l'apprenant fait jouer les vrais outils dans son espace : push, pipeline, gitleaks dans le terminal. Aucune preuve n'est fabriquée (AD-7 inchangé, SM-C2). Le tag et l'approbation de livraison viennent d'ops de setup, car ce sont des objets git et `github.json`, pas des sorties d'outil.

### Lot de finition v1.0 (Epic 12)

- Installation complète vérifiée en moins de 10 min sur trois postes réels (SM-5), mise à jour sans perte de progression (AD-20), durcissement derrière un proxy.
- Correction des retours du test v0.1 et des ateliers.
- Audit d'accessibilité AA dans les deux thèmes : zoom à 400 %, clavier, annonces.
- Relecture des numéros ISO 27001 de `content/barriers.yaml` (non vérifiés, d'après l'addendum).
- Chronométrage des séances (SM-6) et passage complet sans indice dans les deux parcours (SM-8).
- README (avec l'énoncé de NFR-9) et guide d'atelier.
- Mesure du transfert hors de l'application : protocole écrit, puis exercice de fin d'atelier où l'apprenant répare seul un vrai dépôt cassé.
- Release v1.0.0 et présentation.

### Parcours utilisateur de la station 4

C'est le parcours UJ-5. Il s'écrit, avec le flow UX de la livraison, par `bmad-ux` en mise à jour avant le sprint v0.3. Le spine est ensuite complété par `bmad-architecture` sur les points différés de la station 4. C'est un prérequis de l'Epic 10, hors story.

### Ligne de coupe par jalon

On sacrifie d'abord ce qui suit, dans l'ordre. Un élément coupé passe au jalon suivant.

| Jalon | Ordre de coupe | Jamais coupé |
|---|---|---|
| v0.1 | 1. Exécution du code LLM (FR-17) ; 2. scénarios B « stash oublié » et « rebase en conflit » (« `.env` » et « `push --force` » restent) ; 3. « Reprendre » remplacé par une réouverture à l'étape 1 ; 4. repli responsive sous 1280 px | Vrai git, vues fidèles, quiz réel et rétablissement, installation, diagnostic, hors ligne |
| v0.2 | 1. Carte dépliée `chain-map` (le bandeau reste, et « Voir la barrière » se replie sur le nom du scénario) ; 2. test de config LLM (troisième barrière de FR-28) ; 3. page Vocabulaire (les termes liés dans les explications restent) | bandit, pip-audit hors ligne, quality gate, protection de `main`, trois écritures |
| v0.3 | 1. Historique des `env-card` ; 2. export CSV de la fiche (le HTML reste) | Approbation obligatoire, rollback, entretien RSSI avec preuve |
| v1.0 | 1. Mesure du transfert, reportée après v1.0 ; 2. version impression soignée de la fiche | Installation complète hors ligne, SM-7 |

### Délais chiffrés (valeurs de `Settings`)

| Réglage | Valeur |
|---|---|
| Mise à jour des vues après une modification externe (FR-3) | ≤ 2 s, après 300 ms de silence du surveillant |
| Déblocage de la solution (FR-13) | un essai (commande tapée ou choix validé pendant l'étape), ou 20 s passées sur le palier « commande partielle » |
| Délai d'une commande git | 30 s |
| Délai d'un outil ou d'un job du pipeline | 120 s |
| Run complet du pipeline | ≤ 45 s sur le poste de référence (venv d'espace réutilisé), vérifié par un test de performance avant la release v0.2 |
| Tampon d'événements SSE (`event_buffer`) | 1 000 |
| Terminal | 5 000 lignes affichées |
| `max_active_workspaces` | 3 |
| `max_snapshots` | 20 (le 0 et le dernier toujours gardés) |

### Questions UX non bloquantes, tranchées par défaut

L'hypothèse de l'UX est retenue, sauf avis contraire :
- question 4 : le mode désignation reste armé jusqu'à la validation ou Échap ;
- question 5 : un essai est une commande tapée ou un choix validé ;
- question 6 : les approbations sont déclarées par le scénario, et arrivent automatiquement quand les checks sont verts ;
- question 7 : les remises à zéro figurent dans le rapport, pas au bilan ;
- question 9 : « Reprendre » rouvre le bac à sable conservé ;
- question 3 : ordre de repli de l'UX.

### Type de story

Chaque story porte une ligne **Type** :
- **dev** : implémentée par un agent (`dev-story`, puis `second-avis`, puis `reviewer`) ;
- **humaine** : menée par Anaël (mesure, test avec des personnes, relecture de sources), l'agent ne l'exécute pas ;
- **mixte** : l'agent fait la partie code et publication, puis le run autonome s'arrête et notifie Anaël, qui fait les critères marqués « (humain) ».

Une story **en attente de l'UX** n'entre pas dans un sprint tant que son prérequis n'est pas levé : `bmad-sprint-planning` la laisse en `backlog`.

### Suivi des preuves vues

Chaque story de barrière (Epics 7, 8 et 10) soumet à `progress` le fait `evidence_seen{barrier_id}` quand sa preuve s'affiche (AD-14). L'Epic 11 n'a donc pas à revenir sur ces stories.

## Liste des epics

### Jalon v0.1 : socle git hors ligne

#### Epic 1 : Installer, lancer et diagnostiquer l'application
Camille installe seule l'application, sans droits administrateur et derrière un proxy. Celle-ci s'ouvre dans son navigateur sur `127.0.0.1`, et la page de diagnostic lui dit quoi régler. Contenu :
- amorce du dépôt et CI sur trois OS avec les contrôles d'AD-13 ;
- serveur protégé (AD-19) et instance unique (AD-20) ;
- installeurs avec git (AD-15) ;
- registre `tools.toml` (AD-16) ;
- jetons et en-tête.

**FR couvertes :** FR-18 (partie v0.1), FR-19 · NFR-1, NFR-5, NFR-8, NFR-9, NFR-12

#### Epic 2 : Taper du vrai git dans un bac à sable et voir l'effet
L'apprenant ouvre un bac à sable préparé par YAML. Il tape git et les commandes de fichiers, puis édite dans la vue Code ou dans son éditeur. Le graphe, l'index et le terminal se mettent à jour dans l'ordre de FR-4, avec les correspondances entre vues. La Story 2.1 vérifie le déterminisme des SHA sur les trois OS. L'epic pose aussi la première version du catalogue et les gabarits d'exercice des deux parcours.

**FR couvertes :** FR-1, FR-2, FR-3, FR-4, FR-5, FR-16 (gabarits) · NFR-2, NFR-3, NFR-7, NFR-10, NFR-13

#### Epic 3 : Collaborer dans un GitHub simulé
L'apprenant pousse vers `origin`, ouvre une PR, reçoit la revue du collègue simulé et merge. Il récupère aussi le commit d'un collègue. Le modèle de PR porte déjà les checks, les approbations et la protection.

**FR couvertes :** FR-6, FR-7, FR-8

#### Epic 4 : Suivre un scénario guidé avec quiz réels et indices
Chaque étape donne sa consigne, se valide sur l'état réel, puis s'explique. Une mauvaise commande de quiz s'exécute, puis l'état est rétabli. Les indices s'ouvrent par paliers. « Recommencer » existe, et le bilan affiche le score du premier coup.

**FR couvertes :** FR-10, FR-11, FR-13, FR-14, FR-15, FR-20

#### Epic 5 : Comprendre ce que l'agent a fait (mode B)
L'apprenant désigne dans les vues l'élément en cause, en un seul essai, et reçoit une correction contre le vrai dépôt. Il y a quatre scénarios d'erreurs d'agent, et l'encart « Ce qui l'aurait bloqué ». La désignation est générique : l'Epic 11 la réutilise.

**FR couvertes :** FR-12

#### Epic 6 : Parcourir le socle git complet dans les deux parcours
Contenu :
- le catalogue complet en ordre conseillé, avec le choix du parcours ;
- les 8 scénarios du mode A, sur les gabarits posés par l'Epic 2 ;
- « Reprendre » ;
- l'export du rapport ;
- l'exécution facultative du code LLM.

L'epic se termine par la release v0.1.0 et le test avec deux collègues (SM-1 à SM-4).

**FR couvertes :** FR-9, FR-16, FR-17, FR-36

### Jalon v0.2 : stations 1 à 3

#### Epic 7 : Voir le poste local et le pipeline simulé bloquer une PR (stations 1 et 2)
Contenu :
- provisionnement de la chaîne : gitleaks et `uv-cache` préchargé ;
- ruff et pytest dans le terminal ;
- hook gitleaks ;
- pipeline simulé sur chaque PR, avec ses checks liés au SHA ;
- revue obligatoire et refus du push direct sur `main` ;
- trois écritures du pipeline en lecture seule ;
- budget de 45 s pour un run complet.

**FR couvertes :** FR-18 (outils v0.2), FR-21, FR-22, FR-23

#### Epic 8 : Voir les barrières de sécurité et de qualité jouer (station 3)
Contenu :
- bandit ;
- pip-audit hors ligne, avec le point OSV local et le SBOM ;
- la quality gate ;
- des scénarios dans les deux parcours ;
- les barrières propres au code LLM.

**FR couvertes :** FR-24, FR-25, FR-26, FR-27, FR-28

#### Epic 9 : Se situer dans la chaîne et en parler le vocabulaire
Le bandeau et la carte dépliée de la chaîne, la page Vocabulaire et les termes liés aux barrières. L'epic se termine par la release v0.2.0 (SM-9).

**FR couvertes :** FR-32, FR-33

### Jalon v0.3 : livraison et entretien RSSI

#### Epic 10 : Livrer une version taguée, la promouvoir et revenir en arrière (station 4)
Tag SemVer, build, staging puis prod simulée, approbation et rollback. Prérequis : le flow UX et le parcours UJ-5 écrits, et le spine complété.

**FR couvertes :** FR-29, FR-30, FR-31

#### Epic 11 : Défendre la chaîne devant un RSSI et repartir avec la fiche
L'entretien est un quiz où chaque réponse s'accompagne d'une preuve désignée. Les preuves sont produites par des étapes de préparation. La fiche s'exporte en HTML et en CSV, avec les correspondances réglementaires. L'epic se termine par la release v0.3.0 (SM-10, SM-7).

**FR couvertes :** FR-34, FR-35

### Jalon v1.0 : finition et présentation

#### Epic 12 : Installation complète, finition et présentation de v1.0.0
Contenu :
- installation de toute la chaîne vérifiée hors ligne sur trois postes réels ;
- mise à jour sans perte ;
- lot de finition (voir Décisions de découpage) ;
- release v1.0.0 et présentation (SM-5, SM-6, SM-8).

**FR couvertes :** FR-18 (fin) · NFR-1, NFR-6, NFR-11

## Epic 1 : Installer, lancer et diagnostiquer l'application

Camille installe seule l'application, sans droits administrateur et derrière un proxy. L'application s'ouvre dans son navigateur sur `127.0.0.1`, et la page de diagnostic lui dit quoi régler. Cet epic pose aussi l'amorce du dépôt, la CI sur trois systèmes et la coquille d'interface qui recevra les vues des epics suivants.

### Story 1.1 : Amorcer le dépôt et la CI sur trois systèmes

En tant qu'Anaël, auteur du projet,
je veux un dépôt amorcé selon le Structural Seed, avec une CI qui tourne sur Windows, macOS et Linux,
afin que chaque story suivante soit vérifiée sur les trois systèmes et sous les règles hors ligne dès son premier commit.

**Type :** dev

**AD à respecter :** AD-13, AD-18, AD-16 (test de cohérence des versions), conventions (Réglages, Fichiers de données, Langue) · **Exigences :** NFR-5, NFR-8, NFR-9, NFR-11, AR-1, AR-14, AR-19

**Critères d'acceptation :**

**Étant donné** un clone neuf du dépôt
**Quand** on lance `uv sync` puis `uv run pytest -q`
**Alors** l'environnement s'installe avec Python 3.14 géré par uv et les versions exactes de la table Stack, et les tests passent
**Et** `pyproject.toml` porte la version `0.1.0.dev0`, les groupes `chain` et `dev`, et l'extra `window` (pywebview 6.2.1)

**Étant donné** le dépôt amorcé
**Quand** on inspecte son arborescence
**Alors** on y trouve :
- `.gitattributes` (`* text=auto eol=lf`) ;
- `src/wavedevsecops/` avec `config.py` : un objet `Settings` pydantic unique, et aucune lecture directe de l'environnement ailleurs ;
- `contracts/` et `events/`, des feuilles sans import du projet ;
- `content/` et `tests/`.

**Et** un test vérifie les règles de dépendance du spine : `contracts`, `events` et `config` n'importent rien du projet, et personne n'importe `web` ni `cli`

**Étant donné** un push ou une PR
**Quand** GitHub Actions s'exécute
**Alors** `ruff` et `pytest` tournent sur `windows-latest`, `macos-latest` et `ubuntu-latest`
**Et** le contrôle (1) d'AD-13 refuse dans `src/` tout import de `socket`, `http.client`, `urllib.request`, `httpx`, `requests`, `aiohttp` ou `ssl`, hors `llmrun` et hors l'écoute de `web` et `cli`
**Et** le contrôle (2) refuse toute URL `http(s)://` non loopback dans `src/wavedevsecops/web/static/`
**Et** le contrôle (3) fait tourner les tests sous un hook d'audit `socket.connect`, qui échoue sur toute adresse non loopback

**Étant donné** la table Stack du spine et `uv.lock`
**Quand** le test de cohérence des versions tourne
**Alors** il échoue si une version épinglée diffère de la table Stack

### Story 1.2 : Lancer l'application sur un serveur local protégé

En tant qu'apprenant,
je veux lancer l'application par une seule commande et la voir s'ouvrir dans mon navigateur,
afin de travailler sans configurer de serveur, sans invite du pare-feu et sans exposer mon poste au réseau.

**Type :** dev

**AD à respecter :** AD-19, AD-20, AD-5 (racine des données), AD-14 (`progress.json`, horodatages seulement), conventions (Erreurs, Fichiers de données) · **Exigences :** NFR-9, NFR-12, FR-20 (horodatage du premier lancement), AR-20, AR-21

**Critères d'acceptation :**

**Étant donné** l'application installée
**Quand** l'apprenant lance `uv run wavedevsecops`
**Alors** uvicorn écoute sur `127.0.0.1`, sur un port libre choisi au lancement, et le navigateur s'ouvre sur `http://127.0.0.1:<port>/?t=<jeton>`
**Et** le serveur échange le jeton contre un cookie `HttpOnly` et `SameSite=Strict`, puis redirige sans le jeton

**Étant donné** le serveur lancé
**Quand** une requête arrive sans cookie valide, ou avec un `Host` autre que `127.0.0.1:<port>` ou `localhost:<port>`, ou en `POST` avec une `Origin` différente
**Alors** elle est refusée, et aucune réponse ne porte d'en-tête CORS
**Et** un test couvre chacun de ces refus

**Étant donné** une instance déjà lancée
**Quand** l'apprenant relance la commande
**Alors** le second lancement lit `<data>/app.lock`, ouvre l'URL de l'instance existante, puis s'arrête sans écrire de fichier

**Étant donné** un premier lancement
**Quand** l'application démarre
**Alors** elle crée `<data>/` sous `platformdirs.user_data_dir("WaveDevSecOps", appauthor=False, roaming=False)`
**Et** elle crée `progress.json`, écrit par `progress` seul, avec `schema_version`, l'horodatage d'installation lu dans `install.json` s'il existe, et celui du premier lancement
**Et** un fichier de données d'une version future n'est pas modifié et donne une erreur claire en français

**Étant donné** un lancement quelconque
**Quand** la console s'affiche
**Alors** elle montre l'adresse locale, le rappel d'ajouter `127.0.0.1` et `localhost` à `NO_PROXY`, et l'option `--window`
**Et** `--window` ouvre la même interface dans pywebview lorsque l'extra `window` est installé
**Et** les journaux vont dans `<data>/logs/app.log`, en rotation, sans contenu de fichier de l'apprenant

### Story 1.3 : Afficher la coquille d'interface avec l'identité WaveStack

En tant qu'apprenant,
je veux une interface lisible, en clair ou en sombre, avec un en-tête qui me mène aux surfaces livrées,
afin de retrouver l'identité de WaveStack et de travailler confortablement, même hors ligne.

**Type :** dev

**AD à respecter :** AD-13 (front entièrement servi par l'application), AD-19 (point de vie sous cookie), AD-2 (le front ne calcule pas), convention Front (modules ES sans build ni framework, registre des volets) · **Exigences :** NFR-1, NFR-8, UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR35 (application arrêtée), UX-DR37, UX-DR38 (mouvement), UX-DR40, UX-DR41

**Critères d'acceptation :**

**Étant donné** la page servie
**Quand** on l'inspecte
**Alors** tous les jetons de DESIGN.md sont des propriétés CSS : couleurs claires et sombres, `terminal-*`, `focus-on-ink`, typographie, espacements, arrondis, relief
**Et** Fredoka, Atkinson Hyperlegible et JetBrains Mono sont servies en WOFF2 depuis `static/`, sans aucune requête externe

**Étant donné** le menu « Affichage ▾ »
**Quand** l'apprenant choisit Système, Clair ou Sombre, ou coche « Réduire les animations »
**Alors** le choix s'applique tout de suite et survit au rechargement
**Et** avec `prefers-reduced-motion` ou la case cochée, les transitions sont coupées

**Étant donné** le `site-nav`
**Quand** il s'affiche
**Alors** il montre la marque et les liens des surfaces du jalon courant (en v0.1 : Catalogue et Diagnostic), avec la page courante soulignée
**Et** la liste des surfaces livrées est déclarée par le serveur

**Étant donné** la page ouverte
**Quand** le serveur local ne répond plus (le point de vie `GET /api/health`, interrogé à intervalle régulier, échoue ; le flux SSE de la Story 2.2 s'y ajoutera)
**Alors** un bandeau `role="alert"` dit « WaveDevSecOps ne répond plus. Relancez-le ; votre progression est enregistrée. » et les actions deviennent inactives

**Étant donné** les quatre variantes de bouton
**Quand** un bouton est inactif
**Alors** il porte `aria-disabled` et sa raison, dans un texte visible et relié
**Et** aucun texte n'est sous 12 px, et l'estompage ne change jamais l'opacité d'un texte

### Story 1.4 : Sonder les outils requis à partir d'un registre unique

En tant qu'apprenant,
je veux que l'application vérifie seule git et uv, leurs versions, la langue de git et la présence d'un proxy,
afin de savoir avant de commencer si mon poste est prêt.

**Type :** dev

**AD à respecter :** AD-16, AD-15 (git du poste, `xcode-select`), AD-3 (sonde de la locale française), AD-12 (`procs` seul lanceur), AD-17 (`diagnostic_check`) · **Exigences :** FR-19, NFR-5, NFR-7, AR-13, AR-17

**Critères d'acceptation :**

**Étant donné** `tools.toml` à la racine
**Quand** on le lit
**Alors** il déclare pour chaque outil : identifiant, usage, jalon, résolution, version minimale (git ≥ 2.38, uv ≥ 0.11.0, gitleaks ≥ 8.20.0), version provisionnée, sonde de version, accès réseau possible, et réglage qui le coupe
**Et** `diagnostic`, les installeurs et le test de cohérence de la Story 1.1 lisent ce seul fichier

**Étant donné** un git à résoudre
**Quand** la sonde tourne
**Alors** elle retient le git du poste s'il atteint la version minimale, sinon celui de `<data>/tools/`
**Et** sous macOS, elle teste `xcode-select -p` avant d'appeler `/usr/bin/git`

**Étant donné** un git trouvé
**Quand** `gitio` sonde `fr_FR.UTF-8`, puis `fr_FR.utf8`
**Alors** le diagnostic ajoute la ligne informative « git parle français » ou « git parle anglais : traductions absentes », jamais bloquante

**Étant donné** des variables `HTTP(S)_PROXY` posées
**Quand** la sonde du proxy tourne
**Alors** elle rapporte le proxy en partie masqué, la présence de `127.0.0.1` et `localhost` dans `NO_PROXY`, et l'état de `UV_SYSTEM_CERTS`

**Étant donné** une sonde qui échoue ou dépasse son délai
**Quand** le diagnostic s'exécute
**Alors** l'outil est marqué absent ou trop ancien avec sa raison, sans exception visible
**Et** chaque résultat est émis en `diagnostic_check`, avec les textes « Que faire ? » de `content/diagnostic.yaml`

### Story 1.5 : Consulter la page Diagnostic et savoir quoi régler

En tant que Camille, sur un poste professionnel derrière un proxy,
je veux une page qui montre chaque outil, sa version et quoi faire s'il manque,
afin de régler mon poste seule.

**Type :** dev

**AD à respecter :** AD-16 (scénarios indisponibles calculés par `diagnostic`), AD-2 (textes écrits par le serveur), AD-17, conventions (Ton, Textes affichés) · **Exigences :** FR-19, UJ-2, UX-DR11, UX-DR30, UX-DR37

**Critères d'acceptation :**

**Étant donné** un premier lancement
**Quand** l'application s'ouvre
**Alors** elle affiche d'office la page Diagnostic
**Et** les lancements suivants ouvrent l'accueil (l'en-tête seul ici, puis la première version du catalogue à partir de la Story 2.3), et le diagnostic reste accessible depuis l'en-tête

**Étant donné** une recherche en cours
**Quand** les sondes avancent
**Alors** chaque outil affiche « En cours », puis son état en mots et avec une icône (✓ OK, ⚠ Trop ancien, ✗ Absent)
**Et** aucun outil n'est dit absent avant la fin
**Et** une synthèse en `role="status"` résume l'état final : « Recherche terminée : n outils sur m demandent une action… »

**Étant donné** le tableau
**Quand** il s'affiche
**Alors** il est groupé par jalon, avec les colonnes Outil | Usage | Version trouvée | Version requise | État | Que faire ? | Scénarios indisponibles, sous des en-têtes `th`
**Et** « Que faire ? » se déplie et donne les commandes en code
**Et** la colonne Scénarios indisponibles vient de `diagnostic` (0 tant qu'aucun scénario n'est déclaré)

**Étant donné** un outil requis absent ou trop ancien
**Quand** l'en-tête s'affiche
**Alors** le `diagnostic-badge` compte ces outils et se lit « Diagnostic, n outils absents ou trop anciens »
**Et** il disparaît quand tout est OK

**Étant donné** git absent
**Quand** la page s'affiche
**Alors** un `notice-card` d'erreur donne la cause et l'action, et « Continuer vers le catalogue » reste proposé

**Étant donné** un proxy détecté
**Quand** la section Proxy s'affiche
**Alors** elle montre « Proxy détecté », l'état de `NO_PROXY` et celui des certificats, chacun avec son « Que faire ? »
**Et** « Relancer le diagnostic » relance toutes les sondes
**Et** le même diagnostic s'écrit dans la console de lancement

### Story 1.6 : Installer l'application sous Windows sans droits administrateur

En tant que Camille, sous Windows 10 ou 11 et sans droits administrateur,
je veux installer l'application en collant une seule commande PowerShell,
afin d'arriver sur le diagnostic en moins de 10 minutes, même derrière un proxy.

**Type :** dev

**AD à respecter :** AD-15, AD-16, AD-3 (clone avec `-c core.autocrlf=false`), AD-20 (`install.json` versionné, mise à jour par le même installeur) · **Exigences :** FR-18 (v0.1), NFR-5, NFR-8, UJ-2, AR-16

**Critères d'acceptation :**

**Étant donné** un compte Windows standard
**Quand** Camille colle la commande unique d'installation dans PowerShell
**Alors** `install.ps1` installe uv dans son profil, récupère l'application (clone avec `-c core.autocrlf=false`, ou zip) et lance `uv sync`
**Et** il écrit `<data>/install.json` : `schema_version`, horodatage, versions installées, durée de l'installation
**Et** aucune étape ne demande d'élévation

**Étant donné** un poste sans git, ou avec un git antérieur à 2.38
**Quand** l'installeur provisionne git
**Alors** il extrait PortableGit 2.56.0.windows.2 de Git for Windows (`-y -gm2 -InstallPath=<data>/tools/git`), d'après `tools.toml`
**Et** un git du poste suffisant est gardé tel quel

**Étant donné** `HTTPS_PROXY` posée
**Quand** l'installeur télécharge
**Alors** il passe par le proxy et pose `UV_SYSTEM_CERTS=true`

**Étant donné** un téléchargement en échec
**Quand** l'installeur s'arrête
**Alors** il dit en français la cause, les variables à régler et la voie clone ou zip
**Et** relancé, il reprend sans casser une installation partielle

**Étant donné** une installation existante
**Quand** on relance l'installeur
**Alors** il met l'application à jour et conserve `progress.json`

### Story 1.7 : Installer l'application sous macOS et Linux sans droits administrateur

En tant qu'apprenant sous macOS ou Linux, sans droits administrateur,
je veux installer l'application par une commande shell unique,
afin d'avoir la même expérience que sous Windows.

**Type :** dev

**AD à respecter :** AD-15, AD-16, AD-3, AD-20 · **Exigences :** FR-18 (v0.1), NFR-5, AR-16

**Critères d'acceptation :**

**Étant donné** un compte standard
**Quand** l'apprenant lance la commande unique `install.sh`
**Alors** le script, en `sh` POSIX, fait les mêmes étapes que `install.ps1` : uv dans le profil, récupération, `uv sync`, `install.json`

**Étant donné** un poste sans git suffisant
**Quand** le script provisionne git
**Alors** il installe pixi 0.82.0 dans le profil, puis lance `pixi global install git` (conda-forge, git 2.56.0)
**Et** sous macOS, il n'appelle jamais `/usr/bin/git` sans avoir testé `xcode-select -p`

**Étant donné** un proxy, ou un échec de téléchargement
**Quand** le script s'exécute
**Alors** il applique les règles de la Story 1.6 : proxy respecté, `UV_SYSTEM_CERTS`, message en français, voie clone ou zip, reprise sans casse

**Étant donné** la CI
**Quand** le job d'installation tourne (`install.sh` sur `macos-latest` et `ubuntu-latest`, `install.ps1` sur `windows-latest`)
**Alors** l'installation aboutit sur un runner neuf, et sa durée est relevée dans le journal du job

## Epic 2 : Taper du vrai git dans un bac à sable et voir l'effet

L'apprenant ouvre un bac à sable préparé par YAML. Il tape git et des commandes de fichiers, et édite dans la vue Code ou dans son éditeur. Le graphe, l'index et le terminal se mettent à jour dans l'ordre de FR-4, et les correspondances relient les vues. La Story 2.1 vérifie en premier le risque le moins visible du projet : des SHA identiques sur les trois systèmes.

### Story 2.1 : Préparer un bac à sable déterministe à partir d'un YAML

En tant qu'Anaël, auteur de scénarios,
je veux décrire l'état initial d'un bac à sable dans un YAML et obtenir les mêmes SHA sous Windows, macOS et Linux,
afin que chaque scénario soit rejouable et que son empreinte serve de référence en CI.

**Type :** dev

**AD à respecter :** AD-3 (contexte interne, environnement hermétique, déterminisme du setup), AD-5 (disposition de l'espace), AD-6 (empreinte canonique), AD-7 (schéma pydantic, registre d'ops, alias), AD-12 (`procs`), AD-13 (contrôle 4), AD-18 · **Exigences :** NFR-2, NFR-3, NFR-5, NFR-10, FR-14 (base), AR-4, AR-6, AR-8, AR-19

**Critères d'acceptation :**

**Étant donné** un fichier `content/scenarios/<scenario_id>.<mode>.yaml`
**Quand** `scenarios` le charge
**Alors** un modèle pydantic avec `schema_version` le valide : `scenario_id`, mode, parcours servis, outils requis, gabarit de départ, `setup`, étapes (liste vide admise)
**Et** un YAML invalide donne une erreur en français qui nomme le champ et la ligne

**Étant donné** le registre d'ops de setup
**Quand** on l'inspecte
**Alors** il contient, une op par module dans `scenarios/ops/` avec le modèle de ses arguments : `write_file`, `commit`, `branch`, `switch`, `push`
**Et** une op peut porter `as: <alias>`, résolu en `element_id` par le contexte du scénario

**Étant donné** un scénario d'essai « bac à sable libre » (deux commits sur `main`, poussés vers `origin`)
**Quand** son setup s'exécute
**Alors** l'espace `<data>/workspaces/<parcours>/<scenario_id>.<mode>/` contient `repo/`, `origin.git/` (bare, remote `origin`), `hooks/` et `run.json`
**Et** git y est lancé par `gitio` seul, en contexte interne (`LC_ALL=C`), avec tout l'environnement d'AD-3 : `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=<data>/gitconfig`, réglages forcés par `GIT_CONFIG_COUNT`, `GIT_TERMINAL_PROMPT=0`, entrée standard fermée, variables de proxy retirées
**Et** les ops fixent `GIT_AUTHOR_DATE`, `GIT_COMMITTER_DATE`, les noms et les e-mails, et écrivent les fichiers en LF par `wsfs`

**Étant donné** un espace préparé
**Quand** on calcule son empreinte canonique
**Alors** c'est le sha256 d'une sérialisation triée de ces éléments : refs et cibles de `repo/` et `origin.git/` (HEAD compris), objets accessibles depuis les refs et le reflog, entrées de l'index, contenu de l'arbre suivi ou non ignoré, stash, `hooks/`
**Et** les dates de fichier, les fichiers ignorés, `ci/` et `cache/` en sont exclus

**Étant donné** la CI
**Quand** le job des empreintes tourne sur les trois OS, et sous Windows aussi sur un clone fait avec `core.autocrlf=true`
**Alors** l'empreinte de chaque scénario égale celle de `content/fingerprints.json`
**Et** un script de maintenance régénère ce fichier
**Et** sous Linux, la suite de scénarios tourne aussi dans un espace de noms sans réseau (`unshare -n`), selon le contrôle (4) d'AD-13

### Story 2.2 : Faire passer chaque action par la file d'opérations de l'espace

En tant qu'apprenant,
je veux que chaque action sur mon bac à sable s'exécute dans l'ordre et me revienne en direct,
afin de ne jamais voir un état incohérent ni une explication avant l'effet.

**Type :** dev

**AD à respecter :** AD-1 (un seul écrivain, états, ordre fixe, epoch), AD-17 (enveloppe, catalogue de `kind`, intentions, SSE, reprise), AD-5, AD-20 (`run.json` versionné), conventions (Erreurs) · **Exigences :** FR-4 (ordre), NFR-7, AR-2, AR-18, AR-22

**Critères d'acceptation :**

**Étant donné** un espace ouvert
**Quand** deux intentions arrivent en même temps
**Alors** la file les exécute en série, et l'état `engine_state{state, reason_text}` passe par `idle`, `command` ou `setup`
**Et** une intention refusée renvoie un 409 avec `reason_text` en français

**Étant donné** une opération
**Quand** elle s'exécute
**Alors** ses événements sortent sous l'enveloppe `{boot_id, seq, ts, workspace_id, epoch, op_id, kind, payload}` dans l'ordre fixe : `op_started`, sortie, `op_exit`, `state_projected`, puis (si une étape existe) `step_verdict` et `step_explanation`
**Et** un test vérifie qu'aucun module ne publie une explication hors de cette séquence

**Étant donné** une opération produite hors de la file (changement externe, résultat de job)
**Quand** son `epoch` n'est plus le courant
**Alors** la file la rejette

**Étant donné** le flux SSE `GET /api/ws/<id>/events`
**Quand** le navigateur se reconnecte avec `Last-Event-ID`
**Alors** il reçoit les événements manqués depuis le tampon circulaire de `Settings.event_buffer` (1 000)
**Et** si `boot_id` diffère ou si `seq` est sorti du tampon, il reçoit `resync_required` et refait `GET /api/ws/<id>/state`

**Étant donné** plus de `Settings.max_active_workspaces` (3) espaces ouverts
**Quand** un quatrième s'ouvre
**Alors** le moins récent s'endort (file, surveillant et runs arrêtés), puis se rouvre à la demande

**Étant donné** une exception métier dans une opération
**Quand** elle remonte
**Alors** elle devient un `app_error{cause_text, action_text}`, sans trace Python montrée à l'apprenant

### Story 2.3 : Afficher la disposition principale et gérer les volets

En tant qu'apprenant,
je veux voir côte à côte le panneau Scénario, le Dépôt local, le Distant, le Code et le Terminal, et pouvoir masquer, agrandir ou élargir une vue,
afin d'adapter l'écran à ce que je fais sans perdre l'état de vue.

**Type :** dev

**AD à respecter :** convention Front (registre des volets avec les types d'`element_id` émis), AD-2 (le front mémorise seulement la disposition), AD-17 (magasin de projection alimenté par le flux) · **Exigences :** NFR-10, FR-32 (vue ajoutable sans refonte), UX-DR5, UX-DR6, UX-DR7, UX-DR35 (vues vides, chargement), UX-DR36, UX-DR38, UX-DR39

**Critères d'acceptation :**

**Étant donné** l'accueil
**Quand** l'apprenant lance l'application après le premier passage
**Alors** une première version du catalogue affiche la section « Socle git », qui liste les scénarios déclarés dans `content/scenarios/` avec leur titre et leurs modes
**Et** un clic sur un mode ouvre son espace de travail, dans le parcours sans IA par défaut
**Et** la Story 6.1 étend ce même écran (choix du parcours, états, cartes indisponibles) sans le remplacer

**Étant donné** un écran de 1920×1080
**Quand** l'espace de travail s'ouvre
**Alors** le panneau Scénario fait 440 px. Les vues suivent les proportions de l'UX : rangée haute à 40 % (Dépôt local 55 %, Distant + PR 45 %), Code à 33 %, Terminal à 27 %.
**Et** chaque vue a son `pane-step`, son titre, le sous-titre fixé par l'UX, un en-tête fixe et un défilement interne
**Et** pendant la préparation, « Préparation du bac à sable… » s'affiche, et chaque vue montre son état vide titré (textes de l'UX), jamais un spinner muet

**Étant donné** une vue
**Quand** l'apprenant clique « — », une puce « + Nom », ⛶, ou déplace une poignée (à la souris, ou au clavier par pas de 16 px)
**Alors** la vue se masque, se réaffiche, s'agrandit (Échap revient) ou change de taille, avec au moins une vue visible de 240×160 px au moins
**Et** le focus suit les règles de l'UX (puce après « — », titre après réaffichage), et les poignées ont `role="separator"` et leurs valeurs
**Et** la configuration survit au changement de scénario et au rechargement

**Étant donné** le registre des volets
**Quand** une story ajoute une vue
**Alors** elle s'enregistre avec les types d'`element_id` qu'elle émet, sans toucher à la disposition
**Et** un test refuse un type émis qui n'est pas déclaré

**Étant donné** la navigation au clavier
**Quand** l'apprenant tape Tab ou F6
**Alors** Tab suit l'ordre de lecture et saute les vues masquées, chaque vue étant un seul arrêt, et les flèches déplacent le focus dans la vue
**Et** F6 passe d'une zone à la suivante, et Échap ferme dans l'ordre fixé par l'UX

**Étant donné** une fenêtre plus petite que 1920×1080, sous 1280 px, ou à 400 % de zoom
**Quand** l'espace s'affiche
**Alors** le repli de l'UX s'applique : masquage par puces dans l'ordre fixé, puis panneau avec une vue agrandie, puis une colonne
**Et** seuls le graphe, le diff et le terminal défilent dans les deux sens

### Story 2.4 : Taper de vraies commandes git dans le terminal

En tant qu'apprenant,
je veux taper des commandes git et voir leur vraie sortie, en français quand git le peut,
afin d'apprendre git tel qu'il est, sans peur de casser autre chose que le bac à sable.

**Type :** dev

**AD à respecter :** AD-3 (contexte apprenant, éditeur `:`), AD-4 (pas de shell, découpeur POSIX, liste blanche git, fichier unique de listes), AD-12 (`procs.spawn`, `terminate_tree`, `index.lock`), AD-1, AD-17 (`terminal_output`), AD-2 (sortie jamais analysée) · **Exigences :** FR-1, FR-2 (refus), NFR-2, NFR-7, UX-DR13, UX-DR37, AR-5, AR-13

**Critères d'acceptation :**

**Étant donné** la vue Terminal
**Quand** l'apprenant tape `git status` puis Entrée
**Alors** git s'exécute dans `repo/`, en contexte apprenant (`LANG`, `LC_ALL` et `LANGUAGE=fr` si la locale existe)
**Et** stdout et stderr s'affichent au fil de l'eau, verbatim, dans l'ordre d'arrivée
**Et** stderr porte `terminal-stderr` (jamais rouge), le code de sortie non nul ajoute `terminal-exit-error`, et une sortie en anglais porte `lang="en"`

**Étant donné** `git push`, `git pull` ou `git fetch`
**Quand** l'apprenant les lance réseau coupé
**Alors** ils agissent sur `origin`, et un dépôt cible qui n'est pas un remote existant (chemin ou URL) est refusé

**Étant donné** une ligne avec `|`, `&&`, `||`, `;`, `$(…)`, des backquotes, `$VAR`, `<`, une redirection hors `echo`, une sous-commande ou une option hors de `content/terminal-allowlist.yaml`, ou une option interdite (`-c`, `-C`, `--git-dir`, `--work-tree`, `--exec`, `-i`, `--output`, `--no-index`, `--upload-pack`, `-F`…)
**Quand** l'apprenant la valide
**Alors** elle est refusée par `terminal-refused` (`role="alert"`), avec le texte de l'UX qui cite la liste acceptée, tirée du même fichier
**Et** `cd` est refusé avec son explication, et le répertoire courant reste la racine du bac à sable

**Étant donné** `git commit` ou `git tag -a` sans message
**Quand** git échoue
**Alors** sa sortie reste intacte, suivie du `terminal-app-message` « git attend un message de commit. Ajoutez `-m "…"`. »
**Et** `git revert`, `git merge --continue`, `git rebase --continue` et `git commit --amend` aboutissent sans éditeur

**Étant donné** une commande en cours
**Quand** plus d'une seconde passe, ou que l'apprenant tape Ctrl+C, ou que le délai de 30 s est dépassé
**Alors** « En cours… n s » s'affiche hors région live, la saisie est inactive, et Ctrl+C ou le dépassement appellent `procs.terminate_tree`
**Et** `gitio` supprime un `index.lock` périmé, puis l'opération se termine par la relecture de l'état prévue par la file

**Étant donné** le terminal
**Quand** l'apprenant utilise ↑ ou ↓, Ctrl+L, Tab ou Échap
**Alors** l'historique de la session défile, l'affichage s'efface (pas l'historique), le focus sort, ou revient au titre de la vue
**Et** au-delà de 5 000 lignes, les plus anciennes sont masquées avec leur nombre

### Story 2.5 : Utiliser les commandes de fichiers, confinées au bac à sable

En tant qu'apprenant,
je veux créer, lire, déplacer et supprimer des fichiers depuis le terminal,
afin de préparer mes commits sans quitter l'application et sans risque pour mon poste.

**Type :** dev

**AD à respecter :** AD-4 (commandes de fichiers en Python, globs résolus dans le bac à sable, modèle de menace), `wsfs` (seul résolveur, UTF-8 sans BOM, LF), AD-18 (tests de confinement sur les trois OS) · **Exigences :** FR-2, NFR-5, AR-5

**Critères d'acceptation :**

**Étant donné** le terminal
**Quand** l'apprenant tape `ls [-a]`, `cat`, `echo … > f` ou `echo … >> f`, `touch`, `mkdir [-p]`, `rm [-r] [-f]`, `mv`, `cp`, `pwd` ou `clear`
**Alors** la commande s'exécute en Python sur `wsfs`, avec le même comportement sous Windows, macOS et Linux
**Et** `rm`, `mv` et `cp` acceptent `*` et `?`, résolus dans le bac à sable ; aucune autre commande ne développe de glob

**Étant donné** un chemin qui sort du bac à sable (`..`, chemin absolu, lien symbolique sortant) ou qui vise `.git/`
**Quand** une commande de fichier, la vue Code ou « Ouvrir dans mon éditeur » le reçoit
**Alors** `wsfs` le refuse avec une explication en français

**Étant donné** une écriture
**Quand** `wsfs` écrit
**Alors** le fichier est en UTF-8 sans BOM, en LF (`\r\n` normalisé en `\n`)

**Étant donné** la CI sur les trois OS
**Quand** la suite de confinement tourne
**Alors** elle couvre traversées, chemins absolus, liens symboliques, lecteurs Windows, noms réservés Windows et `.git/`, et aucun fichier hors du bac à sable n'est lu ni écrit

### Story 2.6 : Calculer l'état du dépôt et un graphe stable côté serveur

En tant qu'apprenant,
je veux un graphe qui reflète exactement `git log --all` et `git status`, et où un commit ne bouge pas sans raison,
afin de croire ce que je vois.

**Type :** dev

**AD à respecter :** AD-2 (`RepoState`, placement déterministe, grammaire `element_id`, annotations, `spans`), AD-3 (contexte interne, plumbing), AD-17 (`state_projected`, schémas versionnés en ajout seulement) · **Exigences :** FR-4, NFR-2, NFR-13, AR-3

**Critères d'acceptation :**

**Étant donné** une opération terminée
**Quand** `projections` relit l'état
**Alors** il construit un `RepoState` à partir de `for-each-ref`, `rev-list`, `cat-file`, `status --porcelain=v2 -z`, `ls-files -s -z`, `stash list` et `reflog`
**Et** ce `RepoState` contient les commits accessibles, les commits perdus encore dans le reflog, les refs locales et de `origin`, les tags, l'index, l'arbre de travail et le stash

**Étant donné** la grammaire `element_id` de `contracts`
**Quand** on génère puis on analyse chaque forme d'AD-2, avec des segments contenant `:`, `%`, des espaces et de l'Unicode
**Alors** l'aller-retour est exact

**Étant donné** une suite d'états (commit, branche, merge, reset, rebase)
**Quand** le placement du graphe est recalculé
**Alors** un commit garde sa colonne et son rang tant que ses refs et ses parents accessibles n'ont pas changé, et un test le vérifie

**Étant donné** la projection
**Quand** elle est publiée
**Alors** chaque nœud porte `new`, `lost`, `a11y_name_text` (gabarit de l'UX) et `explain_ref` ; `announce_text` résume les changements
**Et** chaque ligne de `terminal_output` porte `lang` et des `spans` (SHA, ref, chemin) résolus contre le `RepoState` : seuls les éléments existants sont liables
**Et** l'invite du terminal (`terminal-prompt`) montre la branche courante, ou « HEAD détachée », lue dans le `RepoState`

**Étant donné** des tests de conformité
**Quand** ils comparent la projection à `git log --all` et `git status` après chaque commande d'un scénario d'essai
**Alors** ils sont identiques

### Story 2.7 : Voir le graphe, la liste des commits et l'index

En tant qu'apprenant,
je veux voir dans la vue Dépôt local le graphe des commits, ses branches, HEAD et l'index,
afin de comprendre en un coup d'œil ce que ma commande vient de faire.

**Type :** dev

**AD à respecter :** AD-2 (le front dessine sans calculer), AD-13 (rendu SVG vendorisé ou natif, sans CDN), convention Front · **Exigences :** FR-4, NFR-13, UX-DR14, UX-DR15, UX-DR16, UX-DR7, UX-DR37

**Critères d'acceptation :**

**Étant donné** un `state_projected`
**Quand** la vue se met à jour
**Alors** le graphe dessine en SVG les commits, les arêtes, HEAD (ou « HEAD détachée »), les branches locales (pilule et icône poste), les refs `origin/…` (double bord et icône serveur) et les tags (encoche), selon les formes de DESIGN.md
**Et** un commit perdu est en tirets avec « perdu · visible par reflog », et la marque `new-mark` « Nouveau » apparaît sur ce que la dernière commande a créé ou déplacé

**Étant donné** un nœud
**Quand** un lecteur d'écran le lit
**Alors** il annonce le `a11y_name_text` du serveur, et la zone de clic couvre le disque, le SHA et le message (24 px au moins)

**Étant donné** le bouton « Liste » / « Graphe »
**Quand** l'apprenant bascule
**Alors** `commit-list` montre le tableau SHA, message, auteur, parents, refs, état, dans l'ordre de `git log --all --graph`, avec la même sélection

**Étant donné** des fichiers indexés, modifiés ou non suivis
**Quand** l'index s'affiche
**Alors** `staging-index` les groupe en « Indexé », « Modifié, non indexé » et « Non suivi », avec la lettre d'état git en code
**Et** un clic sélectionne sans rien indexer

**Étant donné** la région `role="status"` unique
**Quand** une commande se termine
**Alors** elle annonce dans l'ordre de FR-4 : « Commande terminée. Vues mises à jour : … »

### Story 2.8 : Éditer un fichier dans la vue Code et lire un diff

En tant qu'apprenant,
je veux ouvrir un fichier, le modifier, l'enregistrer, et voir le diff d'un commit ou de mon arbre de travail,
afin de préparer un changement sans quitter l'application.

**Type :** dev

**AD à respecter :** AD-1 (`save_file` avec `base_hash`), AD-4 (`wsfs`), AD-17 (`save_file`, `open_external`), AD-13 (composant d'édition vendorisé, choisi ici et consigné), AD-2 (diff projeté avec ses `element_id`) · **Exigences :** FR-3, FR-4, UX-DR17, UX-DR18

**Critères d'acceptation :**

**Étant donné** l'arbre de fichiers de la vue Code
**Quand** l'apprenant ouvre un fichier, le modifie puis tape Ctrl+S ou clique Enregistrer
**Alors** l'intention `save_file{path, content, base_hash}` passe par la file, et `git status` voit le changement
**Et** un fichier modifié mais pas encore enregistré porte un point plein et « non enregistré »

**Étant donné** un `base_hash` qui ne correspond plus au disque
**Quand** l'apprenant enregistre
**Alors** l'enregistrement est refusé, et l'éditeur propose « Garder ma version » ou « Recharger »

**Étant donné** « Ouvrir dans mon éditeur »
**Quand** l'apprenant clique
**Alors** `open_external{path}` ouvre le fichier, résolu par `wsfs`, dans l'éditeur par défaut du système

**Étant donné** la sélection d'un commit ou de l'arbre de travail
**Quand** la vue Code affiche le diff
**Alors** chaque `diff-file-header` et chaque ligne (ajoutée sur `accent-soft` avec « + », supprimée sur `danger-soft` avec « − ») ont leur `element_id`, sont focalisables, et font 24 px de haut
**Et** les marqueurs de conflit sont visibles et éditables

**Étant donné** le choix du composant d'édition
**Quand** la story est livrée
**Alors** le composant est vendorisé dans `static/`, sans build à l'exécution, et le choix est consigné dans le spine (section Deferred levée)

### Story 2.9 : Voir les vues suivre une modification faite hors de l'application

En tant qu'apprenant qui préfère son éditeur habituel,
je veux que les vues se mettent à jour seules quand j'enregistre un fichier ailleurs,
afin de travailler comme d'habitude sans perdre la synchronisation.

**Type :** dev

**AD à respecter :** AD-1 (surveillant suspendu pendant `command` et `setup`, délai de silence, filtre par empreinte, opération « changement externe »), AD-6 (empreinte), AD-17 (`external_change`) · **Exigences :** FR-3, UX-DR17, décision « délais chiffrés »

**Critères d'acceptation :**

**Étant donné** un fichier modifié dans un éditeur externe
**Quand** il est enregistré
**Alors** les vues sont à jour en 2 s au plus, après 300 ms de silence du surveillant, et `external-change-notice` affiche « Modifié hors de l'application »

**Étant donné** une commande en cours ou un setup
**Quand** des fichiers changent sous `repo/`
**Alors** le surveillant est suspendu et ne crée aucune opération ; il reprend après le délai de silence

**Étant donné** un changement sous `.git/` seulement, ou une empreinte identique à celle de la dernière projection
**Quand** le surveillant se réveille
**Alors** aucune opération « changement externe » n'est créée

**Étant donné** l'éditeur avec des changements non enregistrés sur ce fichier
**Quand** le disque change
**Alors** l'éditeur dit « Le fichier a changé sur le disque. » avec « Garder ma version » et « Recharger »

### Story 2.10 : Suivre un élément d'une vue à l'autre et lire son explication

En tant qu'apprenant,
je veux qu'un commit, un fichier ou une ligne que je survole ou sélectionne s'éclaire dans toutes les vues, avec une explication courte,
afin de relier ce que je tape, ce que je vois et ce que cela veut dire.

**Type :** dev

**AD à respecter :** AD-2 (`links` et `explain_ref` portés par la projection, `spans` du terminal), AD-7 (`content/explanations.yaml`), convention Textes affichés · **Exigences :** FR-5, NFR-13, UX-DR7, UX-DR24, UX-DR25, UX-DR37

**Critères d'acceptation :**

**Étant donné** un élément survolé ou focalisé
**Quand** ses `links` sont projetés
**Alors** ses correspondants prennent l'état lié dans chaque vue (table de correspondances de l'UX), et les autres estompent leurs décors sans toucher l'opacité du texte
**Et** dans le terminal, les lignes liées prennent `terminal-lit` et les autres passent en texte secondaire

**Étant donné** un clic, Entrée ou Espace sur un élément
**Quand** la sélection se pose
**Alors** elle est unique et persistante, avec le contour encre et la marque ●, et un nouveau clic l'efface

**Étant donné** un correspondant dans une vue masquée ou hors de la zone visible
**Quand** l'apprenant clique
**Alors** la puce devient « + Nom · lié » et réaffiche la vue avec l'élément en évidence, ou la vue défile jusqu'à lui ; jamais au survol

**Étant donné** l'élément qui a le focus
**Quand** un lecteur d'écran le lit
**Alors** le résumé « n éléments liés : … » lui est relié par `aria-describedby`, et « Voir les éléments liés » ouvre la liste

**Étant donné** le « i » d'un élément (commit, ref, fichier, sortie)
**Quand** l'apprenant le clique, ou tape Entrée ou Espace
**Alors** un `explain-popover` de deux ou trois phrases s'ouvre, tiré de `content/explanations.yaml` par `explain_ref`
**Et** Échap le ferme et rend le focus au « i » ; il ne s'ouvre jamais au seul survol

### Story 2.11 : Préparer les gabarits d'exercice des deux parcours

En tant qu'apprenant,
je veux un petit projet Python réaliste dans mon bac à sable, avec ou sans code LLM selon mon parcours,
afin de travailler sur un dépôt qui ressemble au mien.

**Type :** dev

**AD à respecter :** AD-7 (gabarits dans `content/exercise/<parcours>/`, seul le code d'exercice diffère), AD-13 (code LLM avec `httpx` vers une API compatible OpenAI, `llm.toml` local par défaut avec ses endpoints autorisés, tests qui remplacent l'appel réseau), AD-12 (outils verrouillés dans le `uv.lock` du gabarit) · **Exigences :** FR-16, NFR-10

**Critères d'acceptation :**

**Étant donné** `content/exercise/llm/` et `content/exercise/no_ai/`
**Quand** on les inspecte
**Alors** chacun a `pyproject.toml`, `uv.lock`, `tests/`, `.gitignore` et `.pre-commit-config.yaml` ; seul le code d'exercice diffère

**Étant donné** le parcours LLM
**Quand** les scénarios avancent
**Alors** le code d'exercice suit les stades appel simple → prompt système → outils → boucle, chacun posé par une op de setup (`exercise_stage`)
**Et** `llm.toml` vise par défaut `http://127.0.0.1:11434/v1` et déclare les endpoints autorisés

**Étant donné** les tests du gabarit LLM
**Quand** ils tournent
**Alors** ils remplacent l'appel réseau, et passent hors ligne

## Epic 3 : Collaborer dans un GitHub simulé

L'apprenant pousse vers `origin`, ouvre une PR, reçoit la revue du collègue simulé, puis merge. Il récupère aussi le commit d'un collègue. Dès cet epic, le modèle de PR porte les checks, les approbations et une vraie protection de branche, même si aucun scénario de v0.1 ne les active.

### Story 3.1 : Tenir un modèle de PR complet, prêt pour les stations

En tant qu'Anaël, auteur de scénarios,
je veux un modèle de PR qui porte dès v0.1 les checks, les approbations et la protection de branche,
afin d'ajouter les stations en v0.2 sans refondre le GitHub simulé.

**Type :** dev

**AD à respecter :** AD-8 (un seul écrivain, modèle de PR, checks liés au SHA, `mergeable` et raisons de blocage), AD-7 (ops `open_pr`, `set_protection`), AD-20 (`schema_version`, migrations), AD-6 (`github.json` dans l'empreinte, sérialisation canonique) · **Exigences :** FR-8, NFR-10, AR-9

**Critères d'acceptation :**

**Étant donné** un espace
**Quand** `github_sim` écrit `github.json`
**Alors** l'écriture est atomique, faite depuis une opération de la file, et `github_sim` est le seul module qui écrit ce fichier
**Et** le fichier porte `schema_version`, et les PR sont numérotées à partir de 1 par espace

**Étant donné** le modèle de PR
**Quand** on l'inspecte
**Alors** une PR porte numéro, tête, base, état, `head_sha`, `base_sha`, checks, revues et approbations, approbations requises, et règles de protection de la base
**Et** un check porte `job_id`, `head_sha`, `base_sha`, un état `queued|running|success|failure|error`, le drapeau obligatoire, la sortie et les constats

**Étant donné** une PR ouverte
**Quand** son `head_sha` ou son `base_sha` change
**Alors** ses checks repassent à `queued` dans la même écriture
**Et** après tout changement des refs de `origin`, `mergeable` est recalculé pour toutes les PR ouvertes

**Étant donné** un scénario de test qui déclare un check obligatoire en échec
**Quand** on calcule `mergeable`
**Alors** la PR n'est pas mergeable, sans modification du modèle
**Et** chaque raison de blocage (check, approbations, conflit) porte son texte et son `element_id`

### Story 3.2 : Ouvrir une PR et la merger

En tant qu'apprenant,
je veux ouvrir une PR depuis une branche que j'ai poussée, puis la merger,
afin de vivre le cycle de collaboration de GitHub sans compte et sans réseau.

**Type :** dev

**AD à respecter :** AD-8 (merge sans worktree par `merge-tree --write-tree`, `commit-tree` et `update-ref` avec l'ancienne valeur attendue), AD-1 (intentions `pr_open` et `pr_merge` dans la file), AD-17 (`pr_updated`), AD-2 · **Exigences :** FR-6, FR-4

**Critères d'acceptation :**

**Étant donné** une branche poussée sur `origin`
**Quand** l'apprenant envoie `pr_open`
**Alors** une PR vers `main` est créée, avec `head_sha` et `base_sha` courants, et `pr_updated` est émis

**Étant donné** une branche absente de `origin`
**Quand** l'apprenant tente d'ouvrir une PR
**Alors** l'intention est refusée par un 409 qui dit en français de pousser d'abord la branche

**Étant donné** une PR mergeable
**Quand** l'apprenant envoie `pr_merge`
**Alors** `github_sim` écrit le merge dans `origin.git`, avec un message et une identité fixes, sans passer par `receive-pack`
**Et** après un `git fetch`, le graphe montre `origin/main` à jour

**Étant donné** une PR en conflit avec `main`
**Quand** `mergeable` est calculé
**Alors** la raison « conflit » est listée, et le merge est refusé

**Étant donné** `main` qui a bougé sur `origin` entre le calcul et le merge
**Quand** `update-ref` voit une ancienne valeur différente
**Alors** le merge échoue proprement, `mergeable` est recalculé, et l'apprenant en est informé

### Story 3.3 : Voir le distant et les PR dans la vue Distant + PR

En tant qu'apprenant,
je veux voir les refs de `origin`, mes PR, leurs checks, le journal de revue et ce qui bloque le merge,
afin de savoir où en est mon travail côté serveur.

**Type :** dev

**AD à respecter :** AD-2 (raisons de blocage et liens projetés), convention Front (registre des volets) · **Exigences :** FR-4, FR-6, FR-8, UX-DR19, UX-DR35 (vue vide), UX-DR40

**Critères d'acceptation :**

**Étant donné** la vue Distant + PR
**Quand** elle s'affiche
**Alors** elle liste, dans l'ordre de l'UX : refs de `origin`, PR courante, checks en échec, `merge-blocked`, checks réussis, journal de revue
**Et** sans PR, elle affiche « Aucune PR. Poussez une branche, puis ouvrez une PR. »

**Étant donné** une branche poussée sans PR
**Quand** la vue l'affiche
**Alors** elle propose « Ouvrir une PR »

**Étant donné** une `pr-card`
**Quand** elle s'affiche
**Alors** elle montre son titre, « feature → main » en code, ses checks, son `review-log` (compteur « Approbations : n sur m ») et le bouton Merger
**Et** Merger n'est actif que si la PR est mergeable ; sinon `merge-blocked` donne une raison par ligne, liée à son élément

**Étant donné** des checks dans les cinq états du modèle (de test en v0.1)
**Quand** ils s'affichent
**Alors** chacun a son glyphe, son état en mots, sa durée, l'étiquette « Obligatoire » s'il l'est, et le fond de DESIGN.md ; seul « En cours » est animé

### Story 3.4 : Recevoir la revue et les commits d'un collègue simulé

En tant qu'apprenant,
je veux qu'un collègue simulé relise ma PR et pousse ses propres commits,
afin de m'exercer à récupérer le travail d'un autre et à attendre une approbation.

**Type :** dev

**AD à respecter :** AD-8 (réactions déclarées par le scénario, déclenchées par les événements de PR), AD-7 (op `colleague_commit`, identité et dates fixes), AD-3 (déterminisme) · **Exigences :** FR-6, FR-7, UX-DR14 (badge Collègue), décision « approbations déclarées, automatiques quand les checks sont verts »

**Critères d'acceptation :**

**Étant donné** un scénario qui déclare `colleague_commit` sur `origin`
**Quand** l'apprenant tape `git pull`
**Alors** le commit arrive dans le graphe local avec le badge « Collègue »
**Et** son SHA est identique sur les trois OS (empreinte de référence)

**Étant donné** une réaction déclarée « à l'ouverture de la PR : commentaire, puis approbation »
**Quand** l'apprenant ouvre la PR
**Alors** les entrées arrivent dans le `review-log`, dans l'ordre, avec auteur et heure, et le compteur d'approbations se met à jour

**Étant donné** une réaction « quand les checks sont verts : approbation »
**Quand** tous les checks obligatoires passent à `success`
**Alors** l'approbation arrive, sans action de l'apprenant

### Story 3.5 : Protéger une branche pour de vrai par un hook pre-receive

En tant qu'apprenant,
je veux qu'un push direct sur une branche protégée soit refusé par git lui-même,
afin de voir une vraie protection et pas une interdiction de l'application.

**Type :** dev

**AD à respecter :** AD-8 (protection réelle par `pre-receive`, le merge de `github_sim` ne passe pas par `receive-pack`), AD-9 (hook `#!/bin/sh` d'une ligne généré par `install_hooks`, en LF, un seul `hooks/` par espace, distinction par `GIT_DIR`, `hooks_enabled` dans `run.json`) · **Exigences :** FR-8, FR-22 (mécanisme), NFR-5

**Critères d'acceptation :**

**Étant donné** l'op `install_hooks`
**Quand** le setup la joue
**Alors** chaque hook est un script `#!/bin/sh` d'une ligne en LF, `exec "<python de l'app>" -m wavedevsecops.hooks <nom> "$@"`, avec des chemins posix entre guillemets
**Et** aucun hook n'utilise bash, et aucun n'est copié depuis le dépôt de l'application

**Étant donné** `main` protégée par le scénario de test
**Quand** l'apprenant tape `git push origin main`
**Alors** le hook `pre-receive` refuse la mise à jour et écrit son refus en français sur stderr ; git l'affiche avec `remote:`
**Et** le terminal ajoute « Refusé par la protection de `main` : tout passe par une PR. »

**Étant donné** le même dossier `hooks/`
**Quand** git l'appelle depuis `repo/`
**Alors** le point d'entrée ne fait rien de `pre-receive` ; il n'agit que dans `origin.git/`

**Étant donné** la CI sur les trois OS
**Quand** le test du hook tourne
**Alors** le refus fonctionne sous Windows (sh de PortableGit), macOS et Linux

## Epic 4 : Suivre un scénario guidé avec quiz réels et indices

Chaque étape donne sa consigne, se valide sur l'état réel, puis s'explique. Une mauvaise commande de quiz s'exécute pour de vrai, puis l'état est rétabli. Les indices s'ouvrent par paliers. « Recommencer » existe, et le bilan affiche le score du premier coup. Le premier passage fait foi.

### Story 4.1 : Valider une étape sur l'état réel du dépôt

En tant qu'apprenant,
je veux qu'une étape soit validée parce que le dépôt est dans le bon état, quelle que soit la commande tapée,
afin d'apprendre git plutôt qu'une formule.

**Type :** dev

**AD à respecter :** AD-7 (registre de types d'étape, `check(state, ctx) -> Verdict`, `step_id`, verdict `unexpected`, lint de contenu), AD-1 (validation puis explication dans l'ordre fixe), AD-2 · **Exigences :** FR-11, FR-14, NFR-7, NFR-10, UX-DR8, UX-DR11, UX-DR37

**Critères d'acceptation :**

**Étant donné** le registre `scenarios/steps/`
**Quand** on l'inspecte
**Alors** chaque type a son module, son modèle pydantic et `check(state: RepoState, ctx) -> Verdict` ; le premier type, `repo_state`, exprime des conditions sur les refs, les commits, l'index, l'arbre et le stash
**Et** ajouter un type de test ne modifie ni le moteur ni les scénarios existants

**Étant donné** une étape qui attend une branche `feature` portant HEAD
**Quand** l'apprenant tape `git switch -c feature` ou `git checkout -b feature`
**Alors** les deux sont validées, et `step_verdict` puis `step_explanation` sont émis après `state_projected`

**Étant donné** un état ni attendu ni prévu
**Quand** l'étape le vérifie
**Alors** le verdict est `unexpected`, et le panneau affiche le `notice-card` « État inattendu » : ce qui était attendu, ce que l'étape voit (avec liens), une explication, puis l'action « Continuer »
**Et** rien n'est bloqué ; les actions « Recommencer » et « Ouvrir un indice » s'ajoutent à cet encart avec leurs stories

**Étant donné** le panneau Scénario
**Quand** une étape est en cours
**Alors** il montre, de haut en bas : le titre, `mode-badge` avec son « i », `step-progress` (« Étape n sur N », segments terminés cliquables qui rouvrent leur consigne), la consigne, puis `step-explanation` une fois la vue à jour

**Étant donné** la CI
**Quand** le lint de contenu tourne
**Alors** il charge tous les YAML et vérifie les ops, les types d'étape, les outils, les clés d'explication, les alias et l'unicité des `step_id`

### Story 4.2 : Enregistrer les faits du premier passage

En tant qu'apprenant,
je veux que ma progression soit enregistrée de façon sûre, même si l'application s'arrête brutalement,
afin de ne perdre aucun résultat et de ne jamais voir un score compté deux fois.

**Type :** dev

**AD à respecter :** AD-14 (écrivain unique, faits en ajout seulement, clé d'idempotence `(workspace_id, epoch, op_id)`, `run.json` d'abord, rejeu au démarrage, états dérivés), AD-20 (migrations) · **Exigences :** FR-20, FR-16 (progression par parcours), AR-15

**Critères d'acceptation :**

**Étant donné** une étape validée, un premier essai de quiz, un indice ouvert ou un scénario terminé
**Quand** le moteur soumet le fait
**Alors** `progress` l'ajoute à `progress.json`, sous un verrou unique et par écriture atomique, par parcours et par `(scenario_id, mode, step_id)`

**Étant donné** un fait déjà enregistré avec la même clé d'idempotence
**Quand** il est soumis de nouveau
**Alors** il est ignoré

**Étant donné** un arrêt brutal entre l'écriture de `run.json` et celle des faits
**Quand** l'application redémarre
**Alors** le moteur soumet les faits manquants, sans doublon

**Étant donné** les faits d'un scénario
**Quand** `progress` dérive les états
**Alors** il calcule « À faire », « En cours » ou « Terminé », le score du premier coup et le nombre d'indices
**Et** un fait du premier passage n'est jamais remplacé, et l'événement `progress_updated` est émis

### Story 4.3 : Prendre des instantanés et rétablir un état exact

En tant qu'apprenant,
je veux que l'application puisse remettre mon bac à sable exactement dans un état antérieur,
afin de pouvoir me tromper sans rester coincé sur un état faux.

**Type :** dev

**AD à respecter :** AD-6 (copie de `repo/`, `origin.git/`, `github.json` et `hooks/`, instantané 0, rétention, procédure de restauration, trois essais sous Windows, `restore_failed`, reprise au démarrage), AD-1 (états `restoring`, `epoch` incrémenté, surveillant suspendu), AD-12 (`index.lock`) · **Exigences :** FR-15, FR-10, NFR-7, AR-7

**Critères d'acceptation :**

**Étant donné** la fin d'un setup
**Quand** le moteur prend l'instantané 0
**Alors** `snapshots/0/` contient les copies et leur empreinte, avant tout run du pipeline

**Étant donné** une demande de restauration
**Quand** le moteur restaure l'instantané n
**Alors** il incrémente `epoch`, arrête les runs et vide `ci/`, suspend le surveillant, écrit `restoring{snapshot_id, phase}` dans `run.json`, renomme les dossiers courants vers une corbeille, copie l'instantané, puis compare l'empreinte
**Et** l'état `restore_ended{status: ok}` est émis, et les éléments revenus portent la marque `restored`

**Étant donné** un verrou de fichier sous Windows
**Quand** un renommage échoue
**Alors** le moteur réessaie trois fois, à intervalles espacés, puis passe en `restore_failed`

**Étant donné** un arrêt pendant `restoring`
**Quand** l'application redémarre
**Alors** le moteur reprend la copie ou passe en `restore_failed`

**Étant donné** plus de `Settings.max_snapshots` (20) instantanés
**Quand** un nouveau est pris
**Alors** les plus anciens sont supprimés, sauf le 0 et le dernier

### Story 4.4 : Recommencer un scénario sans perdre son score

En tant qu'apprenant,
je veux remettre un scénario à zéro quand je le souhaite,
afin de réessayer sans crainte, sachant que mon premier passage reste la mesure.

**Type :** dev

**AD à respecter :** AD-6 (Recommencer restaure l'instantané 0, sinon reconstruit par le setup et compare à l'empreinte de référence), AD-14 (remise à zéro consignée après succès), AD-20 (`content_hash` du scénario) · **Exigences :** FR-10, UX-DR40

**Critères d'acceptation :**

**Étant donné** « Recommencer » dans le pied du panneau
**Quand** l'apprenant clique
**Alors** une confirmation en ligne demande « Remettre le scénario à son état initial ? Votre score du premier coup est conservé. »
**Et** après accord, l'espace a l'empreinte de l'instantané 0, le panneau revient à l'étape 1 et dit « Scénario remis à zéro. »

**Étant donné** le `notice-card` « État inattendu » de la Story 4.1
**Quand** il s'affiche
**Alors** il propose aussi « Recommencer »

**Étant donné** un instantané 0 absent ou une restauration qui échoue
**Quand** Recommencer s'exécute
**Alors** l'espace est supprimé, reconstruit par son setup, et son empreinte comparée à celle de `content/fingerprints.json`
**Et** si cela échoue aussi, l'erreur s'affiche avec « Voir le diagnostic »

**Étant donné** une remise à zéro réussie
**Quand** `progress` l'enregistre
**Alors** le fait « remise à zéro » est ajouté, et le score du premier coup ainsi que le compte d'indices restent ceux du premier passage

**Étant donné** un espace dont le `content_hash` du scénario a changé de façon incompatible
**Quand** l'apprenant le rouvre
**Alors** un encart propose « Recommencer », au lieu d'une reprise silencieuse

### Story 4.5 : Exécuter une mauvaise commande de quiz, puis rétablir l'état

En tant qu'apprenant,
je veux qu'une mauvaise réponse de quiz s'exécute pour de vrai, que je voie son effet, puis que l'état revienne,
afin d'apprendre par l'erreur sans rien casser.

**Type :** dev

**AD à respecter :** AD-1 (état `quiz_altered`, écritures de la vue Code refusées), AD-4 (commandes de lecture seulement en `quiz_altered`), AD-6 (instantané avant chaque choix), AD-14 (premier essai), AD-17 (`quiz_choice`, `restore_state`, `quiz_altered`) · **Exigences :** FR-15, SM-C1, UX-DR9, UX-DR10, UX-DR11, UX-DR37

**Critères d'acceptation :**

**Étant donné** une étape de type `quiz` avec ses commandes proposées
**Quand** l'apprenant choisit une commande et clique « Exécuter ma réponse »
**Alors** un instantané est pris, puis la commande s'exécute dans le terminal comme si elle était tapée
**Et** le bouton reste inactif tant que rien n'est coché, et dit « Choisissez une commande. »

**Étant donné** une bonne réponse
**Quand** elle s'exécute
**Alors** l'état produit reste, aucun bandeau ne s'affiche, et l'étape continue

**Étant donné** une mauvaise réponse
**Quand** elle s'exécute
**Alors** l'espace passe en `quiz_altered` ; les vues restent sur l'état modifié ; le `quiz-banner` affiche « État modifié par le quiz — <commande> » et prend le focus ; le panneau affiche l'explication
**Et** le terminal accepte seulement les commandes de lecture, et refuse les autres par « Refusée pendant l'état modifié par le quiz… » ; la vue Code refuse les écritures

**Étant donné** « J'ai compris, rétablir l'état »
**Quand** l'apprenant clique
**Alors** « Rétablissement de l'état… » s'affiche, les vues sont `inert`, puis les éléments revenus portent « Rétabli » et le focus revient au panneau
**Et** après le rétablissement, l'état a la même empreinte qu'avant le choix

**Étant donné** un rétablissement qui échoue
**Quand** le moteur passe en `restore_failed`
**Alors** le `notice-card` d'erreur dit « L'état n'a pas pu être rétabli. Pour ne pas vous laisser sur un état faux, recommencez le scénario. Votre score du premier coup est conservé. », annoncé en `role="alert"`, avec la seule action « Recommencer »

**Étant donné** un quiz rejoué après une erreur
**Quand** l'apprenant rechoisit
**Alors** seul le premier essai est enregistré pour le score

### Story 4.6 : Ouvrir des indices par paliers

En tant qu'apprenant,
je veux une piste, puis une commande partielle, puis la solution, sans pénalité,
afin d'oser demander de l'aide sans sauter la réflexion.

**Type :** dev

**AD à respecter :** AD-2 (disponibilité d'un indice et sa raison calculées par le serveur), AD-7 (trois paliers par étape), AD-14 (palier, temps avant la demande, temps de lecture), AD-17 (`hint_open{tier}`, `hint_opened`) · **Exigences :** FR-13, UX-DR28, décision « délais chiffrés » (solution après un essai ou 20 s sur la commande partielle)

**Critères d'acceptation :**

**Étant donné** `hint-tabs` (Piste | Commande partielle | Solution) en `role="tablist"`
**Quand** l'apprenant ouvre un palier
**Alors** il ne peut l'ouvrir qu'après le précédent ; un onglet verrouillé montre un cadenas et sa condition en clair, porte `aria-disabled="true"`, et reste focalisable

**Étant donné** l'onglet Solution
**Quand** aucun essai n'a eu lieu (commande tapée ou choix validé pendant l'étape) et que moins de 20 s ont passé sur la commande partielle
**Alors** il reste verrouillé avec « Disponible après un essai ou un moment de lecture. », sans décompte
**Et** à son déblocage, « La solution est disponible. » est annoncé

**Étant donné** un palier ouvert
**Quand** `progress` enregistre le fait
**Alors** le fait porte le palier, le temps avant la demande et le temps de lecture avant l'action suivante
**Et** rouvrir un palier déjà ouvert ne compte pas une seconde fois

**Étant donné** le `notice-card` « État inattendu » de la Story 4.1
**Quand** il s'affiche
**Alors** il propose aussi « Ouvrir un indice », qui ouvre le premier palier non encore ouvert

**Étant donné** l'étape en cours
**Quand** des indices ont été ouverts
**Alors** aucun compteur ne s'affiche ; la commande partielle montre des blancs, et la solution est un texte sélectionnable, sans bouton Copier ni Exécuter

### Story 4.7 : Lire le bilan à la fin d'un scénario

En tant qu'apprenant,
je veux voir à la fin mon score du premier coup et le nombre d'indices,
afin de savoir où j'en suis et de choisir la suite.

**Type :** dev

**AD à respecter :** AD-14 (score dérivé par `progress`), AD-2 (le front n'invente pas le texte) · **Exigences :** FR-20, UX-DR12, Voice and Tone (gabarit du score)

**Critères d'acceptation :**

**Étant donné** la dernière étape validée
**Quand** le scénario se termine
**Alors** le panneau affiche le `score-summary` au gabarit « n sur m du premier coup · k indice(s) », avec l'accord « 0 indice », « 1 indice », « 2 indices »
**Et** il propose « Scénario suivant », « Catalogue » et « Recommencer », et les vues restent consultables

**Étant donné** un redémarrage de l'application
**Quand** l'apprenant rouvre un scénario terminé
**Alors** son bilan est identique, lu dans `progress.json`

## Epic 5 : Comprendre ce que l'agent a fait (mode B)

Un agent scénarisé a déjà agi sur le dépôt, avec des erreurs réalistes. L'apprenant désigne dans les vues l'élément en cause, en un seul essai, et reçoit une correction faite contre le vrai dépôt. La désignation est générique : l'entretien RSSI de l'Epic 11 la reprend avec une case « Preuve ».

### Story 5.1 : Rejouer les actes de l'agent B de façon déterministe

En tant qu'Anaël, auteur de scénarios,
je veux décrire en YAML ce qu'a fait l'agent, erreurs comprises,
afin d'obtenir le même dépôt à chaque rejeu, sur les trois systèmes.

**Type :** dev

**AD à respecter :** AD-7 (ops `agent_commit`, `agent_push_force`, `stash`, et une op de rebase laissé en conflit, avec identité et dates fixes ; aucun vrai LLM), AD-3 (déterminisme), AD-18 (empreintes de référence) · **Exigences :** FR-12, NFR-3, UX-DR14 (badge Agent)

**Critères d'acceptation :**

**Étant donné** les ops `agent_commit`, `agent_push_force`, `stash` et `agent_rebase_conflict`
**Quand** un setup les joue
**Alors** chaque acte a l'identité « Agent » et des dates fixes, et le dépôt obtenu a l'empreinte de référence sur les trois OS

**Étant donné** un commit de l'agent
**Quand** le graphe l'affiche
**Alors** il porte le badge « Agent » (`primary-soft`), jamais en rouge

**Étant donné** un scénario B rejoué deux fois
**Quand** on compare les empreintes
**Alors** elles sont identiques

### Story 5.2 : Corriger une désignation côté serveur, en un seul essai

En tant qu'apprenant,
je veux que ma réponse à « qu'a fait l'agent ? » soit corrigée contre le vrai dépôt,
afin que mon explication repose sur ce qui s'est réellement passé.

**Type :** dev

**AD à respecter :** AD-2 (marque `designable`, correction par le serveur contre le `RepoState` courant), AD-7 (ensemble de bonnes réponses en alias, élément principal et équivalents), AD-14 (premier essai), AD-17 (`answer_submit{slots}`, `GET …/resolve_sha?prefix=`, `answer_corrected`) · **Exigences :** FR-12, SM-4

**Critères d'acceptation :**

**Étant donné** une étape de type `designate`
**Quand** le YAML la déclare
**Alors** elle porte la question, les types acceptés, une liste de cases (`slots`) et, pour chaque case, son ensemble de bonnes réponses en alias, avec un élément principal
**Et** la projection marque `designable` tous les éléments des types acceptés, pas seulement les bonnes réponses

**Étant donné** `GET /api/ws/<id>/resolve_sha?prefix=a3f9d21`
**Quand** le préfixe a 7 caractères au moins et désigne un seul commit du bac à sable
**Alors** le serveur renvoie l'aperçu (SHA court, message, auteur), sans consommer l'essai
**Et** un préfixe inconnu ou ambigu renvoie une réponse claire en français

**Étant donné** `answer_submit{slots: [element_id]}`
**Quand** l'apprenant valide pour la première fois
**Alors** le serveur corrige, émet `answer_corrected` avec les marques (choix juste ou faux, attendu, équivalents) et enregistre le premier essai
**Et** une seconde soumission sur la même étape est refusée par un 409

### Story 5.3 : Désigner un élément dans les vues

En tant que Camille,
je veux montrer du doigt, dans le graphe ou le diff, le commit ou la ligne en cause,
afin de prouver que j'ai compris ce que l'agent a fait.

**Type :** dev

**AD à respecter :** AD-2 (seuls les éléments `designable` projetés sont proposés), convention Front · **Exigences :** FR-12, UX-DR26, UX-DR7, UX-DR36, décision « le mode reste armé jusqu'à la validation ou Échap »

**Critères d'acceptation :**

**Étant donné** la question et « Désigner dans les vues »
**Quand** l'apprenant arme le mode
**Alors** les désignables sont entourés de tirets, le curseur système passe en `crosshair`, le bouton dit « Désignation active · Échap pour quitter » avec `aria-pressed="true"`, et le changement est annoncé

**Étant donné** le mode armé
**Quand** l'apprenant clique un désignable, ou tape Entrée dessus (nœud du graphe, en-tête de fichier, ligne de diff, ligne du terminal)
**Alors** l'élément se place dans `answer-slot` ; un autre choix le remplace, et ✕ vide la case
**Et** l'élément choisi montre le contour de sélection à la place des tirets

**Étant donné** Échap
**Quand** l'apprenant le tape
**Alors** le mode se désarme sans vider la case, et le focus revient à `designate-button`

**Étant donné** le mode armé
**Quand** l'apprenant tape Tab
**Alors** il atteint toujours ✕, le champ SHA et « Valider ma réponse », sous lequel figure le texte relié « 1 seul essai »

**Étant donné** le mode désarmé
**Quand** l'apprenant clique un élément
**Alors** le clic ne sert qu'aux correspondances

### Story 5.4 : Choisir dans une liste ou par SHA

En tant qu'apprenant qui navigue au clavier ou connaît le SHA,
je veux choisir l'élément dans une liste filtrable ou en tapant son SHA,
afin de répondre sans viser à la souris.

**Type :** dev

**AD à respecter :** AD-2, AD-17 (`resolve_sha`) · **Exigences :** FR-12, UX-DR26, UX-DR37

**Critères d'acceptation :**

**Étant donné** « Choisir dans la liste ▾ »
**Quand** l'apprenant l'ouvre
**Alors** `designate-list` montre les désignables groupés par vue, avec icône de type et SHA court, dans une liste de 240 px au plus qui défile en interne
**Et** le champ « Filtrer par nom, SHA ou chemin » filtre au clavier, et l'élément choisi porte « choisi »

**Étant donné** le champ « Ou saisir un SHA »
**Quand** l'apprenant tape 7 caractères au moins qui résolvent un commit
**Alors** l'aperçu « `a3f9d21` · Add config · Agent » s'affiche en `role="status"`, et l'élément peut aller dans la case

**Étant donné** un SHA inconnu
**Quand** l'apprenant le tape
**Alors** le champ passe en `aria-invalid`, dit « Aucun commit ne correspond à ce SHA dans le bac à sable. » en `role="alert"`, et l'essai n'est pas consommé

### Story 5.5 : Lire la correction dans les vues et dans le panneau

En tant que Camille,
je veux voir mon choix, l'élément attendu et les équivalents marqués dans les vues, avec l'explication,
afin de comprendre, que j'aie juste ou non.

**Type :** dev

**AD à respecter :** AD-2 (marques portées par la projection), AD-1 (correction puis explication dans l'ordre fixe) · **Exigences :** FR-12, UX-DR26, UX-DR8 (variante correction)

**Critères d'acceptation :**

**Étant donné** une réponse validée
**Quand** `answer_corrected` arrive
**Alors** le choix porte « ✓ Votre choix » ou « ✗ Votre choix » (tirets `danger`), l'élément principal « ✓ Attendu » et les équivalents « ≡ Accepté aussi », à droite de leur rangée
**Et** la préséance verdict > sélection > désignable > lié s'applique

**Étant donné** le panneau
**Quand** la correction s'affiche
**Alors** `step-explanation` (variante correction) liste l'attendu et les équivalents, chacun avec « voir dans les vues », que la réponse soit juste ou non
**Et** la case devient « Votre réponse · validée », sans ✕, et le panneau propose « Continuer » et « Recommencer »

**Étant donné** l'étape suivante
**Quand** l'apprenant continue
**Alors** les marques de verdict disparaissent

### Story 5.6 : Le scénario B « `.env` committé »

En tant que Camille,
je veux découvrir qu'un agent a committé un fichier de secrets, le désigner, le retirer de l'historique, puis savoir quelles barrières l'auraient bloqué,
afin de savoir réparer et expliquer cet incident.

**Type :** dev

**AD à respecter :** AD-7 (scénario déclaratif, ensemble de bonnes réponses : commit, fichier `.env` dans ce commit, ligne `API_KEY=` du diff, SHA), AD-18 (empreinte de référence) · **Exigences :** FR-12, UJ-2, UX-DR8 (variante « Ce qui l'aurait bloqué »)

**Critères d'acceptation :**

**Étant donné** le scénario « add / commit », mode B, dans chaque parcours
**Quand** il s'ouvre
**Alors** le graphe montre deux commits de l'agent, dont l'un ajoute `.env`

**Étant donné** la question « Qu'a fait l'agent ? »
**Quand** Camille désigne la ligne `API_KEY=…`, le fichier `.env` de ce commit, le commit ou son SHA
**Alors** chacun est accepté, et le commit est l'élément principal

**Étant donné** l'étape de réparation
**Quand** aucune ref ne rend plus accessible un commit qui contient `.env`, et que `.env` est ignoré par `.gitignore`
**Alors** l'étape est validée, quelle que soit la suite de commandes utilisée

**Étant donné** la fin du scénario
**Quand** l'encart « Ce qui l'aurait bloqué » s'affiche
**Alors** il liste gitleaks (Station 1 · Poste local, secrets scanning) avec l'étiquette en tirets « Arrive en v0.2 » tant que la station n'est pas livrée, d'après la déclaration des jalons côté serveur (livré par la story 5.9 : ce critère décrit le résultat attendu, 5.9 porte le travail)

### Story 5.7 : Le scénario B « `push --force` qui écrase un collègue »

En tant qu'apprenant,
je veux découvrir qu'un agent a écrasé sur `origin` le travail d'un collègue, désigner ce qui a disparu, puis le restaurer,
afin de savoir défaire un `push --force`.

**Type :** dev

**AD à respecter :** AD-7, AD-8 (`origin` et protection), AD-2 (commits perdus encore dans le reflog projetés) · **Exigences :** FR-12

**Critères d'acceptation :**

**Étant donné** le scénario « push / pull », mode B, dans chaque parcours
**Quand** il s'ouvre
**Alors** le commit du collègue n'est plus sur `origin/main`, mais il reste visible en local, en tirets « perdu · visible par reflog »

**Étant donné** la question
**Quand** l'apprenant désigne le commit du collègue écrasé (élément principal) ou le commit forcé de l'agent (équivalent déclaré)
**Alors** la correction suit l'ensemble déclaré

**Étant donné** l'étape de réparation
**Quand** `origin/main` contient de nouveau le commit du collègue et le travail de l'agent à garder
**Alors** l'étape est validée

### Story 5.8 : Les scénarios B « stash oublié » et « rebase laissé en conflit »

En tant qu'apprenant,
je veux retrouver un stash que l'agent a oublié, et sortir d'un rebase que l'agent a laissé en conflit,
afin de savoir finir le travail inachevé d'un agent.

**Type :** dev

**AD à respecter :** AD-7, AD-4 (`rebase --continue` et `--abort` sans éditeur), AD-3 · **Exigences :** FR-12 · **Ligne de coupe v0.1 :** élément 2

**Critères d'acceptation :**

**Étant donné** le scénario « stash », mode B
**Quand** il s'ouvre
**Alors** un stash de l'agent existe et `git stash list` le montre ; l'apprenant le désigne, puis l'applique et le committe ; l'étape est validée sur l'état réel

**Étant donné** le scénario « rebase », mode B
**Quand** il s'ouvre
**Alors** le dépôt est au milieu d'un rebase en conflit ; l'apprenant désigne le commit en conflit, puis résout dans la vue Code et termine par `git rebase --continue`, ou annule par `git rebase --abort`, selon l'étape

**Étant donné** les deux scénarios
**Quand** la CI compare leurs setups
**Alors** les empreintes de référence sont identiques sur les trois OS

### Story 5.9 : Encart « Ce qui l'aurait bloqué » dans les scénarios B

En tant qu'apprenant,
je veux, à la fin d'un scénario B, voir quelles barrières auraient bloqué l'erreur de l'agent,
afin de relier chaque incident à la barrière DevSecOps qui l'aurait évité.

**Type :** dev

**AD à respecter :** AD-7 (champ du schéma de scénario, lint de contenu), AD-17 (`step_explanation`), AD-2 (projection), convention Textes affichés · **Exigences :** FR-12, UX-DR8 (variante « Ce qui l'aurait bloqué ») · **Arbitrage :** la contradiction entre les stories 5.1 (qui ne prévoit pas l'encart) et 9.3 (qui retire l'étiquette « Arrive en v0.2 ») est tranchée : cette story livre l'encart, 9.3 ne fait que retirer l'étiquette et lier le scénario

**Critères d'acceptation :**

**Étant donné** le schéma d'un scénario B
**Quand** un auteur déclare, pour la fin du scénario, une liste de barrières qui l'auraient bloqué (barrière, station, nom du scénario qui la joue)
**Alors** le schéma pydantic l'accepte, le lint de contenu refuse une barrière inconnue de `content/barriers.yaml`, et un scénario sans cette liste reste valide

**Étant donné** les scénarios B « `.env` committé », « `push --force` », « stash oublié » et « rebase laissé en conflit »
**Quand** leurs déclarations sont écrites
**Alors** chacun nomme ses barrières : gitleaks (Station 1 · Poste local, secrets scanning) pour `.env`, la protection de branche pour `push --force`, et ce que le contenu de chaque scénario justifie pour les deux autres, sans barrière inventée

**Étant donné** une barrière dont la station n'est pas livrée, d'après la déclaration des jalons côté serveur
**Quand** l'encart s'affiche à la fin du scénario
**Alors** il liste la barrière avec l'étiquette en tirets « Arrive en v0.2 », sans lien

**Étant donné** une barrière dont la station est livrée
**Quand** l'encart s'affiche
**Alors** l'étiquette n'apparaît pas et le nom du scénario de la barrière est un lien

**Étant donné** le panneau du scénario
**Quand** le scénario B se termine
**Alors** le rendu `step-explanation` de la variante « Ce qui l'aurait bloqué » s'affiche après la correction, en français, sans toucher au score

## Epic 6 : Parcourir le socle git complet dans les deux parcours

Le catalogue présente les scénarios dans l'ordre conseillé, avec le choix du parcours. Les 8 scénarios du mode A sont écrits pour les deux gabarits d'exercice. « Reprendre », l'export du rapport et l'exécution facultative du code LLM complètent le jalon. L'epic se termine par la release v0.1.0 et le test avec deux collègues.

### Story 6.1 : Choisir son parcours et parcourir le catalogue

En tant qu'apprenant,
je veux choisir mon parcours, voir les scénarios dans l'ordre conseillé avec leur état, et ouvrir celui que je veux,
afin d'avancer à mon rythme.

**Type :** dev

**AD à respecter :** AD-14 (états dérivés par `progress`), AD-16 (indisponibilité calculée par `diagnostic`), AD-5 (un espace par parcours, scénario et mode), AD-2 · **Exigences :** FR-9, FR-16, UX-DR29, UX-DR4 (`path-menu`)

Cette story étend la première version du catalogue posée par la Story 2.3.

**Critères d'acceptation :**

**Étant donné** un premier passage, sans parcours choisi
**Quand** le catalogue s'ouvre
**Alors** il n'affiche que `path-picker`, avec la question « Choisissez votre parcours. Les deux suivent la même progression ; seul le code d'exercice change. » et une phrase par option

**Étant donné** un parcours choisi
**Quand** le catalogue s'affiche
**Alors** la section « Socle git » montre les 8 scénarios dans l'ordre de FR-9, avec un disque numéroté, une colonne Mode A et, s'il existe, une colonne Mode B ; les sections des jalons non livrés n'apparaissent pas
**Et** chaque colonne affiche « À faire », « En cours » ou « Terminé », avec « n sur m du premier coup · k indice(s) »

**Étant donné** un outil requis absent
**Quand** une carte en dépend
**Alors** elle affiche « ⊘ Indisponible » et « Nécessite <outil> · Voir le diagnostic », et ne s'ouvre pas

**Étant donné** `path-menu` dans l'en-tête
**Quand** l'apprenant change de parcours depuis un scénario
**Alors** il revient au catalogue du nouveau parcours, le scénario quitté reste à son étape dans l'ancien, et chaque parcours garde sa progression

**Étant donné** une carte
**Quand** l'apprenant l'ouvre, quel que soit l'ordre
**Alors** le scénario prépare son propre état initial, sans dépendre des précédents

### Story 6.2 : Les scénarios A « add / commit », « push / pull », « branche » et « PR / merge »

En tant qu'apprenant,
je veux les quatre premiers scénarios du socle git, avec leurs quiz,
afin d'apprendre à committer, partager, brancher et passer par une PR.

**Type :** dev

**AD à respecter :** AD-7 (scénarios déclaratifs, trois indices par étape, explications en français), AD-8 (PR et collègue), AD-18 (empreintes de référence) · **Exigences :** FR-9, FR-11, FR-15, FR-16, UJ-1, SM-C1

**Critères d'acceptation :**

**Étant donné** chacun des quatre scénarios, dans les deux parcours
**Quand** le lint de contenu et la CI des empreintes tournent
**Alors** ils passent, et chaque étape a sa consigne, son explication et trois paliers d'indice

**Étant donné** « push / pull »
**Quand** l'apprenant le suit
**Alors** il récupère par `git pull` le commit d'un collègue simulé

**Étant donné** « branche »
**Quand** l'apprenant le suit
**Alors** il crée `feature` et rencontre trois quiz, dont un qui propose `git reset --hard HEAD~1` comme erreur réaliste (Flow 1)

**Étant donné** « PR / merge »
**Quand** l'apprenant le suit
**Alors** il pousse une branche, ouvre une PR, reçoit la revue du collègue, puis merge

**Étant donné** un test de bout en bout par scénario
**Quand** il rejoue la solution de chaque étape
**Alors** chaque étape est validée, et le scénario se termine sans indice

### Story 6.3 : Les scénarios A « conflit », « stash », « rebase » et « récupération »

En tant qu'apprenant,
je veux les quatre derniers scénarios du socle git,
afin de savoir résoudre un conflit, mettre de côté, rebaser et récupérer un commit perdu.

**Type :** dev

**AD à respecter :** AD-7, AD-4 (`merge --continue`, `rebase --continue` sans éditeur), AD-2 (commits perdus projetés), AD-18 · **Exigences :** FR-9, FR-11, FR-15, FR-16, UJ-2, SM-3

**Critères d'acceptation :**

**Étant donné** « conflit »
**Quand** l'apprenant merge deux branches en conflit
**Alors** il résout les marqueurs dans la vue Code, puis termine par `git add` et `git commit` ; l'étape est validée sur l'état réel

**Étant donné** « récupération »
**Quand** l'apprenant a perdu un commit par `reset --hard`
**Alors** il le retrouve par `git reflog` et le restaure ; le commit perdu est affiché en tirets jusqu'à sa restauration

**Étant donné** les quatre scénarios, dans les deux parcours
**Quand** le lint, la CI des empreintes et les tests de bout en bout tournent
**Alors** ils passent

### Story 6.4 : Reprendre le dernier scénario là où on l'a laissé

En tant qu'apprenant qui travaille par séances d'une heure,
je veux reprendre le dernier scénario ouvert à son étape, avec mon bac à sable tel que je l'ai laissé,
afin de ne pas refaire le début.

**Type :** dev

**AD à respecter :** AD-5 (espace conservé), AD-14 (dernier scénario ouvert, disponibilité de « Reprendre » dérivée), AD-6 (empreinte recalculée à la reprise), AD-20 (`content_hash`) · **Exigences :** FR-9, UX-DR29, décision « Reprendre rouvre le bac à sable conservé » · **Ligne de coupe v0.1 :** élément 3 (repli : réouverture à l'étape 1)

**Critères d'acceptation :**

**Étant donné** le dernier scénario ouvert
**Quand** le catalogue s'affiche
**Alors** sa carte montre, dans la colonne du mode en cours, « Étape n sur N » et « Reprendre »

**Étant donné** « Reprendre »
**Quand** l'apprenant clique
**Alors** le scénario se rouvre à cette étape, sur le bac à sable conservé

**Étant donné** un bac à sable disparu ou inutilisable, ou un `content_hash` incompatible
**Quand** l'apprenant reprend
**Alors** un encart dit « Ce scénario ne peut pas reprendre là où vous l'aviez laissé. » et propose « Recommencer »

### Story 6.5 : Exporter mon rapport de progression

En tant qu'apprenant,
je veux exporter moi-même un rapport de ma progression,
afin de le transmettre si je le souhaite, en sachant que rien n'est envoyé.

**Type :** dev

**AD à respecter :** AD-14 (exports produits par `progress`, rendus par Jinja2 : HTML autonome, CSV UTF-8 avec BOM et séparateur `;`), AD-13 (aucune ressource externe dans le HTML), AD-1 (état `exporting`) · **Exigences :** FR-36, NFR-9, UX-DR31, UX-DR11, décision « remises à zéro dans le rapport »

**Critères d'acceptation :**

**Étant donné** « Exporter mon rapport » en pied du catalogue, suivi de « Rien n'est envoyé : vous choisissez à qui transmettre le fichier. »
**Quand** l'apprenant clique
**Alors** `report-preview` liste par parcours : scores, indices, remises à zéro et horodatages (installation, premier lancement), et propose « Exporter en HTML » et « Exporter en CSV »
**Et** sans progression, il dit « Aucun scénario terminé pour l'instant. Le rapport contiendra seulement les dates d'installation et de premier lancement. »

**Étant donné** l'export HTML
**Quand** le fichier est ouvert hors de l'application, réseau coupé
**Alors** il s'affiche en entier (styles et polices en ligne) et s'imprime en PDF depuis le navigateur

**Étant donné** l'export CSV
**Quand** il est ouvert dans un tableur
**Alors** les accents s'affichent correctement (UTF-8 avec BOM, séparateur `;`)

**Étant donné** la fenêtre pywebview
**Quand** l'apprenant exporte
**Alors** la boîte d'enregistrement du système s'ouvre

**Étant donné** un export impossible
**Quand** l'écriture échoue
**Alors** un `notice-card` dit « Le fichier n'a pas pu être enregistré : <cause>. », avec « Réessayer »

### Story 6.6 : Exécuter, en option, le code d'exercice du parcours LLM

En tant qu'apprenant du parcours LLM,
je veux pouvoir lancer moi-même le code d'exercice contre mon LLM,
afin de voir ce qu'il fait, en sachant que c'est la seule action qui peut sortir du poste.

**Type :** dev

**AD à respecter :** AD-13 (seul `llmrun` sort sur le réseau, `python -m <point d'entrée>` dans `cache/venv/`, variables de proxy de l'apprenant rétablies, intention `run_exercise_code{confirmed: true}` seulement, aucune étape ne l'émet), AD-19 (confirmation vérifiée côté serveur), AD-1 (état `command` après un instantané), AD-12 · **Exigences :** FR-17, NFR-1, NFR-9, UX-DR23 · **Ligne de coupe v0.1 :** élément 1

**Critères d'acceptation :**

**Étant donné** le panneau d'un scénario du parcours LLM
**Quand** l'apprenant clique `network-run-button` « Exécuter le code (réseau possible) »
**Alors** une confirmation en ligne demande « Ce code peut appeler un service en ligne. Continuer ? »

**Étant donné** la confirmation
**Quand** l'apprenant accepte
**Alors** un instantané est pris, puis `llmrun` lance le point d'entrée dans `cache/venv/`, avec les variables de proxy de l'apprenant rétablies, et la sortie s'affiche dans le terminal

**Étant donné** une intention `run_exercise_code` sans `confirmed: true` ou sans cookie valide
**Quand** le serveur la reçoit
**Alors** il la refuse

**Étant donné** la CI
**Quand** les contrôles d'AD-13 tournent
**Alors** `llmrun` est le seul module autorisé à importer une bibliothèque réseau, et aucune étape de scénario ne déclare cette intention (lint de contenu)

### Story 6.7 : Publier la release v0.1.0 et la faire tester par deux collègues

En tant qu'Anaël,
je veux publier la v0.1.0 et la faire tester par deux collègues pendant une heure,
afin de valider SM-1 à SM-4 et de faire juger la vue du graphe par d'autres que moi.

**Type :** mixte (publication par l'agent ; SM-1 à SM-4 par Anaël et deux collègues)

**AD à respecter :** AD-18 (version SemVer, tag annoté, release GitHub avec notes, temps d'installation mesuré), AD-13 (énoncé du README) · **Exigences :** NFR-9, NFR-11, SM-1, SM-2, SM-3, SM-4

**Critères d'acceptation :**

**Étant donné** la suite complète verte sur les trois OS
**Quand** Anaël publie
**Alors** `pyproject.toml` porte `0.1.0`, le tag annoté `v0.1.0` existe, et la release GitHub a ses notes
**Et** le dépôt GitHub porte le topic `ai-portfolio`, une description, le topic `status-test`, et une entrée dans `portfolio.json`

**Étant donné** le README
**Quand** on le lit
**Alors** il énonce que l'application n'envoie aucune télémétrie et ne fait aucun appel réseau, sauf l'exécution facultative du code LLM

(humain) **Étant donné** le protocole de `success-metrics.md`
**Quand** Anaël finit les scénarios git sans indice (SM-1), puis deux collègues installent chronomètre en main (SM-2), font branche → PR → conflit → récupération en 1 h au plus (SM-3) et expliquent le mode B (SM-4)
**Alors** les résultats sont consignés dans les notes de release
**Et** un critère vérifié par Anaël seul y est marqué « non validé par un tiers »

## Epic 7 : Voir le poste local et le pipeline simulé bloquer une PR (stations 1 et 2)

Les outils de la chaîne sont installés pour un usage hors ligne. Sur le poste, l'apprenant lance ruff et pytest, et un hook gitleaks protège ses commits. Sur chaque PR, un pipeline simulé lance les vrais outils et affiche un check par outil. La revue obligatoire et la protection de `main` bloquent pour de vrai. Le même pipeline se lit en GitHub Actions, en Jenkins et en GitLab CI.

### Story 7.1 : Provisionner les outils de la chaîne pour un usage hors ligne

En tant qu'apprenant sans droits administrateur,
je veux que l'installation pose gitleaks et tous les paquets dont les stations auront besoin,
afin que les stations fonctionnent ensuite réseau coupé.

**Type :** dev

**AD à respecter :** AD-15 (gitleaks : archive officielle vérifiée par `checksums.txt`, extraite dans `tools/`), AD-12 (préchargement de `uv-cache`, `cache/venv/` par `uv sync --offline --frozen`, environnement hors ligne de `toolrun`, résolution par le registre), AD-16 (outils de la chaîne dans `tools.toml`, versions égales au `uv.lock` du gabarit) · **Exigences :** FR-18 (outils v0.2), FR-19, NFR-1, NFR-4, AR-13, AR-16, AR-17

**Critères d'acceptation :**

**Étant donné** l'installeur sur les trois OS
**Quand** il provisionne la chaîne
**Alors** il télécharge l'archive gitleaks 8.30.1 pour l'OS et l'architecture, vérifie sa somme par `checksums.txt`, puis l'extrait dans `<data>/tools/`
**Et** une somme fausse arrête l'installation de cet outil, avec un message en français

**Étant donné** l'installation
**Quand** elle précharge `<data>/uv-cache`
**Alors** le cache contient l'interpréteur Python géré et chaque version de paquet qu'un état de scénario peut demander, y compris la version corrigée de chaque dépendance vulnérable

**Étant donné** un espace ouvert réseau coupé
**Quand** `toolrun` crée `cache/venv/` par `uv sync --offline --frozen`
**Alors** l'environnement est créé sans accès réseau, avec `UV_OFFLINE=1`, `PIP_NO_INDEX=1`, `NO_PROXY=127.0.0.1,localhost`, les variables de proxy retirées et les caches d'outils dans `cache/`

**Étant donné** `toolrun`
**Quand** il lance un outil
**Alors** il le résout par `tools.toml`, jamais par le PATH du poste

**Étant donné** le diagnostic
**Quand** il s'affiche en v0.2
**Alors** le groupe « Outils de la chaîne (v0.2+) » liste gitleaks, ruff, pytest, pytest-cov, coverage, diff-cover, bandit, pip-audit et pre-commit, avec la version requise
**Et** un écart avec `uv.lock` est signalé « environnement abîmé », avec `uv sync` comme marche à suivre, et les scénarios touchés sont indisponibles

### Story 7.2 : Lancer ruff et pytest dans le terminal (Station 1 · Poste local)

En tant qu'apprenant,
je veux lancer ruff et pytest sur mon dépôt d'exercice et voir leur vraie sortie,
afin de trouver un défaut de lint ou un test cassé avant de committer.

**Type :** dev

**AD à respecter :** AD-4 (outils acceptés seulement si l'étape les déclare), AD-10 (sortie humaine verbatim, liens fichier:ligne tirés d'une exécution machine), AD-12, AD-14 (`evidence_seen`) · **Exigences :** FR-21, UX-DR20, UX-DR13

**Critères d'acceptation :**

**Étant donné** une étape qui déclare `ruff` et `pytest`
**Quand** l'apprenant tape `ruff check .` ou `pytest`
**Alors** l'outil tourne par `toolrun`, et sa sortie humaine s'affiche verbatim dans un bloc `tool-output` désignable, étiqueté au nom de l'outil
**Et** les fichier:ligne du bloc sont des liens vers la vue Code, tirés d'une exécution machine du même outil sur le même arbre

**Étant donné** une étape qui ne déclare pas l'outil
**Quand** l'apprenant le tape
**Alors** la commande est refusée par `terminal-refused`, avec son explication

**Étant donné** les scénarios de station 1 « défaut de lint » et « test cassé », dans les deux parcours
**Quand** l'apprenant lance l'outil
**Alors** le défaut prévu échoue visiblement, l'étape donne son explication, et la correction valide l'étape
**Et** le fait `evidence_seen{barrier_id}` est soumis quand la sortie s'affiche

### Story 7.3 : Être protégé par le hook pre-commit gitleaks

En tant qu'apprenant,
je veux qu'un commit contenant un secret soit refusé avant même d'exister,
afin de voir la première barrière contre les fuites de secrets.

**Type :** dev

**AD à respecter :** AD-9 (hook pre-commit qui lance le vrai `pre-commit run` sur un `.pre-commit-config.yaml` en `repo: local` / `language: system`, `PRE_COMMIT_HOME` dans `cache/`, outil manquant renvoyé vers le diagnostic, `hooks_enabled`), AD-4 (`pre-commit install` refusé), AD-14 (`evidence_seen`) · **Exigences :** FR-21, FR-33 (secrets scanning), UX-DR20, UX-DR37

**Critères d'acceptation :**

**Étant donné** le scénario « secret dans un commit », dans les deux parcours, avec le hook pre-commit actif
**Quand** l'apprenant committe un fichier qui contient une clé
**Alors** `pre-commit run` lance gitleaks (`gitleaks git --pre-commit --staged`), le commit est refusé, et la sortie réelle de gitleaks s'affiche dans `tool-output`
**Et** aucun commit n'apparaît dans le graphe, et le panneau dit « Refusé par le hook pre-commit : gitleaks a trouvé un secret. Le commit n'a pas été créé. », avec un lien vers la ligne, en `role="alert"`

**Étant donné** le même hook
**Quand** l'apprenant retire le secret et recommite
**Alors** le commit passe

**Étant donné** gitleaks absent
**Quand** le hook tourne
**Alors** il sort en échec avec un message en français qui renvoie au diagnostic

**Étant donné** `pre-commit install`
**Quand** l'apprenant le tape
**Alors** la commande est refusée, avec l'explication que les hooks sont posés par le scénario

### Story 7.4 : Faire tourner le pipeline simulé sur chaque PR

En tant qu'apprenant,
je veux qu'à chaque push sur une branche qui a une PR, les vrais outils tournent et affichent un check chacun,
afin de voir la CI travailler comme sur GitHub.

**Type :** dev

**AD à respecter :** AD-10 (`content/pipeline.yaml`, run par `(pr, head_sha, base_sha)` et `epoch`, un run actif par espace, annulation sur un nouveau SHA, `git clone --shared` dans `ci/`, jobs en série, résultats soumis à la file, sortie humaine verbatim et constats machine), AD-8 (checks remis à `queued`, `check_updated`), AD-1, AD-12 (venv de l'espace réutilisé), AD-6 (`ci/` hors instantanés) · **Exigences :** FR-22, NFR-6, UX-DR19, UX-DR20, décision « run complet en 45 s au plus »

**Critères d'acceptation :**

**Étant donné** `content/pipeline.yaml`
**Quand** `ci` le lit
**Alors** chaque job déclare `job_id`, libellé, argv de la sortie humaine, argv de la sortie machine, drapeau obligatoire et sens des codes de sortie (succès, échec, erreur de l'outil) ; les jetons `{osv_url}`, `{base_sha}` et `{repo}` sont remplacés par `ci`
**Et** les jobs de cet epic sont `ruff`, `pytest` et `gitleaks`

**Étant donné** un push sur une branche qui a une PR
**Quand** `head_sha` change
**Alors** les checks passent à `queued`, puis `ci` clone `origin.git` dans `ci/<pr>-<sha7>/` et exécute les jobs en série
**Et** chaque résultat est une opération de la file, qui écrit `github.json` et émet `check_updated`

**Étant donné** l'environnement du run
**Quand** le hash du `uv.lock` du SHA testé égale celui de `cache/venv/`
**Alors** le run réutilise `cache/venv/` ; sinon, il crée son propre environnement par `uv sync --offline --frozen` depuis `uv-cache`
**Et** un test vérifie qu'après la mise à jour d'une dépendance dans `uv.lock`, le check `pytest` voit la nouvelle version

**Étant donné** un run en cours
**Quand** un nouveau SHA arrive sur la même PR, ou qu'un Recommencer incrémente `epoch`
**Alors** le run est annulé par `procs.terminate_tree`, et ses résultats tardifs sont rejetés

**Étant donné** un outil qui sort avec le code « erreur de l'outil »
**Quand** son check s'affiche
**Alors** il porte « ⚠ Erreur de l'outil », distinct d'« Échec », avec « bandit s'est arrêté sans résultat (code 2). Ce n'est pas un défaut de votre code. » et « Relancer le check » (`check_rerun`) ; la PR reste bloquée

**Étant donné** un check
**Quand** l'apprenant clique « Voir la sortie »
**Alors** `tool-output` se déplie avec la sortie humaine verbatim, et la ligne de détail d'un échec donne fichier:ligne en lien

**Étant donné** la durée d'un run
**Quand** il se termine
**Alors** elle est enregistrée en `duration_ms`, et un test mesure le run des jobs de cet epic sur le runner de CI de référence

### Story 7.5 : Voir la revue obligatoire et la protection de `main` bloquer (Station 2 · PR et CI)

En tant qu'apprenant,
je veux voir qu'une PR ne passe ni avec un check obligatoire en échec, ni sans revue, et qu'un push direct sur `main` est refusé,
afin de comprendre les quatre yeux et la protection de branche.

**Type :** dev

**AD à respecter :** AD-8 (`mergeable`, raisons de blocage, `pre-receive`), AD-7 (protection et règles de PR initiales déclarées), AD-14 (`evidence_seen`) · **Exigences :** FR-22, FR-33 (quatre yeux, protection de branche, traçabilité), UX-DR19

**Critères d'acceptation :**

**Étant donné** le scénario « check en échec », dans les deux parcours
**Quand** un check obligatoire échoue
**Alors** `merge-blocked` le liste, et Merger reste inactif avec sa raison

**Étant donné** le scénario « PR sans revue »
**Quand** les checks sont verts mais la revue obligatoire manque
**Alors** `merge-blocked` liste la revue absente, jusqu'à l'approbation du collègue simulé

**Étant donné** le scénario « push direct sur `main` »
**Quand** l'apprenant tape `git push origin main`
**Alors** la sortie réelle du refus s'affiche, suivie de « Refusé par la protection de `main` : tout passe par une PR. »

**Étant donné** chaque barrière qui joue dans ces scénarios
**Quand** sa preuve s'affiche (check, journal de revue, refus)
**Alors** le fait `evidence_seen{barrier_id}` est soumis

### Story 7.6 : Lire le même pipeline en GitHub Actions, Jenkins et GitLab CI

En tant qu'apprenant,
je veux retrouver chaque tâche du pipeline simulé dans les trois écritures du pipeline,
afin de reconnaître la même chaîne sur les outils de mes clients.

**Type :** dev

**AD à respecter :** AD-10 (trois écritures dans le gabarit, jamais exécutées, tâches encadrées par `wds:job <job_id>` et `wds:end`, plages de lignes tirées du SHA de tête, balises absentes donnant un constat non bloquant, test de présence des `job_id`), AD-7 · **Exigences :** FR-23, UX-DR21

**Critères d'acceptation :**

**Étant donné** chaque gabarit
**Quand** on inspecte `.github/workflows/ci.yml`, `Jenkinsfile` et `.gitlab-ci.yml`
**Alors** chaque `job_id` de `content/pipeline.yaml` y est encadré par `wds:job <job_id>` et `wds:end`, et un test le vérifie

**Étant donné** « Voir dans le pipeline » sur un check
**Quand** l'apprenant clique
**Alors** `pipeline-tabs` s'ouvre dans la vue Code (GitHub Actions | Jenkins | GitLab CI), étiqueté « Lecture seule », avec les lignes de la tâche surlignées et « lignes x à y » pour chaque onglet
**Et** changer d'onglet garde la tâche, et survoler un check éclaire ses lignes dans l'onglet ouvert

**Étant donné** une balise absente sur le SHA de tête
**Quand** `ci` calcule les plages
**Alors** il produit un constat non bloquant, jamais une exception

**Étant donné** ces fichiers
**Quand** l'apprenant tente de les exécuter
**Alors** rien ne s'exécute : aucune intention ni commande ne les lance

## Epic 8 : Voir les barrières de sécurité et de qualité jouer (station 3)

Trois barrières bloquent une PR sur un défaut prévu, et chacune explique pourquoi : bandit (SAST), pip-audit avec le SBOM (SCA), et la quality gate. Chaque barrière a un scénario dans chaque parcours. Le parcours LLM ajoute les barrières propres au code LLM.

### Story 8.1 : Bloquer une PR sur du code vulnérable avec bandit (SAST)

En tant qu'apprenant,
je veux que le check bandit échoue sur le code vulnérable prévu, en nommant le fichier, la ligne et la règle,
afin de comprendre ce qu'est un SAST et comment il protège `main`.

**Type :** dev

**AD à respecter :** AD-10 (job `bandit` : sortie humaine verbatim, constats tirés de `bandit -f json`), AD-8, AD-14 (`evidence_seen`) · **Exigences :** FR-24, FR-27 (parcours sans IA), FR-33 (SAST), UX-DR19

**Critères d'acceptation :**

**Étant donné** le job `bandit` ajouté à `content/pipeline.yaml`
**Quand** il tourne sur une PR
**Alors** sa sortie humaine s'affiche verbatim, et ses constats (fichier, ligne, règle) viennent de `bandit -f json`

**Étant donné** le scénario « code vulnérable » du parcours sans IA
**Quand** l'apprenant pousse et ouvre la PR
**Alors** le check bandit passe à « ✗ Échec · Obligatoire », la ligne de détail désigne le fichier, la ligne et la règle, et la PR est bloquée

**Étant donné** le défaut corrigé
**Quand** l'apprenant pousse
**Alors** le check repasse au vert sans autre changement

### Story 8.2 : Servir une base de vulnérabilités locale et figée

En tant qu'apprenant,
je veux que l'analyse des dépendances marche réseau coupé et donne toujours le même résultat,
afin que la barrière SCA soit fiable en atelier.

**Type :** dev

**AD à respecter :** AD-11 (`osv` sert `POST /osv/v1/query` depuis `content/osv/`, extrait daté d'enregistrements OSV réels, sans verrou ni file ; `Settings.osv_url` seule source de l'URL ; script de maintenance), AD-19 (route `/osv/` sans cookie, en POST et en lecture), AD-12 (`toolrun` n'occupe jamais la boucle du serveur) · **Exigences :** FR-25, NFR-1, NFR-3, SM-C2, AR-12

**Critères d'acceptation :**

**Étant donné** `content/osv/`
**Quand** on l'inspecte
**Alors** il contient des enregistrements OSV réels, copiés tels quels, pour les paquets des gabarits, et un fichier qui porte la date de l'extrait

**Étant donné** le serveur lancé
**Quand** pip-audit envoie `POST http://127.0.0.1:<port>/osv/v1/query`
**Alors** `osv` répond depuis l'extrait, sans cookie, sans verrou ni attente de file, pendant qu'un outil tourne
**Et** toute autre méthode sur `/osv/` est refusée

**Étant donné** le script de maintenance
**Quand** Anaël le lance
**Alors** il met à jour l'extrait et sa date ; rien ne se met à jour à l'exécution

### Story 8.3 : Bloquer une PR sur une dépendance vulnérable et lire le SBOM (SCA)

En tant qu'apprenant,
je veux que pip-audit bloque la PR sur la dépendance vulnérable prévue, et pouvoir consulter le SBOM,
afin de comprendre la SCA et de savoir ce que contient mon logiciel.

**Type :** dev

**AD à respecter :** AD-11 (vrai pip-audit avec `--vulnerability-service osv --osv-url {osv_url}`, `--no-deps`, `--disable-pip`, dépendances épinglées ; trois exécutions : humaine, `-f json`, `-f cyclonedx-json` ; date de la base citée), AD-10, AD-14 (`evidence_seen`) · **Exigences :** FR-25, FR-27 (parcours sans IA), FR-33 (SCA, SBOM), UX-DR22, AR-23 (options exactes de pip-audit fixées ici)

**Critères d'acceptation :**

**Étant donné** le job `pip_audit`
**Quand** il tourne
**Alors** il lance trois fois pip-audit sur le même arbre (sortie humaine affichée, `-f json` pour les constats, `-f cyclonedx-json` pour le SBOM), avec des options exactes consignées dans `content/pipeline.yaml` et dans le spine

**Étant donné** le scénario « dépendance vulnérable » du parcours sans IA
**Quand** l'apprenant ouvre la PR
**Alors** le check échoue, désigne la dépendance et sa vulnérabilité, et l'explication cite « base embarquée, figée au <date> »

**Étant donné** « Voir le SBOM »
**Quand** l'apprenant clique, sur le check ou dans l'arbre
**Alors** `sbom-view` montre en lecture seule le composant, la version, la licence et les vulnérabilités, avec la ligne vulnérable marquée ✗ et son identifiant
**Et** chaque ligne est liée à `pyproject.toml` et au check, et désignable

**Étant donné** la dépendance mise à jour vers la version corrigée préchargée
**Quand** l'apprenant pousse, réseau coupé
**Alors** `uv sync --offline` réussit, et le check repasse au vert

### Story 8.4 : Bloquer une PR quand la couverture du nouveau code passe sous 80 %

En tant qu'apprenant,
je veux que la quality gate bloque une PR dont le nouveau code est trop peu testé, en affichant la valeur et le seuil,
afin de comprendre ce qu'est une quality gate.

**Type :** dev

**AD à respecter :** AD-10 (job `quality_gate` : `pytest --cov`, puis `diff-cover` contre `{base_sha}` avec `--fail-under=80`, constats tirés de `coverage json` et de `diff-cover --format json:`), AD-14 (`evidence_seen`) · **Exigences :** FR-26, FR-27 (parcours sans IA), FR-33 (quality gate), NFR-6, décision « run complet en 45 s au plus »

**Critères d'acceptation :**

**Étant donné** le scénario « couverture sous le seuil » du parcours sans IA
**Quand** l'apprenant ouvre la PR
**Alors** le check `quality_gate` échoue, la PR est bloquée, et l'échec affiche la couverture mesurée et le seuil de 80 %

**Étant donné** un test ajouté
**Quand** l'apprenant pousse
**Alors** le check affiche « Couverture du nouveau code n % · seuil 80 % · ✓ »

**Étant donné** le pipeline complet (ruff, pytest, gitleaks, bandit, pip-audit, quality gate)
**Quand** le test de performance tourne en CI
**Alors** il émet une alerte au-delà de 90 s et échoue au-delà de 180 s, sur chacun des trois OS
**Et** la mesure du budget de 45 s se fait sur le poste de référence d'Anaël, avant la release v0.2.0 (Story 9.5)

### Story 8.5 : Le scénario LLM « outil trop puissant » (Flow 4)

En tant que Camille, en atelier d'une heure,
je veux voir une PR du parcours LLM bloquée par bandit, puis par pip-audit, puis par la quality gate, et exiger deux approbations,
afin de vivre la station 3 de bout en bout.

**Type :** dev

**AD à respecter :** AD-7, AD-8 (deux approbations requises, réactions du collègue), AD-10, AD-11 · **Exigences :** FR-24 à FR-28 (parcours LLM), UJ-3, SM-C4

**Critères d'acceptation :**

**Étant donné** le scénario « outil trop puissant » du parcours LLM
**Quand** Camille pousse et ouvre la PR
**Alors** bandit échoue sur l'outil trop puissant donné au LLM, et `merge-blocked` liste « bandit en échec » et « Approbations : 0 sur 2 »

**Étant donné** le défaut bandit corrigé
**Quand** elle pousse
**Alors** bandit passe, puis pip-audit échoue sur la dépendance prévue ; elle consulte le SBOM et met la dépendance à jour

**Étant donné** la quality gate verte et les deux approbations arrivées
**Quand** tout est vert
**Alors** Merger devient actif, et chaque check vert renvoie à ses lignes dans les trois écritures
**Et** ce scénario couvre, pour le parcours LLM, les barrières de FR-24 à FR-26 (FR-27)

### Story 8.6 : La clé d'API en dur, le test de config LLM et l'injection de prompt

En tant qu'apprenant du parcours LLM,
je veux voir bloquer une clé d'API en dur et une config qui enverrait mes données au cloud, et savoir nommer l'injection de prompt,
afin de connaître les risques propres au code LLM.

**Type :** dev

**AD à respecter :** AD-10 (job `gitleaks` du pipeline), AD-13 (`llm.toml` : endpoints autorisés, Ollama local par défaut), AD-7, AD-14 (`evidence_seen`) · **Exigences :** FR-28 · **Ligne de coupe v0.2 :** élément 2 (test de config)

**Critères d'acceptation :**

**Étant donné** le scénario « clé d'API en dur » (station 3, parcours LLM)
**Quand** la clé arrive dans une PR
**Alors** le check gitleaks échoue et bloque la PR

**Étant donné** le scénario « données envoyées au cloud »
**Quand** la config n'est plus locale par défaut, ou qu'un endpoint est hors de la liste autorisée
**Alors** le test du gabarit échoue dans le check `pytest`, et la PR est bloquée ; il repasse sur une config conforme

**Étant donné** l'explication de la revue humaine
**Quand** elle s'affiche
**Alors** l'injection de prompt est nommée et reliée à la revue humaine, sans scénario qui la déclenche

## Epic 9 : Se situer dans la chaîne et en parler le vocabulaire

L'apprenant voit où il est dans la chaîne, de la Station 1 à la Station 4, et la frontière entre CI et CD. Chaque terme du vocabulaire mène à la barrière qui l'incarne. L'epic se termine par la release v0.2.0.

### Story 9.1 : Se situer grâce au bandeau de la chaîne

En tant qu'apprenant,
je veux un bandeau qui montre les quatre stations, la mienne et la frontière CI | CD,
afin de savoir à tout moment où je suis dans la chaîne.

**Type :** dev

**AD à respecter :** convention Front (ajout sans toucher la disposition), AD-7 (section et station déclarées par le scénario), AD-2 · **Exigences :** FR-32, NFR-10, UX-DR32

**Critères d'acceptation :**

**Étant donné** l'espace de travail en v0.2
**Quand** un scénario de station s'ouvre
**Alors** le bandeau de 44 px s'ajoute sous l'en-tête, avec « Station 1 · Poste local » jusqu'à « Station 4 · Livraison » ; seule la hauteur des vues diminue, et le reste de la disposition est inchangé

**Étant donné** la station du scénario
**Quand** le bandeau s'affiche
**Alors** la station courante a le fond `discipline-harness-soft`, un trait bas, la pilule « Vous êtes ici » et `aria-current="step"`
**Et** le libellé « CI | CD », encadré de deux traits, sépare la Station 3 de la Station 4

**Étant donné** le menu Volets
**Quand** l'apprenant l'ouvre
**Alors** il ne gère pas le bandeau

### Story 9.2 : Déplier la carte de la chaîne

En tant qu'apprenant,
je veux déplier une carte des stations, de leurs outils et de leurs barrières,
afin de relier ce que je vois jouer à l'ensemble de la chaîne.

**Type :** dev

**AD à respecter :** AD-2 (liens des nœuds projetés), convention Front · **Exigences :** FR-32, UX-DR32, UX-DR36 · **Ligne de coupe v0.2 :** élément 1

**Critères d'acceptation :**

**Étant donné** « Carte ▾ », ou un clic sur une station du bandeau
**Quand** l'apprenant ouvre la carte
**Alors** `chain-map` se pose par-dessus les vues sans les déplacer, avec une zone par station et des nœuds d'outil et de barrière
**Et** le bouton porte `aria-expanded` et `aria-controls`, le focus va sur la station demandée, les vues dessous sont `inert`, et Échap ferme la carte en rendant le focus au bouton

**Étant donné** un nœud de barrière
**Quand** l'apprenant le survole ou le sélectionne
**Alors** il est lié aux checks, aux hooks et aux termes correspondants

**Étant donné** un outil indisponible, ou la Station 4 en v0.2
**Quand** la carte s'affiche
**Alors** l'outil est en tirets, et la station non livrée porte « Bientôt » en tirets

### Story 9.3 : Trouver les scénarios de station dans le catalogue

En tant qu'apprenant,
je veux voir les scénarios des stations rangés par station dans le catalogue,
afin de choisir la barrière que je veux voir jouer.

**Type :** dev

**AD à respecter :** AD-14, AD-16, AD-7 (station déclarée) · **Exigences :** FR-9, FR-27, UX-DR29, UX-DR8 (« Arrive en v0.2 » retiré une fois livré)

**Critères d'acceptation :**

**Étant donné** le catalogue en v0.2
**Quand** il s'affiche
**Alors** la section « Stations » apparaît, avec un sous-titre « Station n · Nom » à filet `discipline-harness` par station, et une carte par scénario de barrière, avec une phrase de description et une seule ligne d'état

**Étant donné** un scénario qui demande un outil absent
**Quand** sa carte s'affiche
**Alors** elle est indisponible, avec l'outil nommé

**Étant donné** l'encart « Ce qui l'aurait bloqué » du scénario `.env`
**Quand** la Station 1 est livrée
**Alors** l'étiquette « Arrive en v0.2 » disparaît, et le nom du scénario de la barrière devient un lien

### Story 9.4 : Relier chaque terme du vocabulaire à sa barrière

En tant qu'apprenant,
je veux une page Vocabulaire où chaque terme mène à la barrière que j'ai vue jouer,
afin de parler DevSecOps avec des mots rattachés à quelque chose de concret.

**Type :** dev

**AD à respecter :** AD-2 (élément `barrier:<id>`), AD-7 (`content/glossary.yaml`, lint des barrières), convention Textes affichés · **Exigences :** FR-33, UX-DR33 · **Ligne de coupe v0.2 :** élément 3 (la page ; les termes liés restent)

**Critères d'acceptation :**

**Étant donné** la page Vocabulaire, accessible depuis l'en-tête en v0.2
**Quand** elle s'affiche
**Alors** elle liste les termes : secrets scanning, SAST, SCA, SBOM, quality gate, quatre yeux, protection de branche, traçabilité, DAST ; chacun avec une définition en deux phrases, sa barrière et « Voir la barrière »
**Et** DAST porte « Nommé seulement » et ne mène à aucune barrière

**Étant donné** « Voir la barrière »
**Quand** la barrière est dans l'état courant
**Alors** elle est sélectionnée ; sinon, la carte se déplie sur son nœud avec « La voir jouer : scénario <nom> », ou, si la carte n'est pas livrée, le nom du scénario s'affiche en lien

**Étant donné** un terme cité dans une explication
**Quand** il s'affiche
**Alors** c'est un `glossary-term` souligné en pointillés, qui ouvre son explication

**Étant donné** « traçabilité » en v0.2
**Quand** l'apprenant le suit
**Alors** il mène aux PR et aux checks

### Story 9.5 : Publier la release v0.2.0

En tant qu'Anaël,
je veux publier la v0.2.0 après avoir fini toutes les stations 1 à 3, dans les deux parcours, réseau coupé,
afin de valider SM-9.

**Type :** mixte (publication par l'agent ; SM-9 et mesure des 45 s par Anaël)

**AD à respecter :** AD-18, AD-13 (contrôle 4 sur les scénarios de station) · **Exigences :** NFR-11, SM-9

**Critères d'acceptation :**

**Étant donné** la suite complète verte sur les trois OS, scénarios de station compris sous `unshare -n`
**Quand** Anaël publie
**Alors** `pyproject.toml` porte `0.2.0`, le tag annoté `v0.2.0` existe, et la release GitHub a ses notes

(humain) **Étant donné** un poste réseau coupé
**Quand** Anaël finit les scénarios des stations 1 à 3 des deux parcours, sans indice
**Alors** chaque barrière bloque sur son défaut prévu, et le résultat est consigné dans les notes de release
**Et** sur le poste de référence, un run complet du pipeline dure 45 s au plus, et la mesure est consignée

### Story 9.6 : Explications de la vue pipeline et lien actif Traçabilité

En tant qu'apprenant,
je veux des explications sur la vue pipeline, et un terme « traçabilité » qui mène à ce que j'ai produit,
afin de comprendre ce que je vois et de retrouver les traces concrètes d'une chaîne.

**Type :** dev

**AD à respecter :** AD-2 (`explain_ref` porté par la projection), AD-7 (`content/explanations.yaml`, lint), convention Textes affichés · **Exigences :** FR-5, FR-33, UX-DR33 · **Complète :** story 9.4 (critère « traçabilité »)

**Critères d'acceptation :**

**Étant donné** la vue pipeline
**Quand** l'apprenant ouvre l'explication d'un de ses éléments (job, check, sortie)
**Alors** un `explain-popover` de deux ou trois phrases s'ouvre, tiré d'une entrée de `content/explanations.yaml` par `explain_ref`, et le lint de contenu refuse un `explain_ref` sans entrée

**Étant donné** la page Vocabulaire
**Quand** l'apprenant suit le terme « traçabilité » avec un espace ouvert
**Alors** le lien mène aux PR et aux checks de cet espace

**Étant donné** la page Vocabulaire sans espace ouvert
**Quand** l'apprenant suit « traçabilité »
**Alors** le terme n'est pas un lien mort : la page dit qu'il faut ouvrir un scénario de station pour voir des PR et des checks

## Epic 10 : Livrer une version taguée, la promouvoir et revenir en arrière (station 4)

L'apprenant pose un tag SemVer, construit la version taguée, la déploie en staging, la promeut vers la prod simulée après approbation, puis revient en arrière quand une version est défaillante.

**Prérequis hors story, avant le sprint v0.3 :**
- `bmad-ux` en mise à jour écrit le flow de la Station 4 · Livraison et le parcours UJ-5.
- `bmad-architecture` complète la section Deferred du spine : forme de l'artefact, mécanisme de « servir » staging et la prod simulée, schéma `deliveries` de `github.json`.

Les stories ci-dessous s'appuient sur ce qui est déjà fixé : build hors ligne par `toolrun`, artefact nommé d'après le tag, environnements écrits par `github_sim` seul, approbation dans le journal de revue, `element_id` `env:` et `tag:`. Leurs critères seront précisés à la création de chaque story, d'après ces deux mises à jour.

### Story 10.1 : Poser un tag SemVer annoté

En tant qu'apprenant,
je veux poser un tag annoté qui suit SemVer et le pousser sur `origin`,
afin de marquer une version traçable.

**Type :** dev

**AD à respecter :** AD-4 (`tag` dans la liste blanche, refus avec explication), AD-2 (`tag:<nom>`, `graph-tag`), AD-3 (`tag.gpgsign=false`, `tag -a` sans message reconnu), AD-14 (`evidence_seen`) · **Exigences :** FR-29, FR-33 (traçabilité), UX-DR34

**Critères d'acceptation :**

**Étant donné** le terminal
**Quand** l'apprenant tape `git tag -a v1.2.0 -m "…"`
**Alors** un tag annoté apparaît dans le graphe (forme à encoche), puis sur `origin` après `git push origin v1.2.0`

**Étant donné** un nom qui ne suit pas SemVer (`v1.2`, `1.2.0-`, `release`)
**Quand** l'apprenant tape `git tag -a …`
**Alors** la commande est refusée par `terminal-refused` : « Refusé : `v1.2` ne suit pas SemVer (MAJEUR.MINEUR.CORRECTIF). »

**Étant donné** un tag poussé
**Quand** sa preuve s'affiche
**Alors** le fait `evidence_seen{barrier_id: tag_semver}` est soumis

### Story 10.2 : Construire la version taguée

En tant qu'apprenant,
je veux construire l'artefact de la version taguée et le voir porter le numéro du tag,
afin de savoir exactement ce qui part en staging puis en prod.

**Type :** dev · **Statut :** en attente de l'UX (prérequis de l'Epic 10)

**AD à respecter :** AD-12 (build hors ligne par `toolrun`), AD-8 (état écrit par `github_sim` seul), AD-1 (opération de la file), complément du spine (forme de l'artefact) · **Exigences :** FR-29, UX-DR34

**Critères d'acceptation :**

**Étant donné** l'onglet « Livraison » ajouté à la vue Distant + PR
**Quand** l'apprenant clique « Construire la version taguée » sur un tag poussé
**Alors** le build s'exécute hors ligne, et un `build-artifact` affiche le nom, le numéro du tag en code et le commit source

**Étant donné** un commit sans tag
**Quand** l'apprenant tente un build
**Alors** l'intention est refusée, avec la raison en français

**Étant donné** un build en échec
**Quand** l'outil sort en erreur
**Alors** la sortie réelle s'affiche, et aucun artefact n'est créé

### Story 10.3 : Promouvoir une version vers la prod simulée, après approbation

En tant qu'apprenant,
je veux déployer en staging, puis promouvoir vers la prod simulée seulement après une approbation,
afin de comprendre la frontière entre CI et CD et l'approbation de livraison.

**Type :** dev · **Statut :** en attente de l'UX (prérequis de l'Epic 10)

**AD à respecter :** AD-8 (environnements et approbation écrits par `github_sim`, raisons de blocage avec `element_id`), AD-2 (`env:<staging|prod>`), AD-6 (environnements dans les instantanés), AD-14 (`evidence_seen`), complément du spine (mécanisme de « servir ») · **Exigences :** FR-29, FR-30, FR-33 (traçabilité), UX-DR34

**Critères d'acceptation :**

**Étant donné** un artefact construit
**Quand** l'apprenant le déploie en staging
**Alors** l'`env-card` Staging affiche la version servie, en code

**Étant donné** « Promouvoir vers la prod simulée » sans approbation
**Quand** l'apprenant clique
**Alors** `promotion-gate` refuse la promotion, avec la présentation de `merge-blocked` et la raison liée

**Étant donné** l'approbation de livraison, déclarée par le scénario ou demandée
**Quand** elle entre dans le `review-log` de la livraison
**Alors** `promotion-gate` passe au fond `accent-soft` avec ✓, la promotion réussit, et l'`env-card` Prod simulée affiche la version servie
**Et** le fait `evidence_seen{barrier_id: delivery_approval}` est soumis

### Story 10.4 : Revenir à la version précédente par un rollback

En tant qu'apprenant,
je veux revenir en un geste à la version précédente quand la prod simulée sert une version défaillante,
afin de savoir réparer une livraison.

**Type :** dev · **Statut :** en attente de l'UX (prérequis de l'Epic 10)

**AD à respecter :** AD-8, AD-6, AD-14 (`evidence_seen`), complément du spine · **Exigences :** FR-31, UX-DR34, UX-DR40 (`button-danger`, confirmation en ligne)

**Critères d'acceptation :**

**Étant donné** le scénario « version défaillante en prod simulée »
**Quand** il s'ouvre
**Alors** la prod simulée sert la version défaillante, et la défaillance est visible

**Étant donné** « Rollback » (`button-danger`) sur l'`env-card` de la prod simulée
**Quand** l'apprenant le clique puis confirme en ligne
**Alors** la prod simulée sert la version précédente, et l'annonce dit « La prod simulée sert de nouveau v1.1.0. »
**Et** le fait `evidence_seen{barrier_id: rollback}` est soumis

**Étant donné** l'historique de l'`env-card`
**Quand** il s'affiche
**Alors** il liste les versions servies, dans l'ordre (ligne de coupe v0.3, élément 1)

### Story 10.5 : Les scénarios de la Station 4 · Livraison dans les deux parcours

En tant qu'apprenant,
je veux un scénario de livraison complet dans mon parcours, en séance courte,
afin d'enchaîner tag, build, promotion et rollback.

**Type :** dev · **Statut :** en attente de l'UX (prérequis de l'Epic 10)

**AD à respecter :** AD-7, AD-18 (empreintes), AD-2 · **Exigences :** FR-29 à FR-31, UJ-5, NFR-6, FR-32 (Station 4 au bandeau et sur la carte), FR-33 (traçabilité complétée), UX-DR29

**Critères d'acceptation :**

**Étant donné** les scénarios de la Station 4 (promotion sans approbation, version défaillante) dans les deux parcours
**Quand** le lint, la CI des empreintes et les tests de bout en bout tournent
**Alors** ils passent, et le flow suit UJ-5

**Étant donné** le catalogue, le bandeau et la carte en v0.3
**Quand** ils s'affichent
**Alors** la Station 4 · Livraison a sa section, la pilule « Vous êtes ici » et ses nœuds, sans « Bientôt »

**Étant donné** le terme « traçabilité »
**Quand** l'apprenant le suit en v0.3
**Alors** il mène aussi au tag SemVer et à l'approbation de livraison

## Epic 11 : Défendre la chaîne devant un RSSI et repartir avec la fiche

Karim répond aux questions d'un RSSI simulé. Chaque réponse s'accompagne d'une preuve qu'il désigne dans les vues. Les preuves sont produites pour de vrai par des étapes de préparation. Il exporte ensuite la fiche barrière → risque → preuve, avec ses correspondances ISO 27001, NIS2, DORA et CRA. L'epic se termine par la release v0.3.0.

### Story 11.1 : Décrire les barrières, leurs risques et leurs correspondances réglementaires

En tant qu'Anaël,
je veux un seul fichier de contenu qui décrit chaque barrière, son risque, sa preuve attendue et ses correspondances,
afin que l'entretien, la fiche et le vocabulaire parlent tous de la même barrière.

**Type :** dev

**AD à respecter :** AD-14 (la fiche lit `content/barriers.yaml`), AD-7 (lint des barrières), AD-2 (`barrier:<id>`) · **Exigences :** FR-35, addendum (correspondances candidates)

**Critères d'acceptation :**

**Étant donné** `content/barriers.yaml`
**Quand** on le lit
**Alors** il décrit les neuf barrières de l'addendum (gitleaks, bandit, pip-audit avec SBOM, quality gate, revue obligatoire, protection de branche, tag SemVer, approbation de livraison, rollback), chacune avec risque, preuve attendue, et correspondances ISO 27001:2022, NIS2, DORA et CRA, marquées « explicite » ou « interprétation »
**Et** les contrôles ISO sont cités par leur numéro et un intitulé court, sans le texte de la norme

**Étant donné** le lint de contenu
**Quand** il tourne
**Alors** chaque `barrier_id` cité par un scénario, un terme ou un fait `evidence_seen` existe dans ce fichier

### Story 11.2 : Répondre à une question du RSSI avec une réponse et une preuve

En tant que Karim,
je veux choisir une réponse et désigner sa preuve dans les vues,
afin de montrer qu'une barrière a vraiment joué, pas seulement de la nommer.

**Type :** dev

**AD à respecter :** AD-2 (correction côté serveur, types désignables), AD-7 (type d'étape à deux cases), AD-14 (premier essai), AD-17 (`answer_submit{slots}`), réemploi de la désignation de l'Epic 5 · **Exigences :** FR-34, UX-DR27, UX-DR26

**Critères d'acceptation :**

**Étant donné** une étape `rssi_question`
**Quand** le YAML la déclare
**Alors** elle a une case « Réponse » (`quiz-choice`, avec des propositions réalistes) et une case « Preuve » (désignation, avec son ensemble de bonnes réponses)
**Et** les types désignables sont : sortie d'outil (bloc ou ligne), check, entrée du journal de revue, ligne du SBOM, tag, et SHA si la preuve est un commit

**Étant donné** une seule case remplie
**Quand** l'apprenant regarde « Valider ma réponse »
**Alors** le bouton reste inactif et dit « Il manque la preuve. Désignez-la dans les vues. » (ou la réponse qui manque)

**Étant donné** les deux cases remplies, dans n'importe quel ordre
**Quand** l'apprenant valide
**Alors** la question n'est réussie que si la réponse est juste et la preuve dans l'ensemble déclaré
**Et** un seul essai est permis ; la correction s'affiche dans les vues et dans le panneau ; le premier essai est enregistré

**Étant donné** le bon outil désigné pour la mauvaise barrière
**Quand** la correction s'affiche
**Alors** la question est échouée, et la preuve attendue porte « ✓ Attendu »

### Story 11.3 : Passer l'entretien RSSI

En tant que Karim,
je veux un entretien qui commence par la préparation du dossier, puis enchaîne les questions,
afin de répondre avec des preuves réelles et de connaître mon score.

**Type :** dev

**AD à respecter :** AD-7 (le setup ne lance jamais `ci` ; tag et approbation de livraison posés par des ops de setup), AD-10 (pipeline lancé par l'apprenant pendant la préparation), AD-14 (score mesuré comme les autres scénarios) · **Exigences :** FR-34, FR-20, UJ-4, SM-7, SM-C1, SM-C2

**Critères d'acceptation :**

**Étant donné** le scénario « Entretien RSSI », dans la section « Savoir en parler » du catalogue
**Quand** Karim l'ouvre
**Alors** les étapes de préparation lui font pousser une branche et ouvrir la PR (le pipeline tourne pour de vrai), puis lancer gitleaks dans le terminal ; le tag et l'approbation de livraison viennent du setup
**Et** aucune sortie d'outil n'est fabriquée

**Étant donné** le registre d'ops de setup
**Quand** cette story est livrée
**Alors** il contient les ops `tag` (tag annoté SemVer, poussé sur `origin`) et `approve_delivery` (approbation de livraison écrite par `github_sim` dans le journal de revue), avec identité et dates fixes, si les Stories 10.1 à 10.5 ne les ont pas déjà créées
**Et** le setup de l'entretien a son empreinte de référence sur les trois OS

**Étant donné** la préparation terminée
**Quand** les questions s'enchaînent (par exemple « Qu'est-ce qui empêche une clé d'API d'arriver sur `main` ? »)
**Alors** chaque question couvre une barrière de `content/barriers.yaml`, avec des mauvaises réponses réalistes

**Étant donné** la dernière question
**Quand** le bilan s'affiche
**Alors** il montre « n sur m du premier coup », et propose « Ouvrir la fiche »

### Story 11.4 : Exporter la fiche barrière → risque → preuve

En tant que Karim,
je veux une fiche qui liste chaque barrière, son risque, sa preuve et ses correspondances, exportable en HTML et en CSV,
afin de préparer mon rendez-vous avec le RSSI dans ses propres outils.

**Type :** dev

**AD à respecter :** AD-14 (exports produits par `progress`, rendus par Jinja2 : HTML autonome, CSV UTF-8 avec BOM et séparateur `;` ; preuves vues lues dans les faits), AD-13 · **Exigences :** FR-35, UX-DR31, UX-DR4 (lien Fiche) · **Ligne de coupe v0.3 :** élément 2 (CSV)

**Critères d'acceptation :**

**Étant donné** « Fiche » dans l'en-tête en v0.3, ou « Ouvrir la fiche » au bilan
**Quand** la page s'ouvre
**Alors** `barrier-sheet` a une ligne par barrière et les colonnes Barrière | Risque | Preuve | ISO 27001 | NIS2 | DORA | CRA, avec les étiquettes « explicite » (pleine) et « interprétation » (en tirets)
**Et** une barrière sans fait `evidence_seen` affiche « Preuve pas encore vue : scénario <nom> »

**Étant donné** l'export HTML
**Quand** Karim l'ouvre hors de l'application, réseau coupé
**Alors** il s'affiche en entier, et s'imprime en PDF sur fond blanc, sans pois ni relief

**Étant donné** l'export CSV
**Quand** Karim l'ouvre dans un tableur
**Alors** il a une ligne par barrière, les accents corrects, et une colonne par référentiel avec la mention de chaque correspondance

### Story 11.5 : Publier la release v0.3.0

En tant qu'Anaël,
je veux publier la v0.3.0 après avoir fini la Station 4 et l'entretien RSSI,
afin de valider SM-10 et SM-7.

**Type :** mixte (publication par l'agent ; SM-10 et SM-7 par Anaël)

**AD à respecter :** AD-18 · **Exigences :** NFR-11, SM-10, SM-7

**Critères d'acceptation :**

**Étant donné** la suite complète verte sur les trois OS
**Quand** Anaël publie
**Alors** `pyproject.toml` porte `0.3.0`, le tag annoté `v0.3.0` existe, et la release GitHub a ses notes

(humain) **Étant donné** un poste réseau coupé
**Quand** Anaël finit la Station 4 sans indice (promotion refusée sans approbation, rollback qui ramène la version précédente) et l'entretien RSSI
**Alors** SM-10 et le score de l'entretien (80 % ou plus) sont consignés, marqués « non validé par un tiers » s'il est seul

## Epic 12 : Installation complète, finition et présentation de v1.0.0

Toute la chaîne s'installe en moins de 10 minutes, sans droits administrateur, puis s'utilise réseau coupé. Une mise à jour ne perd rien. Le lot de finition corrige, vérifie et documente. L'epic se termine par la release v1.0.0 et la présentation.

### Story 12.1 : Vérifier l'installation complète, puis l'usage hors ligne, sur trois postes réels

En tant que Camille, sur un poste professionnel,
je veux installer toute la chaîne en moins de 10 minutes, puis tout utiliser réseau coupé,
afin de suivre un atelier complet sans réseau.

**Type :** mixte (mesures sur postes réels par Anaël ; corrections par l'agent)

**AD à respecter :** AD-15, AD-12, AD-16, AD-18 (temps d'installation mesuré avant la release) · **Exigences :** FR-18 (fin), NFR-1, NFR-5, SM-5

**Critères d'acceptation :**

**Étant donné** trois postes réels, sous Windows, macOS et Linux, sans droits administrateur, dont un derrière un proxy d'entreprise
**Quand** l'installation complète est chronométrée
**Alors** elle dure moins de 10 minutes sur chacun, et la durée est relevée dans `install.json`

**Étant donné** chaque poste, une fois le réseau coupé
**Quand** on rejoue un scénario de chaque station et l'entretien RSSI
**Alors** tout fonctionne, et le diagnostic est entièrement vert

**Étant donné** un écart constaté
**Quand** il est corrigé
**Alors** la correction fait l'objet d'un test, ou d'une ligne du diagnostic

### Story 12.2 : Mettre à jour l'application sans perdre sa progression

En tant qu'apprenant qui a commencé en v0.1,
je veux mettre à jour vers v1.0 en gardant ma progression et mes espaces,
afin de ne rien refaire.

**Type :** dev

**AD à respecter :** AD-20 (`schema_version`, migrations numérotées en ajout seulement, `content_hash`, mise à jour par l'installeur ou par `git pull` puis `uv sync`), AD-14 · **Exigences :** FR-18, FR-20, NFR-7

**Critères d'acceptation :**

**Étant donné** des fichiers `progress.json`, `github.json`, `run.json` et `install.json` produits par v0.1, v0.2 et v0.3
**Quand** v1.0 les charge
**Alors** chaque propriétaire applique ses migrations, et les tests de migration passent sur des fixtures de chaque version

**Étant donné** un scénario dont le contenu a changé de façon incompatible
**Quand** l'apprenant le rouvre après la mise à jour
**Alors** « Recommencer » lui est proposé, et son score du premier coup est conservé

### Story 12.3 : Auditer et corriger l'accessibilité

En tant qu'apprenant qui navigue au clavier, avec un lecteur d'écran ou un fort zoom,
je veux que tout soit utilisable dans les deux thèmes,
afin de suivre la formation comme les autres.

**Type :** mixte (contrôle automatique et corrections par l'agent ; audit manuel par Anaël)

**AD à respecter :** AD-2 (annonces et noms accessibles écrits par le serveur), convention Front · **Exigences :** UX-DR7, UX-DR13, UX-DR14, UX-DR26, UX-DR28, UX-DR36, UX-DR37, UX-DR38

**Critères d'acceptation :**

**Étant donné** les parcours UJ-1 à UJ-5, au clavier seul, dans les deux thèmes
**Quand** l'audit est mené
**Alors** chaque action est possible, et l'ordre de Tab, F6 et Échap suit l'UX

**Étant donné** un zoom à 400 % (320 px CSS)
**Quand** le panneau, le catalogue et les pages annexes s'affichent
**Alors** ils se lisent sur une colonne, sans défilement horizontal

**Étant donné** un contrôle automatique de contraste et d'ARIA, en CI
**Quand** il tourne sur les pages principales
**Alors** il ne relève aucun écart de niveau AA
**Et** les écarts trouvés à la main sont corrigés, ou consignés

### Story 12.4 : Intégrer les retours du test v0.1 et des ateliers

En tant qu'Anaël,
je veux traiter les retours consignés depuis le test v0.1 et les ateliers,
afin de présenter un produit qui a tenu compte de ses premiers utilisateurs.

**Type :** mixte (tri des retours par Anaël ; corrections par l'agent)

**AD à respecter :** selon le retour ; en cas de modification d'un AD, `bmad-correct-course` avant le code · **Exigences :** risques « graphe validé par son auteur seul » et « agent B trop propre »

**Critères d'acceptation :**

**Étant donné** la liste des retours consignés
**Quand** Anaël la trie
**Alors** chaque retour est classé (corrigé dans v1.0, reporté après v1.0 ou écarté), avec sa raison
**Et** chaque retour corrigé fait l'objet d'un test, ou d'un scénario mis à jour

### Story 12.5 : Relire les correspondances réglementaires

En tant qu'Anaël,
je veux vérifier chaque numéro ISO 27001 et chaque article NIS2, DORA ou CRA de la fiche,
afin de ne pas présenter à un RSSI une correspondance fausse.

**Type :** humaine

**AD à respecter :** AD-14 · **Exigences :** FR-35, addendum (points de vigilance)

**Critères d'acceptation :**

**Étant donné** `content/barriers.yaml`
**Quand** Anaël relit chaque correspondance contre une source qu'il nomme
**Alors** chaque correspondance est confirmée, corrigée ou retirée, et sa mention « explicite » ou « interprétation » est revue
**Et** la fiche rappelle les points de vigilance de l'addendum (règlement d'exécution NIS2, date d'application du CRA, aucun seuil de couverture imposé)

### Story 12.6 : Chronométrer les séances et finir tous les scénarios sans indice

En tant qu'Anaël,
je veux vérifier que chaque séance tient dans son temps et que je finis tout sans indice,
afin de valider SM-6 et SM-8 avant la présentation.

**Type :** humaine

**AD à respecter :** AD-14 (rapport exporté comme preuve) · **Exigences :** NFR-6, SM-6, SM-8, SM-C3

**Critères d'acceptation :**

**Étant donné** les stations 1 et 2, la station 3, puis la station 4
**Quand** elles sont chronométrées
**Alors** les stations 1 et 2 tiennent en 1 h au plus, la station 3 dans une autre heure, et la station 4 en séance courte, sans explication raccourcie ni sautée

**Étant donné** tous les scénarios des deux parcours
**Quand** Anaël les finit
**Alors** le rapport exporté montre zéro indice, et il est joint aux notes de release

### Story 12.7 : Mesurer le transfert hors de l'application

En tant qu'Anaël,
je veux savoir si un apprenant répare seul un vrai dépôt cassé après l'atelier,
afin de mesurer ce que la formation apporte hors de l'application.

**Type :** humaine

**AD à respecter :** AD-14 (les mesures ne quittent la machine que par l'export fait par l'apprenant) · **Exigences :** PRD §10 (mesure du transfert et de l'usage après les ateliers), NFR-9 · **Ligne de coupe v1.0 :** élément 1

**Critères d'acceptation :**

**Étant donné** un protocole écrit dans `docs/`
**Quand** on le lit
**Alors** il décrit l'exercice de fin d'atelier (un vrai dépôt git cassé, hors de l'application), ce qu'on observe, et la question posée un mois plus tard sur l'usage

**Étant donné** le premier atelier après v1.0
**Quand** le protocole est appliqué
**Alors** les résultats sont consignés sans donnée personnelle, conformément à NFR-9

### Story 12.8 : Publier v1.0.0 et la présenter

En tant qu'Anaël,
je veux publier la v1.0.0 avec sa documentation, puis la présenter aux collègues,
afin de lancer les ateliers.

**Type :** mixte (publication et documentation par l'agent ; présentation par Anaël)

**AD à respecter :** AD-18 · **Exigences :** NFR-9, NFR-11, SM-5 à SM-8

**Critères d'acceptation :**

**Étant donné** la suite complète verte sur les trois OS, et les Stories 12.1 à 12.6 terminées
**Quand** Anaël publie
**Alors** `pyproject.toml` porte `1.0.0`, le tag annoté `v1.0.0` existe, et la release GitHub a ses notes, avec SM-5 à SM-8 et leur statut « validé par un tiers » ou non
**Et** le topic GitHub passe à `status-deployed`, et l'entrée de `portfolio.json` est à jour

**Étant donné** le README et le guide d'atelier
**Quand** on les lit
**Alors** le README dit comment installer, lancer, mettre à jour, et énonce l'absence de télémétrie ; le guide décrit le déroulé d'un atelier par station
