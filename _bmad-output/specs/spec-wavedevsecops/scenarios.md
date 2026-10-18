# Catalogue des scénarios — WaveDevSecOps

Scénarios décrits en YAML déclaratif, avec des types d'étape extensibles. Chaque étape porte une explication écrite. Les deux parcours (code LLM en décor, code minimal sans IA) partagent la progression ; seul le code d'exercice change.

## Socle git (v0.1)

| Ordre | Thème | Mode A (je tape) | Mode B (l'agent a agi) |
|---|---|---|---|
| 1 | add / commit | oui | `.env` committé ; annonce les barrières DevSecOps |
| 2 | push / pull | oui, commit d'un collègue à récupérer | `push --force` qui écrase le travail d'un collègue |
| 3 | branche | oui | |
| 4 | PR / merge | oui, via le GitHub simulé | |
| 5 | conflit | oui | |
| 6 | stash | oui | stash oublié |
| 7 | rebase | oui | rebase laissé en conflit |
| 8 | récupération (reflog / reset) | oui | |

Les cases vides du mode B ne sont pas exigées par la source. L'agent B est scénarisé et déterministe ; il ne fait pas de leçon sur le fonctionnement des agents. Des quiz ponctuent les scénarios : la mauvaise commande choisie est exécutée, expliquée, puis annulée.

Code d'exercice du parcours LLM, de scénario en scénario : appel simple → prompt système → outils → boucle. Son exécution est facultative.

## Stations DevSecOps

| Station | Barrière | Défaut prévu qui la déclenche |
|---|---|---|
| 1 poste local (v0.2) | ruff, pytest | défaut de lint, test cassé |
| 1 | hook pre-commit gitleaks | secret dans un commit |
| 2 PR et CI (v0.2) | checks obligatoires, revue obligatoire, protection de `main` | check en échec, PR sans revue, push direct sur `main` |
| 3 sécurité et qualité (v0.2) | bandit (SAST) | code vulnérable |
| 3 | pip-audit (SCA) + SBOM | dépendance vulnérable |
| 3 | quality gate | couverture sous le seuil |
| 3, parcours LLM | gitleaks | clé d'API en dur |
| 3, parcours LLM | bandit + deux approbations | outil trop puissant donné au LLM |
| 3, parcours LLM | test de config | données envoyées au cloud : config non locale par défaut ou endpoint hors liste autorisée |
| 3, parcours LLM | revue humaine | injection de prompt, seulement nommée |
| 4 livraison (v0.3) | approbation, rollback | promotion sans approbation, version défaillante en prod simulée |

La station 3 a des scénarios dans les deux parcours.

## Savoir en parler

- **Entretien RSSI** : quiz ; chaque réponse désigne une preuve dans les vues (sortie d'outil, check, journal de revue, SBOM, tag).
- **Fiche exportable** : barrière → risque → preuve, avec correspondance ISO 27001, NIS2, DORA, CRA.
