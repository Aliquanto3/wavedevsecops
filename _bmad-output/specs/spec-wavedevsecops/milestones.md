# Jalons — WaveDevSecOps

Un seul produit. Chaque jalon donne une release SemVer : version dans le manifeste, tag git annoté, release GitHub avec notes. Présentation officielle à `v1.0.0`.

| Jalon | Contenu | Capabilities |
|---|---|---|
| `v0.1` socle git hors ligne | Bac à sable réel, vues, GitHub simulé, scénarios A et B, quiz, deux parcours, installation de git sans admin, suivi local. Points d'ancrage des stations posés (voir Constraints de SPEC.md). | CAP-1 à CAP-9 |
| `v0.2` stations 1 à 3 | Poste local, PR et CI, trois écritures du pipeline, sécurité et qualité, barrières du code LLM, carte de la chaîne, vocabulaire. | CAP-10 à CAP-14, CAP-16, CAP-17 |
| `v0.3` station 4 | Livraison : tag, build, staging → prod simulé, approbation, rollback. | CAP-15 |
| `v1.0` finition et présentation | Lot de finition (contenu fixé au découpage en stories), installation de tous les outils hors ligne (fin de CAP-8), entretien RSSI et fiche s'ils ne sont pas déjà livrés, puis présentation aux collègues et ateliers. | CAP-8, CAP-18, CAP-19 |

## Après v0.1

Test pendant une heure avec 2 collègues s'ils sont disponibles, sinon tests d'Anaël seul. Ce retour est le seul moyen de valider la vue du graphe par d'autres que son auteur (voir `risks.md`).
