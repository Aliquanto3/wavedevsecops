# git-commands-training

> ⚪ **En spécification** : aucun code pour l'instant.

Application pédagogique locale pour apprendre git et GitHub, puis la chaîne CI/CD et les
concepts DevSecOps, pensée pour les personnes qui codent avec des agents (vibe coding) et
doivent comprendre ce que l'agent fait sur leur dépôt. Pédagogie inspirée de
[WaveStack](https://github.com/Aliquanto3/agentic-harness-training-demo).

## Ce qui est prévu

- **Du vrai git, hors ligne** : un dépôt bac à sable, un dépôt distant local et un GitHub
  simulé (PR, revue, merge, commits d'un collègue), dans des vues synchronisées.
- **Deux façons d'apprendre** : taper les commandes et voir leur effet ; puis lire ce qu'un
  agent scénarisé a fait sur le dépôt (erreurs réalistes comprises) et décider.
- **Quiz** où la mauvaise commande est exécutée pour de vrai, expliquée, puis annulée.
- **Deux parcours** : un code qui appelle un LLM puis devient un mini-harnais (prompt système,
  outils, boucle), ou un code minimal sans IA.
- **Chaîne DevSecOps en quatre stations**, avec des outils légers (ruff, pytest, pre-commit,
  gitleaks, bandit, pip-audit) : poste local, PR et CI, sécurité et qualité, livraison.
  Jenkins, GitHub Actions, GitLab CI et Sonar sont montrés comme équivalents.
- **Savoir en parler à un RSSI** : scénario d'entretien et fiche barrière → risque → preuve.

## Jalons

`v0.1` socle git → `v0.2` stations 1 à 3 → `v0.3` livraison → `v1.0` présentation.

## Documents

- [Idée forgée](docs/forge/forged-idea.md) : décisions, options rejetées, points à trancher.
- [Rapport de la session](docs/forge/forge-report.html).

## Licence

Apache 2.0, voir [LICENSE](LICENSE) et [NOTICE](NOTICE).
