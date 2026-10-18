# Idée forgée : git-commands-training

Appli locale pour apprendre git/GitHub puis la chaîne CI/CD et DevSecOps, pédagogie WaveStack. Public : Anaël, puis collègues en vibe coding (autonomie, puis ateliers), puis clients. Open source, topic `ai-portfolio`.

## Produit et jalons
- Un seul produit, une seule spec. Présentation officielle à `v1.0.0`.
- Releases SemVer : `v0.1` socle git hors ligne → `v0.2` stations 1 à 3 → `v0.3` station 4 → `v1.0`.
- Après le socle git : test avec 2 collègues s'ils sont disponibles, sinon tests d'Anaël seul.

## Socle git
- **Mécanique** : A (l'apprenant tape les commandes, voit l'effet) ; scénarios B (un agent a agi sur le dépôt, l'apprenant comprend et décide).
- **Moteur** : vrai git sur un dépôt bac à sable, serveur local Python/uv. Dépôt bare local = `origin`. Couche « GitHub simulé » : PR, revue, merge, commits d'un collègue. Tout hors ligne.
- **Agent B** scénarisé et déterministe, avec des erreurs réalistes prévues (`.env` committé, `push --force`, stash oublié, rebase en conflit).
- **Deux parcours** : code LLM en décor (appel simple → prompt système → outils → boucle ; exécution facultative, aucun scénario n'en dépend, pas de leçon sur le fonctionnement des agents) et code minimal sans IA.
- **Contenu** : vues code, dépôt local (graphe, index), distant et PR simulés, terminal. Scénarios add/commit → push/pull → branche → PR/merge → conflit → stash → rebase → récupération (reflog/reset). Quiz où la mauvaise commande est exécutée pour de vrai puis annulée. Explication écrite à chaque étape.

## Chaîne DevSecOps
- **Concepts et barrières**, avec de vrais outils légers locaux. Pas de vrai Jenkins ni de vrai SonarQube.
- **Station 1, poste local** : ruff, pytest, hook pre-commit gitleaks.
- **Station 2, PR et CI** : pipeline simulé qui exécute les outils, checks obligatoires, protection de `main`, revue obligatoire. GitHub Actions, Jenkinsfile et `.gitlab-ci.yml` montrés comme trois écritures du même pipeline, en lecture seule.
- **Station 3, sécurité et qualité (le cœur)** : bandit (SAST), pip-audit (SCA) et SBOM, quality gate avec seuil de couverture (équivalent Sonar).
  - Barrières propres au code LLM : clé en dur → gitleaks ; outil trop puissant → bandit + 2 approbations ; données vers le cloud → test sur la config locale par défaut + endpoints autorisés ; injection de prompt nommée seulement, avec revue humaine.
  - Scénarios dans les deux parcours.
- **Station 4, livraison (en dernier)** : tag SemVer, build, staging → prod simulé, approbation, rollback.
- **Savoir en parler** :
  - vocabulaire cible lié à une barrière visible (secrets scanning, SAST, SCA/SBOM, quality gate, quatre yeux, protection de branche, traçabilité ; DAST seulement nommé) ;
  - scénario « entretien RSSI », au format quiz, chaque réponse appuyée sur une preuve dans les vues ;
  - fiche exportable barrière → risque → preuve ;
  - conformité (ISO 27001, NIS2, DORA, CRA) en simple correspondance.
- **Schémas CI / CD** : une vue « carte de la chaîne » suit l'apprenant.
- **Hors périmètre** : Docker, K8s, IaC, observabilité, secrets managers (glossaire au mieux).

## Points d'ancrage dès le socle git
Scénarios en YAML déclaratif avec des types d'étape extensibles ; modèle de PR avec checks et protection de branche ; dépôts d'exercice avec `pyproject.toml` et `tests/` ; mise en page qui accepte un volet supplémentaire ; scénario `.env` qui annonce les barrières.

## Critères de réussite
- **v0.1, socle git** :
  - Anaël finit les scénarios sans indice (quiz ≥ 80 % du premier coup).
  - 3 collègues installent seuls en moins de 10 min sans droits admin.
  - En 1 h ou moins, ils finissent branche → PR → conflit → récupération et expliquent ce qu'un agent a fait.
- **v1.0** :
  - Installation de tous les outils en moins de 10 min sans admin, chaîne entièrement hors ligne.
  - Parcours DevSecOps en séances d'une heure au plus (stations 1-2, puis 3 ; la 4 en séance courte).
  - Entretien RSSI réussi à ≥ 80 % du premier coup, avec preuves, et fiche exportée.
  - Anaël finit tous les scénarios des deux parcours sans indice.
  - Critères collègues vérifiés par eux s'ils sont disponibles, sinon par Anaël.

## Rejeté
- **Git simulé en JS** : terrain occupé (Learn Git Branching, Oh My Git!, GitHub Skills), messages non fidèles.
- **Chatbot tuteur avant v1.0** : risque en démo, coût du routage multi-endpoints.
- **Vrai LLM qui pilote git** : non déterministe, désynchronise les quiz.
- **Vrais Jenkins et SonarQube** : serveurs Java lourds, incompatibles avec l'installation légère.
- **Agentique comme objectif pédagogique** : double charge cognitive.
- **Scénario par référentiel de conformité** : la simple correspondance suffit.
- **Deux produits successifs V1 et V2** : remplacés par un seul produit à jalons.

## Plus tard (après v1.0)
Mode formateur pour les ateliers (réinitialiser, sauter une étape, notes d'animation), mode connecté à un vrai GitHub, chatbot (Ollama et endpoints cloud), MR de GitLab dans un glossaire, cherry-pick et bisect, anglais, hébergement sans installation, suivi de plusieurs apprenants.

## À trancher en architecture
- git sans droits admin (MinGit portable ?), et de même gitleaks (binaire Go) et les autres outils.
- Snapshot et restauration fiables du bac à sable.
- pip-audit en hors ligne : instantané de la base de vulnérabilités embarqué, ou résultat simulé.
- Comment le pipeline simulé exécute les outils et affiche les checks.
- Nom, licence, stack (reprendre celle de WaveStack ?).
- Couche de connexion LLM (exécution facultative du code d'exercice).
