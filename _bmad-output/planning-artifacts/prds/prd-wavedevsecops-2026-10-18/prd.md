---
title: WaveDevSecOps
status: final
created: 2026-10-18
updated: 2026-10-18
sources:
  - ../../../specs/spec-wavedevsecops/SPEC.md
  - ../../../specs/spec-wavedevsecops/scenarios.md
  - ../../../specs/spec-wavedevsecops/milestones.md
  - ../../../specs/spec-wavedevsecops/success-metrics.md
  - ../../../specs/spec-wavedevsecops/risks.md
  - ../../../specs/spec-wavedevsecops/glossary.md
  - ../../../specs/spec-wavedevsecops/pedagogy-reference.md
---

# PRD : WaveDevSecOps

## 0. Objet du document

Ce PRD s'adresse à Anaël, qui porte le produit, ainsi qu'aux étapes suivantes : UX, architecture, puis découpage en epics et stories. Il reprend sans les rediscuter les décisions de la spec `_bmad-output/specs/spec-wavedevsecops/`. Le PRD ne recopie pas cette spec : il la traduit en exigences fonctionnelles numérotées (FR-n), en parcours utilisateur (UJ-n) et en critères de réussite (SM-n). Chaque FR renvoie à la capability d'origine (CAP-n) et au jalon qui la livre. Le vocabulaire du §3 est obligatoire dans tout le document. Les inférences non confirmées portent la marque `[ASSUMPTION]` et sont reprises au §11. Le détail technique est dans `addendum.md`.

## 1. Vision

WaveDevSecOps est une application locale qui apprend git, GitHub, puis la chaîne CI/CD et DevSecOps, en montrant ce qui se passe vraiment, pendant que cela se passe, vue par vue. Elle reprend la pédagogie de WaveStack : plusieurs vues synchronisées sur le même état, une explication courte attachée à chaque élément, et des échecs qui servent de matériau pédagogique au lieu de faire planter l'application.

Le public visé code avec des agents (vibe coding). Ces personnes ne tapent jamais `git rebase`, ne savent pas revenir en arrière et ne comprennent pas ce que l'agent a fait sur leur dépôt. Elles ne savent pas non plus dire à un RSSI quelle barrière protège leur code, contre quel risque, avec quelle preuve. L'application les fait passer d'un vrai bac à sable git aux stations DevSecOps, jusqu'à un entretien RSSI simulé et une fiche exportable barrière → risque → preuve.

Learn Git Branching, Oh My Git! et GitHub Skills existent déjà. Face à Learn Git Branching et GitHub Skills, le seul atout de WaveDevSecOps est le **vrai** git, hors ligne : les sorties affichées sont celles de git, et tout tourne réseau coupé. Oh My Git! utilise aussi du vrai git ; face à lui, l'atout est ce qui vient ensuite : GitHub simulé, l'agent qui a déjà agi sur le dépôt, puis la chaîne DevSecOps jusqu'à l'entretien RSSI. Le projet est open source, publié au portfolio (`ai-portfolio`) avec une release SemVer à chaque jalon, et sera présenté officiellement en `v1.0.0`.

## 2. Utilisateurs cibles

### 2.1 Jobs To Be Done

- **Comprendre ce que l'agent a fait** sur mon dépôt, et savoir réparer : revenir en arrière, récupérer un commit perdu, défaire un `push --force`.
- **Taper git sans peur**, parce que je vois l'effet de chaque commande sur le graphe, l'index et le distant.
- **Savoir défendre mon code devant un RSSI** : nommer la barrière, le risque qu'elle couvre et la preuve qu'elle laisse.
- **Parler le vocabulaire DevSecOps** (SAST, SCA, SBOM, quality gate, quatre yeux) en le rattachant à quelque chose que j'ai vu bloquer.
- **Apprendre sur un poste verrouillé**, sans droits administrateur ni réseau, en séances d'une heure au plus.

### 2.2 Public successif et non-utilisateurs

Les publics arrivent dans cet ordre : Anaël, puis des collègues en vibe coding (seuls, puis en ateliers), puis des clients. Ne sont pas visés avant v1.0 :

- Les formateurs qui animent une salle : le mode formateur vient après v1.0.
- Les publics non francophones.
- Les équipes qui veulent un suivi de plusieurs apprenants.

Ne sont visées à aucun jalon : les personnes qui veulent apprendre le fonctionnement des agents. Le code LLM n'est qu'un décor.

### 2.3 Parcours utilisateur clés

- **UJ-1. Anaël termine le socle git sans indice (v0.1).**
  - **Contexte :** l'auteur du produit, qui doit lui-même réussir chaque scénario sans aide avant de le montrer à quelqu'un.
  - **Point de départ :** application installée et lancée en local ; parcours LLM choisi.
  - **Déroulé :** Anaël ouvre le scénario « branche » dans l'ordre conseillé et lit la consigne. Il tape `git switch -c feature` dans le terminal, et le graphe montre la nouvelle branche. Au quiz suivant, Anaël choisit volontairement `git reset --hard HEAD~1` : la commande s'exécute pour de vrai, le graphe montre le commit perdu, l'explication s'affiche, puis l'état est rétabli.
  - **Moment clé :** à la fin du scénario, Anaël voit son score du premier coup et « 0 indice ».
  - **Suite :** il passe au scénario « PR / merge ».

- **UJ-2. Camille installe seule, puis comprend ce que l'agent a fait (v0.1).**
  - **Contexte :** collègue consultante qui code avec un agent et n'a jamais résolu un conflit à la main. Poste professionnel sans droits administrateur.
  - **Point de départ :** elle a reçu un lien vers le dépôt.
  - **Déroulé :** elle lance la commande unique d'installation. Elle ouvre l'application, et la page de diagnostic confirme que git est trouvé. En moins d'une heure, elle enchaîne branche, PR dans le GitHub simulé, conflit (qu'elle résout dans la vue code), puis récupération par `reflog`. Elle ouvre enfin le scénario de mode B « `.env` committé » : un agent scénarisé a committé un fichier de secrets. Elle répond à la question « qu'a fait l'agent ? », retire le secret de l'historique, et lit l'annonce des barrières qui l'auraient bloqué.
  - **Moment clé :** elle sait expliquer, graphe à l'appui, ce que l'agent a fait.
  - **Cas limite :** si l'installation échoue derrière un proxy d'entreprise, la page de diagnostic dit quoi régler.

- **UJ-3. Camille voit une PR bloquée en station 3 (v0.2).**
  - **Contexte :** atelier d'une heure consacré à la sécurité et à la qualité.
  - **Déroulé :** dans le parcours LLM, le code d'exercice donne au LLM un outil trop puissant. Elle pousse et ouvre la PR. Le pipeline simulé lance bandit, qui échoue, et la PR exige deux approbations. La carte de la chaîne situe la station courante. Elle corrige, et bandit repasse au vert. pip-audit signale ensuite une dépendance vulnérable : elle consulte le SBOM, met à jour la dépendance, et la quality gate passe au-dessus du seuil de couverture.
  - **Moment clé :** la PR devient mergeable, et chaque check vert renvoie à ses lignes dans les fichiers GitHub Actions, Jenkins et GitLab CI.

- **UJ-4. Karim répond au RSSI et repart avec la fiche (au plus tard v1.0).**
  - **Contexte :** développeur chez un client, qui doit présenter à son RSSI la chaîne qui protège une application écrite avec un agent.
  - **Déroulé :** il lance l'entretien RSSI. À chaque question (par exemple « qu'est-ce qui empêche une clé d'API d'arriver sur `main` ? »), il choisit une réponse et désigne sa preuve dans les vues : la sortie de gitleaks, le check en échec, le journal de revue. Une réponse sans preuve est refusée.
  - **Moment clé :** il atteint au moins 80 % du premier coup et exporte la fiche barrière → risque → preuve, avec les correspondances ISO 27001, NIS2, DORA et CRA.
  - **Suite :** il ouvre la fiche hors de l'application pour préparer son rendez-vous.

## 3. Glossaire

Le glossaire reprend celui de la spec (`glossary.md`) et le complète. Le vocabulaire cible et ses barrières sont détaillés en FR-33.

- **Bac à sable** : dépôt git réel, propre à l'exercice, qu'on peut restaurer.
- **`origin`** : dépôt bare local qui joue le rôle du distant.
- **GitHub simulé** : couche locale qui fournit PR, revue, merge et commits d'un collègue.
- **Mode A** : l'apprenant tape les commandes et voit leur effet.
- **Mode B** : un agent scénarisé a déjà agi sur le dépôt ; l'apprenant comprend ce qui s'est passé, puis décide.
- **Parcours** : LLM (le code d'exercice appelle un LLM, en décor) ou sans IA (code minimal).
- **Station** : partie de la chaîne DevSecOps : 1 poste local, 2 PR et CI, 3 sécurité et qualité, 4 livraison.
- **Barrière** : contrôle qui bloque un risque et laisse une preuve.
- **Carte de la chaîne** : vue qui situe l'apprenant dans les stations et montre la frontière entre CI et CD.
- **Vue** (ou **volet**) : zone de l'écran qui montre une facette de l'état : code, dépôt local, distant et PR, terminal, carte.
- **Scénario** : séquence d'étapes décrite en YAML, qui prépare l'état des dépôts et donne la consigne. Il appartient à un mode (A ou B) et sert les deux parcours.
- **Étape** : unité d'un scénario. Elle a un type extensible, une consigne et une explication, et elle se valide sur l'état réel des dépôts.
- **Quiz** : étape où l'apprenant choisit une commande ou une réponse. Une mauvaise commande est exécutée, expliquée, puis annulée.
- **Indice** : aide à paliers ouverte à la demande pendant une étape (piste, commande partielle, solution). Chaque palier ouvert compte pour un indice.
- **Score du premier coup** : part des quiz d'un scénario réussis au premier essai.
- **Preuve** : trace visible dans les vues qui atteste qu'une barrière a joué : sortie d'outil, check, journal de revue, SBOM, tag.
- **Pipeline simulé** : exécution locale, sur chaque PR, des outils de la chaîne, dont le résultat s'affiche sous forme de checks.
- **Prod simulée** / **staging** : environnements locaux de la station 4, qui servent une version construite.
- **Dépôt d'exercice** : contenu du bac à sable, soit un petit projet Python avec `pyproject.toml` et `tests/`, propre à chaque parcours. Les barrières tournent sur lui.
- **Quatre yeux** : règle selon laquelle aucun changement n'arrive sur `main` sans la revue d'une autre personne. Elle prend la forme d'une revue obligatoire (station 2) et de deux approbations (station 3).
- **Jalon** : version livrée (v0.1, v0.2, v0.3, v1.0), qui donne lieu à une release SemVer.

## 4. Fonctionnalités

### 4.1 Bac à sable et terminal (v0.1, CAP-1)

**Description :** l'apprenant travaille sur un vrai dépôt git (le bac à sable), relié à un dépôt bare local qui joue `origin`. Le terminal intégré accepte git et quelques commandes de fichiers. Les fichiers se modifient dans la vue code ou dans l'éditeur habituel de l'apprenant. Réalise UJ-1 et UJ-2.

#### FR-1 : Vraies commandes git

L'apprenant tape des commandes git dans le terminal intégré, et elles s'exécutent sur le bac à sable.

**Conséquences (testables) :**
- La sortie affichée est celle de git (stdout et stderr), sans réécriture.
- `push`, `pull` et `fetch` agissent sur `origin`, réseau coupé.

#### FR-2 : Commandes de fichiers de base et confinement

En plus de git, le terminal accepte une courte liste de commandes de fichiers (du type `ls`, `cat`, `echo >`, `rm`) qui s'exécutent dans le bac à sable. `[ASSUMPTION: la liste exacte est fixée en architecture, avec un comportement identique sur les trois systèmes.]`

**Conséquences (testables) :**
- Toute commande hors de la liste est refusée, avec une explication en français.
- Aucune commande acceptée ne lit ni n'écrit hors du bac à sable et de `origin`.

#### FR-3 : Édition des fichiers

L'apprenant modifie un fichier dans la vue code et l'enregistre. Un bouton ouvre aussi ce fichier dans son éditeur externe.

**Conséquences (testables) :**
- Après un enregistrement dans la vue code, `git status` voit le changement.
- Après une modification faite dans un éditeur externe, les vues se mettent à jour sans action de l'apprenant. `[ASSUMPTION: un délai de quelques secondes est acceptable.]`

### 4.2 Vues synchronisées (v0.1, CAP-2)

**Description :** les vues code, dépôt local (graphe des commits et index), distant avec ses PR simulées, et terminal sont affichées côte à côte, sur le même état. Réalise UJ-1 à UJ-3.

#### FR-4 : Vues fidèles à l'état réel

**Conséquences (testables) :**
- Après chaque commande et chaque enregistrement de fichier, le graphe est conforme à `git log --all` et l'index à `git status`.
- Les vues sont à jour avant que l'explication de l'étape s'affiche : l'apprenant voit l'effet pendant qu'il se produit, pas après coup.
- La vue du distant montre les refs de `origin` et les PR du GitHub simulé.

#### FR-5 : Correspondances entre vues

Sélectionner un élément (un commit, un fichier, une PR) met en évidence ses correspondants dans les autres vues, comme dans WaveStack. `[ASSUMPTION: principe repris de pedagogy-reference.md ; les correspondances exactes sont fixées en UX.]`

### 4.3 GitHub simulé (v0.1, CAP-3)

**Description :** une couche locale fournit PR, revue, merge et commits d'un collègue, sans compte ni réseau. Réalise UJ-2 et UJ-3.

#### FR-6 : Cycle de PR

L'apprenant ouvre une PR depuis une branche poussée, la fait relire, puis la merge.

**Conséquences (testables) :**
- Une branche poussée sur `origin` permet d'ouvrir une PR vers `main`.
- Le merge met à jour `main` sur `origin`, et le graphe le montre.

#### FR-7 : Commits d'un collègue

Un scénario fait apparaître sur `origin` le commit d'un collègue simulé.

**Conséquences (testables) :**
- Le commit se récupère par `git pull` et apparaît dans le graphe local.

#### FR-8 : Modèle de PR prêt pour les stations

Dès v0.1, le modèle de PR porte des checks, des approbations et une protection de branche, même si aucun scénario de v0.1 ne les active. Ce point d'ancrage permet d'ajouter les stations sans refonte.

**Conséquences (testables) :**
- Un scénario de test de v0.1 qui active un check bloquant empêche le merge, sans modification du modèle de PR.

### 4.4 Scénarios, progression et indices (v0.1, CAP-4, CAP-5)

**Description :** l'apprenant suit la progression du socle git en mode A, puis en mode B (catalogue dans `scenarios.md`). Il peut ouvrir n'importe quel scénario. Réalise UJ-1 et UJ-2.

#### FR-9 : Catalogue en ordre conseillé, accès libre

L'apprenant voit les scénarios dans l'ordre conseillé (add/commit → push/pull → branche → PR/merge → conflit → stash → rebase → récupération par reflog et reset) et peut en ouvrir un à tout moment.

**Conséquences (testables) :**
- Chaque scénario prépare son propre état initial, sans dépendre des scénarios précédents.
- Le catalogue indique, pour chaque scénario, s'il est terminé.

#### FR-10 : Recommencer un scénario

L'apprenant remet un scénario à son état initial avec un bouton « Recommencer ». Ce bouton n'est pas le mode formateur (réinitialiser à volonté, sauter une étape), qui vient après v1.0.

**Conséquences (testables) :**
- L'état reconstruit est identique, octet pour octet, à l'état initial du scénario.
- Chaque remise à zéro est journalisée, sans pénalité.
- Le score du premier coup et le compte d'indices restent ceux du premier passage : recommencer ne permet pas d'améliorer SM-1.

#### FR-11 : Scénarios mode A

Chaque étape donne une consigne et affiche son explication.

**Conséquences (testables) :**
- Une étape est validée sur l'état réel des dépôts, jamais sur le texte tapé : deux commandes différentes qui produisent le même état sont acceptées toutes les deux.
- Si l'apprenant arrive à un état inattendu, l'étape l'explique au lieu de planter.

#### FR-12 : Scénarios mode B

Un agent scénarisé a déjà modifié le dépôt, erreurs réalistes comprises. L'apprenant comprend ce qui s'est passé, puis décide et répare.

**Conséquences (testables) :**
- Rejouer un scénario B donne le même état de dépôt, octet pour octet.
- Les erreurs `.env` committé, `push --force` qui écrase le travail d'un collègue, stash oublié et rebase laissé en conflit ont chacune leur scénario.
- Le scénario `.env` annonce les barrières DevSecOps qui l'auraient bloqué.
- Avant de réparer, l'apprenant répond à « qu'a fait l'agent ? » en désignant l'élément en cause dans les vues : il clique le commit, la branche ou la ligne de diff, ou tape un SHA. La réponse est corrigée automatiquement contre le dépôt réel.
- La question n'accepte qu'un essai. L'explication s'affiche ensuite, que la réponse soit juste ou non. Le résultat entre dans le score du premier coup et mesure SM-4.

**Hors périmètre :** aucun vrai LLM ne pilote l'agent B, et aucun scénario n'explique comment fonctionnent les agents.

#### FR-13 : Indices à paliers

Pendant une étape, l'apprenant ouvre à la demande jusqu'à trois paliers d'indice : piste, commande partielle, solution.

**Conséquences (testables) :**
- Chaque palier ouvert compte pour un indice dans le suivi (FR-20), sans pénalité sur le score.
- Les paliers s'ouvrent dans l'ordre : on n'accède pas à la solution sans être passé par la piste.
- La solution ne s'ouvre qu'après une tentative de l'apprenant sur l'étape, ou après quelques secondes passées sur le palier précédent. L'apprenant la tape lui-même : elle ne s'exécute pas toute seule.
- Pour chaque indice, le suivi enregistre le palier atteint, le temps écoulé avant la demande et le temps de lecture avant l'action suivante.

#### FR-14 : Scénarios déclaratifs

L'auteur ajoute un scénario en écrivant un fichier YAML, sans modifier le code de l'application, tant qu'il utilise des types d'étape existants.

**Conséquences (testables) :**
- Un nouveau type d'étape (par exemple « check de PR » pour les stations) s'ajoute sans modifier les scénarios existants.

### 4.5 Quiz à exécution réelle (v0.1, CAP-6)

#### FR-15 : Mauvaise commande exécutée puis annulée

Quand l'apprenant choisit une mauvaise commande, elle s'exécute pour de vrai, son effet est expliqué dans les vues, puis il est annulé.

**Conséquences (testables) :**
- Après l'annulation, l'état est identique à celui d'avant (commits, refs, index, arbre de travail, stash du bac à sable ; refs de `origin` ; état des PR).
- Si la restauration échoue, l'application le signale et propose de recommencer le scénario (FR-10), sans laisser l'apprenant sur un état faux.

### 4.6 Deux parcours (v0.1, CAP-7)

#### FR-16 : Choix du parcours

L'apprenant choisit le parcours LLM ou le parcours sans IA, au code minimal. Les deux suivent la même progression, et seul le code d'exercice change. Dans le parcours LLM, ce code évolue de scénario en scénario : appel simple → prompt système → outils → boucle.

**Conséquences (testables) :**
- Chaque parcours se termine sans jamais exécuter le code LLM.
- L'apprenant peut changer de parcours. Chaque parcours garde sa propre progression, ce qui permet de mesurer SM-8 parcours par parcours.

#### FR-17 : Exécution facultative du code LLM

L'apprenant peut, en option, exécuter le code d'exercice du parcours LLM. Aucun scénario n'en dépend. La couche de connexion au LLM est une question d'architecture (§10).

### 4.7 Installation et premier lancement (v0.1, complétée en v1.0, CAP-8)

#### FR-18 : Installation sans droits administrateur

Une personne installe l'application seule, avec une commande unique (PowerShell sous Windows, équivalent shell sous macOS et Linux), ou depuis un clone ou un zip.

**Conséquences (testables) :**
- v0.1 : git et l'application s'installent en moins de 10 min, sans droits administrateur, sur Windows 10/11, macOS et Linux.
- v1.0 : tous les outils de la chaîne s'installent dans les mêmes conditions, et l'application tourne ensuite entièrement hors ligne.
- L'installation fonctionne derrière un proxy d'entreprise.

#### FR-19 : Page de diagnostic

Au premier lancement, une page indique la présence et la version de chaque outil requis par le jalon, et dit quoi faire pour chaque outil manquant.

**Conséquences (testables) :**
- Un outil absent ou trop ancien est signalé avec la marche à suivre, et les scénarios qui en dépendent sont marqués indisponibles au lieu de planter.
- La page détecte un proxy configuré et rappelle les réglages utiles (certificats, `NO_PROXY`).

### 4.8 Suivi de progression local (v0.1, CAP-9)

#### FR-20 : Score et indices par scénario

Pour chaque scénario terminé, l'apprenant voit son score du premier coup et le nombre d'indices utilisés.

**Conséquences (testables) :**
- Les données sont stockées en local dans un fichier lisible, pour un seul apprenant par installation, et survivent à un redémarrage. Le fichier contient aussi l'horodatage de l'installation et celui du premier lancement, ce qui permet de mesurer SM-2.
- Le score de l'entretien RSSI (FR-34) est mesuré de la même façon.

#### FR-36 : Rapport de progression exporté

L'apprenant exporte lui-même un rapport de sa progression (scores, indices, remises à zéro, horodatages) dans un fichier qu'il peut transmettre s'il le souhaite. C'est le seul moyen pour les mesures de quitter la machine (NFR-9).

### 4.9 Chaîne DevSecOps : stations 1 et 2 (v0.2, CAP-10 à CAP-12)

**Description :** les outils réels tournent sur le dépôt d'exercice (`pyproject.toml`, `tests/`), en local puis dans un pipeline simulé sur chaque PR. Réalise UJ-3.

#### FR-21 : Station 1, poste local

L'apprenant lance ruff et pytest, et un hook pre-commit gitleaks protège les commits.

**Conséquences (testables) :**
- Un commit qui contient un secret est refusé par le hook, avec la sortie de gitleaks.
- Le défaut de lint et le test cassé prévus échouent visiblement.

#### FR-22 : Station 2, pipeline simulé sur PR

Sur chaque PR, le pipeline simulé exécute les outils et affiche un check par outil.

**Conséquences (testables) :**
- Une PR dont un check obligatoire échoue ne peut pas être mergée.
- Une PR sans la revue obligatoire (quatre yeux) ne peut pas être mergée.
- Un push direct sur `main` est refusé.

#### FR-23 : Trois écritures du même pipeline

L'apprenant lit, en lecture seule, le même pipeline écrit pour GitHub Actions, Jenkins (`Jenkinsfile`) et GitLab CI (`.gitlab-ci.yml`).

**Conséquences (testables) :**
- Chaque tâche du pipeline simulé renvoie à ses lignes dans les trois fichiers.

**Hors périmètre :** vrais Jenkins et GitLab, et exécution de ces fichiers.

### 4.10 Station 3, sécurité et qualité : le cœur (v0.2, CAP-13, CAP-14)

**Description :** trois barrières bloquent une PR sur un défaut prévu, et chacune explique pourquoi. La station a des scénarios dans les deux parcours. Le parcours LLM y ajoute les barrières propres au code LLM. Réalise UJ-3.

#### FR-24 : SAST avec bandit

Le code vulnérable prévu fait échouer le check bandit, avec l'explication du défaut.

**Conséquences (testables) :**
- La PR est bloquée, et l'échec désigne le fichier, la ligne et la règle bandit en cause.
- Une fois le défaut corrigé, le check repasse au vert sans autre changement.

#### FR-25 : SCA avec pip-audit, et SBOM

La dépendance vulnérable prévue fait échouer le check pip-audit. L'apprenant consulte le SBOM du dépôt d'exercice.

**Conséquences (testables) :**
- La PR est bloquée, et l'échec désigne la dépendance et sa vulnérabilité.
- Le check fonctionne réseau coupé (le moyen relève de l'architecture, §10).

#### FR-26 : Quality gate

La quality gate échoue quand la couverture du nouveau code passe sous 80 %, valeur par défaut de la quality gate de Sonar.

**Conséquences (testables) :**
- La PR est bloquée, et l'échec affiche la couverture mesurée et le seuil.

#### FR-27 : Scénarios dans les deux parcours

Chaque barrière de FR-24 à FR-26 a au moins un scénario dans le parcours LLM et un dans le parcours sans IA.

#### FR-28 : Barrières propres au code LLM (parcours LLM)

**Conséquences (testables) :**
- Chacune des trois premières barrières ci-dessous a un scénario où elle se déclenche et bloque la PR.
- Une clé d'API en dur est bloquée par gitleaks.
- Un outil trop puissant donné au LLM est bloqué par bandit, et la PR exige deux approbations.
- Un test vérifie que la config est locale par défaut et que les endpoints appelés figurent sur la liste autorisée. Le test échoue sur une config non locale ou un endpoint hors liste.
- L'injection de prompt est nommée et reliée à la revue humaine, sans scénario qui la déclenche.

### 4.11 Station 4, livraison (v0.3, CAP-15)

#### FR-29 : Tag et build

L'apprenant pose un tag SemVer, puis construit la version taguée.

**Conséquences (testables) :**
- Le tag est un tag annoté visible dans le graphe et sur `origin`.
- Un tag qui ne respecte pas SemVer est refusé, avec une explication.
- Le build produit un artefact qui porte le numéro du tag ; cet artefact est celui que staging puis la prod simulée servent.

#### FR-30 : Promotion après approbation

L'apprenant promeut la version de staging vers la prod simulée.

**Conséquences (testables) :**
- Sans approbation, la promotion est refusée.

#### FR-31 : Rollback

Un scénario fait servir une version défaillante en prod simulée, et l'apprenant déclenche le rollback.

**Conséquences (testables) :**
- Après le rollback, la prod simulée sert la version précédente.

### 4.12 Carte de la chaîne (v0.2, CAP-16)

#### FR-32 : Situer l'apprenant

Une vue suit l'apprenant de station en station.

**Conséquences (testables) :**
- La station courante est mise en évidence.
- La frontière entre CI et CD est visible.
- La carte s'ajoute comme vue supplémentaire, sans refonte de la mise en page de v0.1.

### 4.13 Savoir en parler (v0.2 à v1.0, CAP-17 à CAP-19)

**Description :** l'apprenant relie le vocabulaire aux barrières qu'il a vues jouer, défend la chaîne devant un RSSI simulé et repart avec une fiche. Réalise UJ-4.

#### FR-33 : Vocabulaire lié aux barrières (v0.2)

Chaque terme du vocabulaire cible ouvre la barrière qui l'incarne dans les vues.

**Conséquences (testables) :**
- Chaque terme mène à la barrière visible qui l'incarne :
  - secrets scanning → gitleaks (hook pre-commit en station 1, clé en dur en station 3) ;
  - SAST → bandit ;
  - SCA / SBOM → pip-audit et SBOM ;
  - quality gate → seuil de couverture ;
  - quatre yeux → revue obligatoire et deux approbations ;
  - protection de branche → `main` protégée ;
  - traçabilité → PR, checks, tag SemVer et approbation de livraison.
- DAST est signalé comme seulement nommé, sans barrière.

Comme les preuves de traçabilité (tag, approbation de livraison) n'existent qu'à partir de la station 4, l'entretien RSSI et la fiche complets arrivent au plus tôt en v0.3. En v0.2, le terme « traçabilité » de FR-33 mène aux PR et aux checks.

#### FR-34 : Entretien RSSI (au plus tard v1.0)

Un scénario au format quiz simule un entretien avec un RSSI. Chaque réponse doit désigner une preuve dans les vues.

**Conséquences (testables) :**
- Une réponse sans preuve désignée n'est pas acceptée.
- Le score du premier coup est mesuré (FR-20).

#### FR-35 : Fiche barrière → risque → preuve (au plus tard v1.0)

L'apprenant exporte une fiche qui liste, pour chaque barrière, le risque couvert, la preuve produite et la correspondance avec ISO 27001, NIS2, DORA et CRA.

**Conséquences (testables) :**
- L'export produit deux fichiers lisibles hors de l'application. Le premier est un HTML autonome, imprimable en PDF depuis le navigateur. Le second est un CSV en UTF-8 avec BOM, qui s'ouvre directement dans le tableur où le RSSI tient sa déclaration d'applicabilité.
- Chaque fichier a une ligne par barrière, avec ses correspondances réglementaires. Chaque correspondance porte la mention « explicite » ou « interprétation ».
- Les contrôles ISO 27001 sont cités par leur numéro et un intitulé court, sans reproduire le texte de la norme.

**Hors périmètre :** un scénario par référentiel de conformité (la correspondance suffit), et un export au format OSCAL ou JSON. Les correspondances candidates sont dans `addendum.md`.

## 5. Exigences non fonctionnelles transverses

- **NFR-1 Hors ligne de bout en bout :** git, GitHub simulé et toute la chaîne DevSecOps tournent sans réseau. Seule l'exécution facultative du code LLM (FR-17) peut utiliser le réseau.
- **NFR-2 Vrai git :** jamais de git simulé. Les messages affichés sont ceux de git.
- **NFR-3 Déterminisme :** aucun vrai LLM ne pilote git, et aucun scénario ne dépend de l'exécution du code LLM. L'agent B est entièrement scénarisé. Un même scénario rejoué donne le même état.
- **NFR-4 Outils réels et légers :** ruff, pytest, pre-commit, gitleaks, bandit et pip-audit, sans serveur lourd. Chaque outil existe sur les trois systèmes.
- **NFR-5 Trois systèmes :** Windows 10/11, macOS et Linux, avec un comportement identique pour les scénarios.
- **NFR-6 Séances courtes :** le socle git (branche → PR → conflit → récupération) tient en 1 h, les stations 1 et 2 en une séance d'1 h au plus, la station 3 en une autre, et la station 4 en séance courte.
- **NFR-7 Échecs pédagogiques :** une commande ratée, un état inattendu ou un outil manquant donnent une explication, jamais un plantage.
- **NFR-8 Français :** interface et contenus en français. Les identifiants du code restent en anglais.
- **NFR-9 Confidentialité :** l'application n'envoie aucune télémétrie et ne fait aucun appel réseau. Seule exception : l'exécution facultative du code LLM (FR-17), lancée par l'apprenant. Les mesures ne quittent la machine que par le rapport que l'apprenant exporte (FR-36). Une vérification en CI garantit l'absence d'appel réseau dans le code de l'application, en dehors du module isolé de FR-17. Le README l'énonce explicitement.
- **NFR-10 Points d'ancrage dès v0.1 :** scénarios en YAML à types d'étape extensibles (FR-14), modèle de PR avec checks et protection de branche (FR-8), dépôts d'exercice avec `pyproject.toml` et `tests/`, et mise en page qui accepte une vue supplémentaire (FR-32).
- **NFR-11 Releases :** chaque jalon donne une release SemVer : version dans le manifeste, tag annoté et release GitHub avec notes. Le projet est open source, sous le topic `ai-portfolio`.
- **NFR-12 Forme :** application web servie par un serveur Python géré par `uv`, ouverte automatiquement dans le navigateur. Le serveur n'écoute que sur `127.0.0.1`, sur un port libre : cela évite l'invite du pare-feu et l'accès depuis le réseau. Une fenêtre pywebview reste le repli si le navigateur du poste pose problème.
- **NFR-13 Explication attachée :** chaque élément affiché (commit, ref, check, barrière, sortie d'outil) porte une explication courte en français, accessible depuis l'élément lui-même.

## 6. Non-objectifs

- Un git simulé en JavaScript.
- Un vrai LLM qui pilote git, et un chatbot tuteur avant v1.0.
- De vrais Jenkins et SonarQube.
- Apprendre le fonctionnement des agents : le code LLM est un décor.
- Un scénario par référentiel de conformité.
- Deux produits successifs (V1, V2) : il n'y a qu'un produit, livré par jalons.
- Docker, Kubernetes, IaC, observabilité et secrets managers, au mieux cités dans le glossaire ; DAST, seulement nommé.

## 7. Périmètre par jalon

| Jalon | Contenu | FR |
|---|---|---|
| `v0.1` socle git hors ligne | Bac à sable, terminal, édition, vues, GitHub simulé, scénarios A et B, indices, quiz, deux parcours, installation de git sans admin, diagnostic, suivi local, points d'ancrage | FR-1 à FR-20, FR-36 |
| `v0.2` stations 1 à 3 | Poste local, PR et CI, trois écritures, SAST, SCA et SBOM, quality gate, barrières LLM, carte, vocabulaire | FR-21 à FR-28, FR-32, FR-33 |
| `v0.3` station 4 | Tag, build, staging → prod simulée, approbation, rollback | FR-29 à FR-31 |
| `v1.0` finition et présentation | Installation de tous les outils sans droits administrateur, puis usage entièrement hors ligne (fin de FR-18), entretien RSSI et fiche s'ils ne sont pas encore livrés, lot de finition (contenu fixé au découpage en stories), puis présentation | FR-18, FR-34, FR-35 |

Après v0.1, deux collègues testent l'application pendant une heure s'ils sont disponibles ; sinon, Anaël la teste seul. C'est le seul moyen de faire valider la vue du graphe par quelqu'un d'autre que son auteur.

**Après v1.0 seulement :** mode formateur (réinitialiser, sauter une étape, notes d'animation), mode connecté à un vrai GitHub, chatbot (Ollama et endpoints cloud), MR de GitLab dans le glossaire, cherry-pick et bisect, version anglaise, hébergement sans installation, suivi de plusieurs apprenants.

## 8. Critères de réussite

Les critères qui portent sur les collègues sont vérifiés par deux collègues s'ils sont disponibles, sinon par Anaël. Un critère vérifié par Anaël seul est marqué « non validé par un tiers » dans les notes de release. Il reste à vérifier au premier atelier. C'est surtout le cas de SM-2 et de SM-4 : Anaël connaît déjà l'installation et les scénarios. Le protocole est dans `success-metrics.md`.

**v0.1**
- **SM-1 Maîtrise de l'auteur :** Anaël finit les scénarios git avec zéro indice, et réussit au moins 80 % des quiz du premier coup. Valide FR-11 à FR-15 et FR-20.
- **SM-2 Installation autonome :** deux collègues installent l'application seuls, sans droits administrateur, en moins de 10 min, chronomètre en main. Valide FR-18 et FR-19.
- **SM-3 Socle en une heure :** en 1 h au plus, ils finissent branche → PR → conflit → récupération. Valide FR-1 à FR-11 et NFR-6.
- **SM-4 Compréhension du mode B :** ils expliquent ce qu'un agent a fait sur le dépôt. Dans l'application, ils désignent l'élément en cause du premier coup ; à l'oral, ils en donnent l'explication pendant le test. Valide FR-12.

**v0.2**
- **SM-9 Stations 1 à 3 :** Anaël finit les scénarios des stations 1 à 3 des deux parcours sans indice, réseau coupé, et chaque barrière bloque sur son défaut prévu. Valide FR-21 à FR-28.

**v0.3**
- **SM-10 Station 4 :** Anaël finit la station 4 sans indice, réseau coupé : promotion refusée sans approbation, rollback qui ramène la version précédente. Valide FR-29 à FR-31.

**v1.0**
- **SM-5 Installation complète :** tous les outils s'installent en moins de 10 min, sans droits administrateur, et la chaîne s'utilise entièrement réseau coupé. Valide FR-18 et NFR-1.
- **SM-6 Séances courtes :** les stations 1 et 2 tiennent dans une séance d'1 h au plus, la station 3 dans une autre, et la station 4 dans une séance courte. Valide NFR-6.
- **SM-7 Entretien RSSI :** au moins 80 % de réussite du premier coup, chaque réponse avec sa preuve, et fiche exportée. Valide FR-34 et FR-35.
- **SM-8 Maîtrise complète de l'auteur :** Anaël finit tous les scénarios des deux parcours sans indice. Valide FR-9 à FR-33.

**Contre-critères (à ne pas optimiser)**
- **SM-C1 Facilité des quiz :** ne pas simplifier les quiz pour atteindre les 80 %. Les mauvaises réponses doivent rester des erreurs réalistes. Contrebalance SM-1 et SM-7.
- **SM-C2 Fidélité des outils :** ne pas simuler la sortie d'un outil pour gagner du temps d'installation. Un outil réel reste la règle, sauf décision d'architecture explicite (pip-audit). Contrebalance SM-2 et SM-5.
- **SM-C3 Explications coupées :** ne pas raccourcir ni sauter les explications pour tenir l'heure. Contrebalance SM-3 et SM-6.
- **SM-C4 Nombre de scénarios :** un scénario de plus ne vaut que s'il couvre une erreur ou une barrière du catalogue. Contrebalance SM-8.

## 9. Risques

Le registre complet est dans `risks.md`. Les risques qui pèsent sur les exigences sont les suivants :

| Risque | Parade |
|---|---|
| L'installation de git, de gitleaks et des autres outils sans droits administrateur échoue (FR-18). | Question 1 du §10 ; critère vérifié en v0.1 (SM-2) puis en v1.0 (SM-5). |
| pip-audit interroge une base en ligne, ce qui casse le hors-ligne (FR-25). | Question 3 du §10. |
| La restauration du bac à sable échoue après un quiz (FR-15). | Question 2 du §10 ; repli sur « Recommencer » (FR-10). |
| Le développement se fait d'un seul bloc jusqu'à v1.0. | Une release à chaque jalon (NFR-11) ; test après v0.1 (§7). |
| La vue du graphe n'est validée que par son auteur (FR-4). | Test avec deux collègues après v0.1, sinon tests d'Anaël. |
| Le code LLM du décor devient lui-même une cible. | Barrières de FR-28 ; exécution du code LLM facultative (FR-17). |
| Un agent B trop propre ne prépare pas aux vraies erreurs. | Erreurs réalistes imposées par FR-12. |

## 10. Questions ouvertes

Ces questions sont laissées ouvertes ici volontairement : l'architecture les tranche.

1. Comment installer git sans droits administrateur (MinGit portable ?), et de même gitleaks (binaire Go) et les autres outils, sur les trois systèmes.
2. Comment prendre des instantanés du bac à sable et les restaurer de façon fiable (condition de FR-15).
3. Comment faire tourner pip-audit hors ligne : instantané embarqué de la base de vulnérabilités, ou résultat simulé.
4. Comment le pipeline simulé exécute les outils et affiche les checks.
5. Stack : reprendre celle de WaveStack ? Le nom (WaveDevSecOps) et la licence (Apache 2.0) figurent déjà dans le README et le fichier LICENSE.
6. Quelle couche de connexion LLM utiliser pour l'exécution facultative du code d'exercice (FR-17).
7. Quelles commandes de fichiers accepte le terminal (FR-2), et comment garantir le confinement sur les trois systèmes.

Ces points sont fixés au découpage en stories, sous la responsabilité d'Anaël :

- le contenu du lot de finition de v1.0 ;
- le jalon exact de l'entretien RSSI et de la fiche, en v0.3 au plus tôt ;
- une ligne de coupe par jalon, c'est-à-dire ce qu'on sacrifie d'abord si l'auteur seul manque de temps ;
- un parcours utilisateur pour la station 4 ;
- une mesure du transfert hors de l'application (l'apprenant répare-t-il seul un vrai dépôt ?) et de l'usage après les ateliers ;
- le délai chiffré de mise à jour des vues après une modification externe (FR-3).

## 11. Index des hypothèses

- §4.1 FR-2 : la liste exacte des commandes de fichiers est fixée en architecture.
- §4.1 FR-3 : la mise à jour des vues après une modification externe peut prendre quelques secondes.
- §4.2 FR-5 : sélectionner un élément met en évidence ses correspondants, comme dans WaveStack.
Hypothèses confirmées par Anaël le 2026-10-18, après la recherche web : FR-10, FR-12, FR-13, FR-16, FR-36, FR-35, NFR-9 et NFR-12.
