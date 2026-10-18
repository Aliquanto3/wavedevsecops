---
id: SPEC-wavedevsecops
companions:
  - milestones.md
  - scenarios.md
  - success-metrics.md
  - glossary.md
  - risks.md
  - pedagogy-reference.md
sources:
  - ../../../docs/forge/forged-idea.md
  - ../../../docs/forge/forge-report.html
---

> **Contrat canonique.** Cette SPEC et les fichiers de `companions:` forment le contrat complet de ce qu'il faut construire, tester et valider. Les sources listées en frontmatter servent à la traçabilité.

# WaveDevSecOps

## Why

**Vision à réaliser** doublée d'une **douleur** : appliquer la pédagogie de WaveStack (montrer ce qui se passe vraiment, vue par vue) à git, GitHub puis la chaîne CI/CD et DevSecOps. Les personnes qui codent avec des agents (vibe coding) ne tapent jamais `git rebase`, ne savent pas revenir en arrière et ne comprennent pas ce que l'agent a fait sur leur dépôt ; elles ne savent pas non plus dire à un RSSI quelle barrière protège leur code, contre quel risque, avec quelle trace. Public successif : Anaël, puis ses collègues en vibe coding (en autonomie, puis en ateliers), puis des clients. Le seul atout face à Learn Git Branching, Oh My Git! ou GitHub Skills est le **vrai** git, hors ligne. Projet open source exposé au portfolio (`ai-portfolio`), présenté officiellement à la `v1.0.0`.

## Capabilities

Jalon de livraison entre parenthèses ; détail dans `milestones.md`, catalogue des scénarios dans `scenarios.md`.

### Socle git

- **CAP-1** Bac à sable git réel (v0.1)
  - **intent:** L'apprenant tape de vraies commandes git sur un dépôt bac à sable relié à un dépôt distant local qui joue `origin`.
  - **success:** La sortie affichée est celle de git, sans réécriture ; tous les scénarios s'exécutent réseau coupé.
- **CAP-2** Vues synchronisées (v0.1)
  - **intent:** L'apprenant voit côte à côte le code, le dépôt local (graphe des commits, index), le distant et les PR simulés, et le terminal.
  - **success:** Après chaque commande, chaque vue reflète l'état réel des dépôts (graphe conforme à `git log --all`, index conforme à `git status`).
- **CAP-3** GitHub simulé (v0.1)
  - **intent:** L'apprenant ouvre une PR, la fait relire, la merge et récupère les commits d'un collègue, sans compte ni réseau.
  - **success:** Une branche poussée donne une PR que l'on relit et merge ; un commit de collègue apparaît sur `origin` et se récupère par `pull`.
- **CAP-4** Scénarios « je tape » (mode A) (v0.1)
  - **intent:** L'apprenant suit la progression add/commit → push/pull → branche → PR/merge → conflit → stash → rebase → récupération (reflog/reset), avec une explication écrite à chaque étape.
  - **success:** Chaque étape se valide sur l'état réel du dépôt, pas sur le texte tapé ; chaque étape affiche son explication.
- **CAP-5** Scénarios « l'agent a agi » (mode B) (v0.1)
  - **intent:** Un agent scénarisé a modifié le dépôt, erreurs réalistes comprises ; l'apprenant comprend ce qui s'est passé, puis décide et répare.
  - **success:** Rejouer un scénario B donne le même état de dépôt octet pour octet ; les erreurs `.env` committé, `push --force`, stash oublié et rebase en conflit ont chacune un scénario ; le scénario `.env` annonce les barrières DevSecOps.
- **CAP-6** Quiz à exécution réelle (v0.1)
  - **intent:** Quand l'apprenant choisit la mauvaise commande, elle est exécutée pour de vrai, son effet est expliqué, puis annulé.
  - **success:** Après annulation, l'état des dépôts (commits, refs, index, arbre de travail, stash) est identique à l'état d'avant.
- **CAP-7** Deux parcours (v0.1)
  - **intent:** L'apprenant choisit un parcours dont le code d'exercice appelle un LLM et devient un mini-harnais (appel simple → prompt système → outils → boucle), ou un parcours au code minimal sans IA.
  - **success:** Chaque parcours se termine sans jamais exécuter le code LLM ; l'exécution du code LLM reste possible en option.
- **CAP-8** Installation autonome (v0.1, complétée en v1.0)
  - **intent:** Une personne installe l'application seule, sans droits administrateur.
  - **success:** Sur Windows, macOS et Linux, en moins de 10 min sans admin : git et l'application en v0.1 ; tous les outils de la chaîne en v1.0, qui tourne alors entièrement hors ligne.
- **CAP-9** Suivi de progression local (v0.1)
  - **intent:** L'application mesure ce qu'exigent les critères de réussite : score au premier essai de chaque quiz et usage des indices par scénario.
  - **success:** Pour chaque scénario terminé, l'apprenant voit son score du premier coup et le nombre d'indices utilisés.

### Chaîne DevSecOps

- **CAP-10** Station 1, poste local (v0.2)
  - **intent:** L'apprenant fait tourner ruff, pytest et un hook pre-commit gitleaks sur le dépôt d'exercice.
  - **success:** Un commit contenant un secret est refusé par le hook avec la sortie de gitleaks ; un défaut de lint et un test cassé prévus échouent visiblement.
- **CAP-11** Station 2, PR et CI (v0.2)
  - **intent:** Un pipeline simulé exécute les outils sur chaque PR ; checks obligatoires, protection de `main` et revue obligatoire s'appliquent.
  - **success:** Une PR avec un check en échec ou sans revue ne peut pas être mergée ; un push direct sur `main` est refusé.
- **CAP-12** Trois écritures du même pipeline (v0.2)
  - **intent:** L'apprenant lit, en lecture seule, le pipeline écrit pour GitHub Actions, Jenkins (`Jenkinsfile`) et GitLab CI (`.gitlab-ci.yml`).
  - **success:** Chaque étape du pipeline simulé renvoie à ses lignes dans les trois fichiers.
- **CAP-13** Station 3, sécurité et qualité — le cœur (v0.2)
  - **intent:** L'apprenant voit bandit (SAST), pip-audit (SCA) avec un SBOM, et une quality gate avec seuil de couverture (équivalent Sonar) bloquer une PR.
  - **success:** Chaque outil bloque une PR sur un défaut prévu et l'explique ; le SBOM est consultable ; la gate échoue sous le seuil de couverture ; la station a des scénarios dans les deux parcours.
- **CAP-14** Barrières propres au code LLM (v0.2)
  - **intent:** Le parcours LLM montre les barrières contre ses risques propres : clé en dur → gitleaks ; outil trop puissant → bandit et deux approbations ; données envoyées au cloud → test qui vérifie la config locale par défaut et la liste des endpoints autorisés ; injection de prompt nommée seulement, couverte par la revue humaine.
  - **success:** Chacune des trois premières barrières a un scénario où elle se déclenche et bloque ; l'injection de prompt est nommée et reliée à la revue.
- **CAP-15** Station 4, livraison (v0.3)
  - **intent:** L'apprenant pose un tag SemVer, construit, promeut de staging vers une prod simulée après approbation, puis fait un rollback.
  - **success:** Sans approbation, pas de promotion ; après rollback, la prod simulée sert la version précédente.
- **CAP-16** Carte de la chaîne (v0.2)
  - **intent:** Une vue suit l'apprenant de station en station et montre où s'arrête la CI et où commence la CD.
  - **success:** La station courante est mise en évidence ; la frontière CI / CD est visible.

### Savoir en parler

- **CAP-17** Vocabulaire lié aux barrières
  - **intent:** Chaque terme cible (voir `glossary.md`) est rattaché à une barrière visible dans les vues.
  - **success:** Chaque terme ouvre la barrière qui l'incarne ; DAST, seul terme sans barrière, est signalé comme seulement nommé.
- **CAP-18** Entretien RSSI
  - **intent:** Un scénario au format quiz simule un entretien avec un RSSI ; chaque réponse s'appuie sur une preuve désignée dans les vues.
  - **success:** Une réponse sans preuve désignée n'est pas acceptée ; le score du premier coup est mesuré (CAP-9).
- **CAP-19** Fiche barrière → risque → preuve
  - **intent:** L'apprenant exporte une fiche qui liste, pour chaque barrière, le risque couvert, la preuve produite et la correspondance avec ISO 27001, NIS2, DORA et CRA.
  - **success:** L'export produit un fichier lisible hors de l'application, avec une ligne par barrière et ses correspondances réglementaires.

## Constraints

- **Hors ligne de bout en bout** : git, GitHub simulé et toute la chaîne DevSecOps tournent sans réseau.
- **Vrai git** : jamais de git simulé ; les messages affichés sont ceux de git.
- **Déterminisme** : aucun vrai LLM ne pilote git ; aucun scénario ne dépend de l'exécution du code LLM ; l'agent B est entièrement scénarisé.
- **Outils réels et légers** : ruff, pytest, pre-commit, gitleaks, bandit, pip-audit ; aucun serveur lourd (ni Jenkins ni SonarQube réels).
- **Installation légère** : moins de 10 min, sans droits administrateur ; serveur local Python géré par `uv`.
- **Trois systèmes** : Windows 10/11, macOS et Linux ; tous les outils de la chaîne doivent exister sur les trois.
- **Points d'ancrage dès v0.1**, pour que les stations s'ajoutent sans refonte : scénarios en YAML déclaratif à types d'étape extensibles ; modèle de PR qui porte checks et protection de branche ; dépôts d'exercice avec `pyproject.toml` et `tests/` ; mise en page qui accepte un volet supplémentaire.
- **Séances d'une heure au plus** : stations 1-2 en une séance, station 3 en une autre, station 4 en séance courte ; le socle git (branche → PR → conflit → récupération) tient en 1 h.
- **Un seul produit à jalons** : release SemVer à chaque jalon (version dans le manifeste, tag annoté, release GitHub avec notes) ; open source, topic `ai-portfolio`.

## Non-goals

- Git simulé en JavaScript.
- Chatbot tuteur avant v1.0.
- Vrai LLM qui pilote git.
- Vrais Jenkins et SonarQube.
- Enseigner le fonctionnement des agents : le code LLM est un décor, l'agentique n'est pas un objectif pédagogique.
- Un scénario par référentiel de conformité : la simple correspondance suffit.
- Deux produits successifs (V1, V2).
- Docker, Kubernetes, IaC, observabilité, secrets managers (glossaire au mieux) ; DAST au-delà du nom.
- Après v1.0 seulement : mode formateur (réinitialiser, sauter une étape, notes d'animation), mode connecté à un vrai GitHub, chatbot (Ollama et endpoints cloud), MR de GitLab en glossaire, cherry-pick et bisect, anglais, hébergement sans installation, suivi de plusieurs apprenants.

## Success signal

- **v0.1** : Anaël finit les scénarios git sans indice (quiz ≥ 80 % du premier coup) ; deux collègues installent seuls en moins de 10 min sans admin, puis en 1 h au plus finissent branche → PR → conflit → récupération et expliquent ce qu'un agent a fait.
- **v1.0** : installation de tous les outils en moins de 10 min sans admin, chaîne entièrement hors ligne ; parcours DevSecOps en séances d'une heure au plus ; entretien RSSI réussi à ≥ 80 % du premier coup avec preuves, fiche exportée ; Anaël finit tous les scénarios des deux parcours sans indice. Protocole dans `success-metrics.md`.

## Assumptions

- Le contenu du lot de finition de la v1.0 est fixé au découpage en stories.
- Interface et contenus en français ; l'anglais vient après v1.0.
- Un seul apprenant par installation ; progression stockée en local.
- Des indices existent et leur usage est compté, puisque les critères disent « sans indice ».
- Carte de la chaîne et vocabulaire arrivent avec les stations (v0.2) ; entretien RSSI et fiche au plus tard en v1.0, jalon exact fixé au découpage en stories.

## Open Questions

**À trancher en architecture** (laissés ouverts volontairement) :

- Installer git sans droits admin (MinGit portable ?), et de même gitleaks (binaire Go) et les autres outils.
- Snapshot et restauration fiables du bac à sable (condition de CAP-6).
- pip-audit hors ligne : instantané embarqué de la base de vulnérabilités, ou résultat simulé.
- Comment le pipeline simulé exécute les outils et affiche les checks.
- Nom, licence, stack (reprendre celle de WaveStack ?). Constat : le README et le fichier LICENSE du dépôt portent déjà le nom WaveDevSecOps et Apache 2.0.
- Couche de connexion LLM pour l'exécution facultative du code d'exercice.
