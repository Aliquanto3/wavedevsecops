---
story: "3.3"
key: 3-3-voir-le-distant-et-les-pr-dans-la-vue-distant-pr
title: Voir le distant et les PR dans la vue Distant + PR
status: review
branch: story/3-3-vue-distant-pr
ad: [AD-2, AD-17]
---

# Story 3.3 : Voir le distant et les PR dans la vue Distant + PR

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 3.3 » ; FR-4, FR-6, FR-8, UX-DR19, UX-DR35, UX-DR40.

## Livré

- **Projection `views.remote`** (`contracts/remote.py`, `projections/remote.py`) : calculée par le serveur à chaque projection, d'après `github.json` et les refs de `origin.git`. `Views.remote` est un ajout (valeur par défaut vide, AD-17). Un `github.json` ou un `origin.git` illisible donne `remote.error_text`, jamais une projection en échec.
  - `branches[]` : une branche de `origin` (`name_text` « origin/feature », `short_sha`, `protection_text`, `pr_number` de la PR ouverte, `can_open_pr`). `can_open_pr` : branche poussée, différente de `main`, sans PR ouverte, avec du travail à merger (`github_sim.is_contained`, ajout public de la 3.3).
  - `pulls[]` : `pr-card` avec titre (« PR n°n : branche » si le scénario n'en a pas), `branches_text` « feature → main », `state_text`, `current`, `checks[]`, `review`, `merge`. Ordre : PR courante (l'ouverte de la branche locale courante, sinon la plus récente ouverte), puis les autres ouvertes, puis les mergées.
  - `checks[]` : `pr-check` avec `state_text` (En attente, En cours, Réussi, Échec, Erreur de l'outil), `duration_text` (« 2,4 s », « 2 min 05 s »), `required` (déclaré, ou exigé par la protection de la base), `stale`. Ordre d'affichage du serveur : échecs et erreurs, puis en attente et en cours, puis réussis.
  - `review` : `review-log` avec `entries[]` (auteur, badge `actor`, `action_text`, `time_text` « 14:32 UTC », `body_text`, `stale`), `counter_text` « Approbations : 1 sur 2 » et `required_text` « 2 approbations requises » (« Aucune approbation requise » sans protection).
  - `merge` : `enabled` (PR ouverte et mergeable), `disabled_text`, `reasons[]` (`kind`, `text`, `element_id` de l'élément en cause : le check, ou `pr:n` pour les approbations et le conflit) et `done_text` « Mergée dans main (a1b2c3d) ».
- **Annonce** : `projections.project` ajoute à `announce_text` les changements de PR (« PR n°1 ouverte, feature → main. », « PR n°1 : mergée. », « PR n°1 peut être mergée. », compteur d'approbations) ; la région `role="status"` partagée les lit.
- **Front** (`web/static/js/remote.js`, `web/static/css/remote.css`) : le volet `remote` de `views.js` rend la projection. Ordre de l'UX : refs de `origin`, puis par carte le titre et « feature → main » en code, les checks en échec, `merge-blocked` (bouton Merger et une raison par ligne), les checks en attente, en cours et réussis, le `review-log`. Sans PR : « Aucune PR. Poussez une branche, puis ouvrez une PR. » sous la liste des refs ; sans PR ni branche : l'état vide seul. Chaque check a son glyphe (✓ ✗ ⚠ ○ et le point cerclé d'encre), son état en mots, sa durée à droite, « Obligatoire » s'il l'est et le fond de DESIGN.md ; seul « En cours » est animé (`prefers-reduced-motion` l'arrête, shell.css).
- **Actions** : « Merger » envoie `pr_merge {number}` et « Ouvrir une PR » (branche poussée sans PR) envoie `pr_open {head}`. Merger inactif porte `aria-disabled` et sa raison (actions.js) ; il l'est aussi pendant une autre action de la file. Les refus du serveur (409) s'affichent par la zone d'erreur existante (`postIntent`).
- Registre du volet : `elementTypes` gagne `review` (une ligne) et une `projection.remote` (types contrôlés par le magasin comme pour le dépôt local).
- Tests : `tests/test_remote_view.py` (vrai git et vrai `github.json` : branches et « Ouvrir une PR », carte, ordre des checks, blocage, journal, PR courante, mergée, fichier illisible, annonces, durées) et `tests/test_remote_dom.py` (Node : ordre de la carte, glyphes, animation unique, raisons liées et sélection partagée, Merger actif et inactif, Ouvrir une PR, états vides, PR mergée, vue refusée, contrastes des deux thèmes, feuille sans couleur en dur ni `opacity`).

## `element_id` de la vue (pour 2.10, suivre un élément d'une vue à l'autre)

| Élément | `element_id` | Nœud (`data-element-id`) | Liens projetés (`links`) |
| --- | --- | --- | --- |
| Branche de `origin` | `ref:refs/remotes/origin/<branche>` (le même que l'étiquette `graph-remote-ref` du graphe) | bouton `.remote-ref` | `commit:<sha40>`, `pr:<n>` |
| PR | `pr:<n>` | bouton `.pr-pick` (titre de la carte) | `ref:…/origin/<head>`, `ref:…/origin/<base>` |
| Check | `check:<n>:<job_id>:<head_sha40>` | bouton `.pr-check` | `pr:<n>` |
| Revue | `review:<n>:<k>` | bouton `.review-pick` | `pr:<n>` |

- Une raison de `merge-blocked` n'a pas d'`element_id` propre : son bouton porte `data-link` (l'`element_id` de la cause : un check, `pr:<n>` ou la branche manquante) et sélectionne cet élément. Les boutons « Merger » et « Ouvrir une PR » ne sont pas des éléments sélectionnables.
- La sélection est celle du magasin (`selectionFor`), partagée avec les autres vues : sélectionner `ref:refs/remotes/origin/main` ici marque aussi l'étiquette du graphe dans la vue Dépôt local dès que celle-ci écoute la même sélection. Cette vue ne vide jamais une sélection dont elle n'est pas propriétaire.

## Décisions

- La vue est une projection (`views.remote`) et non un traitement de `pr_updated` : chaque opération republie `state_projected`, donc un rechargement ou une reprise du flux retrouve la vue entière. `pr_updated` garde sa charge ouverte du catalogue (3.2), le schéma n'a pas à changer.
- `contracts/remote.py` redéclare les quatre `Literal` d'états de `contracts/github.py` : `contracts/__init__` importe `views` avant de définir `element_id`, que `github.py` lui demande ; l'import direct créerait un cycle. Les deux déclarations sont de mêmes valeurs.
- Les revues viennent toutes du collègue simulé (3.4) : le badge « Collègue » est celui de `graph-actor`.
- Les heures du journal sont en UTC (« 14:32 UTC ») : le serveur les écrit, le front ne convertit rien.

## Reports

- Détail d'un check en échec (fichier:ligne en lien, règle), « Voir la sortie » (`tool-output`) et « Voir dans le pipeline » : stories du pipeline (épique 4 et suivantes). « Relancer le check » (outil en erreur) idem.
- Chronomètre de « En cours » (UX) : la durée n'existe qu'à la fin du job (`duration_ms`) ; il viendra avec le run du pipeline (AD-10).
- Onglet « Livraison » (v0.3).
- Correspondances au survol et sélection croisée avec le graphe : 2.10. Le dépôt local vide encore une sélection absente de sa vue (`repo.js`, `draw`) : à régler avec 2.10, qui rend la sélection partagée.
- Titre de PR saisi à l'ouverture : « Ouvrir une PR » n'envoie que la branche ; le titre par défaut est « PR n°n : branche ».
- Contrôles à faire dans un navigateur par Anaël : disposition de la rangée haute à 45 % (cartes longues, défilement vertical du volet), animation du point « En cours », contraste réel sur fond sombre, ordre de lecture au lecteur d'écran (cartes, checks, journal), focus après un clic sur Merger.

## Revue
