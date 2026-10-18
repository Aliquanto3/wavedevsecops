# Risques — WaveDevSecOps

Points faibles restés ouverts à la sortie de la forge. Les parades marquées « architecture » relèvent des questions ouvertes de SPEC.md et ne sont pas tranchées ici.

| Risque | Parade connue |
|---|---|
| git, gitleaks et les autres outils ne s'installent pas sans droits admin sur un poste verrouillé. | Architecture (binaires portables ?). Critère d'installation < 10 min vérifié à v0.1 puis v1.0. |
| pip-audit interroge une base en ligne, ce qui casse le hors-ligne. | Architecture (instantané embarqué ou résultat simulé). |
| La restauration du bac à sable échoue après un quiz où la mauvaise commande est exécutée. | Architecture (snapshot) ; critère de CAP-6 : état identique après annulation. |
| Développement d'un seul bloc jusqu'à v1.0 (« big bang »). | Releases 0.x à chaque jalon ; test après v0.1. |
| La vue du graphe des commits, qui porte tout le reste, n'est validée que par son auteur ; le retour des collègues après v0.1 n'est pas garanti. | Test avec des collègues s'ils sont disponibles, sinon tests d'Anaël. |
| Le code LLM en décor devient une cible (clé en dur, outil trop puissant, données vers le cloud). | Barrières dédiées de CAP-14 ; exécution du code LLM facultative. |
| Un agent B trop propre ne prépare pas aux vraies erreurs. | Erreurs réalistes prévues dans les scénarios B (CAP-5). |
