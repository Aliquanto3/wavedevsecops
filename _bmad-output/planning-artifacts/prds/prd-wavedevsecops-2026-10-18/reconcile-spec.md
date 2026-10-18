# Réconciliation SPEC.md → PRD et addendum (WaveDevSecOps)

Date : 2026-10-18. Source : `_bmad-output/specs/spec-wavedevsecops/SPEC.md`. Cibles : `prd.md`, `addendum.md`. Journal des décisions : `.memlog.md`. Contrôle complémentaire : `success-metrics.md` (ligne 3, critères « collègues »).

Statuts : ok / affaibli / absent / contradictoire. « ok+ » = présent et précisé ou étendu par une décision du memlog, sans contradiction.

## 1. Tableau de réconciliation

### Why

| Élément de la spec | Localisation PRD | Statut |
|---|---|---|
| Vision à réaliser : pédagogie WaveStack (montrer ce qui se passe vraiment, vue par vue) appliquée à git, GitHub, CI/CD, DevSecOps | §1 al. 1 | ok |
| Cadrage « vision doublée d'une douleur » | §1 (la douleur est décrite, jamais nommée comme telle) | ok (ton légèrement perdu) |
| Douleur 1 : ne tapent jamais `git rebase`, ne savent pas revenir en arrière, ne comprennent pas l'agent | §1 al. 2, §2.1 | ok |
| Douleur 2 : dire au RSSI quelle barrière, quel risque, quelle trace | §1 al. 2 (« preuve » au lieu de « trace ») | ok (terme glissé, cohérent avec le glossaire) |
| Public successif : Anaël, collègues (autonomie puis ateliers), clients | §2.2 | ok |
| Concurrents nommés (Learn Git Branching, Oh My Git!, GitHub Skills) | §1 al. 3 | ok |
| « Le **seul** atout » = vrai git, hors ligne | §1 al. 3 : « l'atout » | affaibli (« seul » perdu) |
| Open source, portfolio `ai-portfolio`, présenté officiellement à `v1.0.0` | §1 al. 3, NFR-11 | ok |

### Capabilities

| CAP | Élément | Localisation PRD | Statut |
|---|---|---|---|
| 1 | intent : vraies commandes sur dépôt relié à un `origin` local | §4.1, FR-1 | ok |
| 1 | success : sortie de git sans réécriture | FR-1 | ok |
| 1 | success : tous les scénarios s'exécutent réseau coupé | FR-1 (push/pull/fetch), NFR-1 ; pas de critère testable « tous les scénarios » | ok (implicite) |
| 2 | intent : vues code, dépôt local (graphe, index), distant et PR, terminal | §4.2 | ok |
| 2 | success : graphe = `git log --all`, index = `git status` après chaque commande | FR-4 | ok |
| 3 | intent : ouvrir, relire, merger une PR, récupérer un collègue, sans compte ni réseau | §4.3, FR-6, FR-7 | ok |
| 3 | success : branche poussée → PR relue et mergée ; commit de collègue récupéré par `pull` | FR-6, FR-7 | ok |
| 4 | intent : progression add/commit → … → récupération, explication à chaque étape | FR-9, FR-11 | ok |
| 4 | success : validation sur l'état réel, explication affichée | FR-11 | ok |
| 5 | intent : agent scénarisé, erreurs réalistes, comprendre puis décider et réparer | FR-12 | ok |
| 5 | success : rejeu octet pour octet | FR-12 | ok |
| 5 | success : quatre erreurs (`.env`, `push --force`, stash oublié, rebase en conflit) chacune un scénario | FR-12 | ok |
| 5 | success : le scénario `.env` annonce les barrières DevSecOps | FR-12 | ok |
| 5 | ajout : question « qu'a fait l'agent ? », un essai | FR-12 | ok+ (memlog 2026-10-18) |
| 6 | intent : mauvaise commande exécutée, expliquée, annulée | FR-15 | ok |
| 6 | success : état identique (commits, refs, index, arbre de travail, stash) | FR-15 (étendu aux refs `origin` et aux PR) | ok+ |
| 7 | intent : parcours LLM (mini-harnais : appel simple → prompt système → outils → boucle) | FR-16 | ok |
| 7 | intent : parcours « au code minimal sans IA » | FR-16 : « parcours sans IA » | ok (nuance « code minimal » perdue) |
| 7 | success : fin sans exécuter le code LLM ; exécution possible en option | FR-16, FR-17 | ok |
| 8 | intent : installation seule, sans admin | FR-18 | ok |
| 8 | success : 3 systèmes, < 10 min, v0.1 git + appli, v1.0 tous les outils, hors ligne | FR-18, §7 | ok |
| 9 | intent/success : score du premier coup et indices par scénario terminé | FR-20 | ok |
| 10 | intent : ruff, pytest, hook pre-commit gitleaks sur le dépôt d'exercice | FR-21 | ok |
| 10 | success : secret refusé avec la sortie de gitleaks ; lint et test cassés échouent visiblement | FR-21 | ok |
| 11 | intent : pipeline simulé sur chaque PR, checks obligatoires, protection de `main`, revue obligatoire | FR-22 | ok |
| 11 | success : PR en échec ou sans revue non mergeable ; push direct sur `main` refusé | FR-22 | ok |
| 12 | intent/success : trois écritures en lecture seule, chaque étape renvoie à ses lignes | FR-23 | ok |
| 13 | intent : bandit, pip-audit + SBOM, quality gate avec seuil de couverture | FR-24, FR-25, FR-26 | ok |
| 13 | success : chaque outil bloque une PR et l'explique | §4.10 description (« chacune explique pourquoi ») ; FR-24 explicite ; FR-25 et FR-26 sans critère testable « bloque la PR + explique » | ok (partiel) |
| 13 | success : SBOM consultable ; gate échoue sous le seuil | FR-25, FR-26 | ok |
| 13 | success : scénarios dans les deux parcours | FR-27 | ok |
| 14 | intent/success : clé en dur → gitleaks ; outil trop puissant → bandit + deux approbations ; test config locale + liste d'endpoints ; injection nommée et reliée à la revue | FR-28 | ok |
| 14 | success : chacune des trois premières a **un scénario** qui se déclenche et bloque | FR-28 dit « est bloquée » mais n'exige pas de scénario par barrière | ok (partiel, voir écart 3) |
| 15 | intent/success : tag SemVer, build, staging → prod simulée après approbation, rollback ; pas de promotion sans approbation ; rollback sert la version précédente | FR-29 à FR-31, jalon v0.3 | ok |
| 16 | intent/success : carte, station courante en évidence, frontière CI/CD | FR-32, jalon v0.2 | ok |
| 17 | intent/success : chaque terme ouvre sa barrière ; DAST seul sans barrière | FR-33 | ok |
| 18 | intent/success : entretien RSSI en quiz, preuve désignée obligatoire, score du premier coup | FR-34, FR-20 | ok |
| 19 | intent/success : fiche barrière → risque → preuve + ISO 27001, NIS2, DORA, CRA ; un fichier, une ligne par barrière | FR-35 (deux fichiers, HTML + CSV) | ok+ (memlog) |
| 1 à 19 | Jalons v0.1 / v0.2 / v0.3 ; CAP-18 et 19 au plus tard v1.0 | §7, titres §4 | ok (aucun jalon modifié) |

### Constraints

| Contrainte | Localisation PRD | Statut |
|---|---|---|
| Hors ligne de bout en bout | NFR-1 (exception : exécution facultative du code LLM) | ok |
| Vrai git, messages de git | NFR-2, FR-1 | ok |
| Déterminisme : aucun LLM ne pilote git, aucun scénario ne dépend du code LLM | NFR-3 | ok |
| « L'agent B est entièrement scénarisé » | FR-12 (« agent scénarisé », hors périmètre), pas repris dans NFR-3 | ok (déplacé) |
| Outils réels et légers, aucun serveur lourd | NFR-4, §6 | ok |
| Installation < 10 min, sans admin, serveur Python géré par `uv` | FR-18, NFR-12 | ok |
| Trois systèmes, outils présents sur les trois | NFR-4, NFR-5 | ok |
| Points d'ancrage dès v0.1 (YAML extensible, modèle de PR, dépôts d'exercice, volet supplémentaire) | NFR-10, FR-8, FR-14, FR-32 | ok |
| Séances d'une heure au plus (stations 1-2, 3, 4 ; socle en 1 h) | NFR-6, SM-3, SM-6 | ok |
| Un seul produit à jalons, release SemVer, open source, `ai-portfolio` | NFR-11, §6, §7 | ok |

### Non-goals

| Non-goal | Localisation PRD | Statut |
|---|---|---|
| Git simulé en JavaScript | §6 | ok |
| Chatbot tuteur avant v1.0 | §6 | ok |
| Vrai LLM qui pilote git | §6 | ok |
| Vrais Jenkins et SonarQube | §6 | ok |
| Enseigner le fonctionnement des agents | §6 ; §2.2 (listé sous « Ne sont pas visés avant v1.0 ») | ok en §6 / déformé en §2.2 (écart 2) |
| Un scénario par référentiel de conformité | §6, FR-35 | ok |
| Deux produits successifs | §6 | ok |
| Docker, K8s, IaC, observabilité, secrets managers ; DAST au-delà du nom | §6, FR-33 | ok |
| Après v1.0 : mode formateur (réinitialiser, sauter, notes), connecté, chatbot (Ollama, cloud), MR GitLab, cherry-pick/bisect, anglais, hébergement, multi-apprenants | §7 fin, §2.2, FR-10 | ok |

### Success signal

| Élément | Localisation PRD | Statut |
|---|---|---|
| v0.1 : Anaël sans indice, quiz ≥ 80 % du premier coup | SM-1 | ok |
| v0.1 : deux collègues installent seuls < 10 min sans admin | SM-2 | ok (réserve « si disponibles » justifiée par `success-metrics.md` l.3) |
| v0.1 : en 1 h au plus, branche → PR → conflit → récupération | SM-3 | ok |
| v0.1 : ils expliquent ce qu'un agent a fait | SM-4 (affiné : désignation dans l'appli + oral) | ok+ |
| v1.0 : installation complète < 10 min, hors ligne | SM-5 | ok |
| v1.0 : séances d'une heure au plus | SM-6 | ok |
| v1.0 : entretien RSSI ≥ 80 % du premier coup avec preuves, fiche exportée | SM-7 | ok |
| v1.0 : Anaël finit tous les scénarios des deux parcours sans indice | SM-8 | ok |
| Protocole dans `success-metrics.md` | §8 intro | ok |

### Assumptions

| Hypothèse | Localisation PRD | Statut |
|---|---|---|
| Contenu du lot de finition v1.0 fixé au découpage en stories | §7 (ligne v1.0), §10 fin | ok |
| Français, anglais après v1.0 | NFR-8, §7 | ok |
| Un seul apprenant par installation, progression locale | FR-20 | ok |
| Indices existent et leur usage est compté | FR-13, FR-20 | ok |
| Carte et vocabulaire en v0.2 ; RSSI et fiche au plus tard v1.0, jalon exact au découpage | §7, §4.13, §10 fin | ok |

### Open Questions

| Question | Localisation PRD | Statut |
|---|---|---|
| Installer git, gitleaks et autres outils sans admin (MinGit ?) | §10 q.1 | ok |
| Snapshot et restauration du bac à sable (condition de CAP-6) | §10 q.2 | ok |
| pip-audit hors ligne : instantané embarqué ou résultat simulé | §10 q.3, FR-25, SM-C2 | ok |
| Comment le pipeline simulé exécute les outils et affiche les checks | §10 q.4 | ok |
| Nom, licence, stack (WaveStack ?) + constat README/LICENSE | §10 q.5, addendum « Stack candidate (non décidée) » | ok (nom et licence présentés comme acquis, conforme au constat) |
| Couche de connexion LLM | §10 q.6, FR-17 | ok |
| « À trancher en architecture, laissées ouvertes volontairement » | §10 intro | ok |
| Ajout PRD : q.7 commandes de fichiers du terminal | §10 q.7 | ajout, cohérent (memlog) |

**Éléments vérifiés : 99** (1 Why en 8 points, 19 CAP en 37 lignes intent/success, 10 contraintes, 9 non-goals, 9 success signal, 5 hypothèses, 7 questions ouvertes ; total des lignes du tableau).

Bilan : ok ou ok+ : 95 ; affaibli : 2 (« seul atout », succès partiel de CAP-13) ; déformé : 1 (§2.2, non-goal « agents ») ; partiel : 1 (CAP-14, scénario par barrière). Aucun élément absent, aucun jalon modifié, aucune contradiction non justifiée par le memlog.

## 2. Écarts et corrections proposées

### Écart 1. « Le seul atout » devient « l'atout » (affaibli, ton perdu)

- Spec, Why : « Le **seul** atout face à Learn Git Branching, Oh My Git! ou GitHub Skills est le **vrai** git, hors ligne. »
- PRD §1 al. 3 : « l'atout de WaveDevSecOps est le **vrai** git, hors ligne ».
- Effet : la spec pose un choix de positionnement exclusif (le reste est du décor) ; le PRD le présente comme un atout parmi d'autres.
- Correction : écrire « le seul atout de WaveDevSecOps face à eux est le **vrai** git, hors ligne ».

### Écart 2. Non-goal « enseigner les agents » rangé sous « avant v1.0 » (déformé)

- Spec, Non-goals : « Enseigner le fonctionnement des agents : le code LLM est un décor, l'agentique n'est pas un objectif pédagogique » (permanent) ; seule la liste « Après v1.0 seulement » est datée.
- PRD §2.2 : « Ne sont pas visés avant v1.0 : … Les personnes qui veulent apprendre le fonctionnement des agents. » Cela suggère qu'ils pourraient l'être après v1.0.
- Correction : sortir cette puce de la liste « avant v1.0 » et l'écrire à part : « Ne sont visées à aucun jalon : les personnes qui veulent apprendre le fonctionnement des agents ; le code LLM n'est qu'un décor. »

### Écart 3. CAP-14 : l'exigence « un scénario par barrière qui se déclenche et bloque » n'est pas testable en FR-28

- Spec CAP-14 success : chacune des trois premières barrières a un scénario où elle se déclenche et bloque.
- PRD FR-28 : les conséquences testables disent que la clé est bloquée, l'outil est bloqué, le test échoue ; elles n'exigent pas un scénario par barrière. FR-27 ne couvre que FR-24 à FR-26.
- Correction : ajouter à FR-28 la conséquence « Chacune des trois premières barrières a un scénario du parcours LLM où elle se déclenche et bloque ; l'injection de prompt est nommée et reliée à la revue, sans scénario qui la déclenche. »

### Écart 4. CAP-13 : « chaque outil bloque une PR et l'explique » seulement dans la description de §4.10

- Spec CAP-13 success : chaque outil bloque une PR sur un défaut prévu et l'explique.
- PRD : FR-24 (bandit) mentionne l'explication ; FR-25 (pip-audit) et FR-26 (gate) ne disent ni que la PR est bloquée ni que l'échec est expliqué ; seule la description de §4.10 le dit.
- Correction : ajouter à FR-25 et FR-26 la conséquence testable « La PR est bloquée et l'échec est expliqué (dépendance et vulnérabilité en cause ; couverture mesurée contre le seuil). »

### Écart 5 (mineur). Nuances qualitatives

- CAP-7 : « parcours au code minimal sans IA » devient « parcours sans IA ». Ajouter « au code d'exercice minimal » en FR-16.
- Why : le cadrage « vision à réaliser doublée d'une douleur » n'est pas nommé. Facultatif : une phrase en §1 (« Le projet répond à une vision et à une douleur »).
- Constraints : « l'agent B est entièrement scénarisé » n'est pas reprise littéralement en NFR-3. Ajouter « l'agent du mode B est entièrement scénarisé » à NFR-3.

## 3. Ajouts du PRD sans contradiction avec la spec (pour mémoire)

Tous passent par le memlog ou une hypothèse marquée : terminal borné à git + commandes de fichiers (FR-2), édition dans la vue code + éditeur externe (FR-3), accès libre au catalogue (FR-9), « Recommencer » sans pénalité (FR-10, sans effet sur SM-1), question « qu'a fait l'agent ? » (FR-12), indices à trois paliers (FR-13), zéro télémétrie et rapport exporté (NFR-9, FR-20b), fiche en HTML + CSV (FR-35), forme web locale sur `127.0.0.1` (NFR-12), proxy d'entreprise (FR-18, repris de WaveStack), restauration échouée gérée (FR-15), nouvelle question ouverte q.7. Réserve « collègues si disponibles » (§7, §8) : conforme à `success-metrics.md` l.3, donc non retenue comme écart.

Aucune contradiction PRD / spec non justifiée par le memlog. Aucun ajout du PRD ne contredit la spec.
