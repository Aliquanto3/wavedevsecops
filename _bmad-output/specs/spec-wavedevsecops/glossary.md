# Glossaire — WaveDevSecOps

## Vocabulaire cible (CAP-17), chaque terme lié à une barrière visible

| Terme | Barrière qui l'incarne |
|---|---|
| Secrets scanning | gitleaks, hook pre-commit (station 1) et clé en dur (station 3) |
| SAST | bandit (station 3) |
| SCA / SBOM | pip-audit et SBOM (station 3) |
| Quality gate | seuil de couverture, équivalent Sonar (station 3) |
| Quatre yeux | revue obligatoire, deux approbations (stations 2 et 3) |
| Protection de branche | `main` protégée (station 2) |
| Traçabilité | PR, checks, tag SemVer, approbation de livraison (stations 2 et 4) |
| DAST | seulement nommé, sans barrière |

## Termes du produit

- **Bac à sable** : dépôt git réel, propre à l'exercice, restaurable.
- **`origin`** : dépôt bare local qui joue le distant.
- **GitHub simulé** : couche locale qui fournit PR, revue, merge et commits d'un collègue.
- **Mode A** : l'apprenant tape les commandes et voit leur effet.
- **Mode B** : un agent scénarisé a agi sur le dépôt ; l'apprenant comprend et décide.
- **Parcours** : LLM (code d'exercice qui appelle un LLM, en décor) ou sans IA (code minimal).
- **Station** : étape de la chaîne DevSecOps (1 poste local, 2 PR et CI, 3 sécurité et qualité, 4 livraison).
- **Barrière** : contrôle qui bloque un risque et laisse une preuve.
- **Carte de la chaîne** : vue qui situe l'apprenant dans les stations et montre la frontière CI / CD.

## Hors périmètre, au mieux en glossaire

Docker, Kubernetes, IaC, observabilité, secrets managers. Après v1.0 : MR (GitLab).
