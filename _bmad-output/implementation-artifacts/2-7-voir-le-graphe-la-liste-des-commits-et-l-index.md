---
story: "2.7"
key: 2-7-voir-le-graphe-la-liste-des-commits-et-l-index
title: Voir le graphe, la liste des commits et l'index
status: review
branch: story/2-7-graphe-index
ad: [AD-2, AD-13, AD-17]
---

# Story 2.7 : Voir le graphe, la liste des commits et l'index

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.7 ». UX : DESIGN.md (`graph-*`, `commit-list`, `new-mark`, `staging-index`), EXPERIENCE.md (Graphe, Dépôt local).

## Livré

- `js/repo.js` : corps du volet « Dépôt local », tenu à jour par le magasin.
  - Graphe : une rangée de 28 px par commit, dans l'ordre des `nodes` du serveur ; un seul `<svg>` (`aria-hidden`) dessine les arêtes (`first_parent`, `merge`, en tirets vers un commit perdu) et les disques (14 px, trait `discipline-prompt`, tirets `muted` pour un perdu) à partir de `column` et de l'ordre des nœuds ; par-dessus, un `<button>` par commit couvre toute la rangée (disque, SHA, message : 28 px de haut). Son nom accessible est le `a11y_name_text` du serveur, mot pour mot ; `aria-pressed` porte la sélection.
  - Étiquettes (`RefLabel`) selon `kind` : `graph-head` (« HEAD » / « HEAD détachée », rectangle encre), `graph-branch` (pilule, icône poste), `graph-remote-ref` (double bord, icône serveur), `graph-tag` (rectangle à encoche, icône tag). Badges « Collègue » / « Agent » d'après `actor`. `new-mark` « Nouveau » sur un nœud ou une ref `new`, « Rétabli » sur `restored`. Commit perdu : « perdu · visible par reflog ».
  - `commit-list` : tableau SHA, Message, Auteur, Parents, Refs, État dans l'ordre des nœuds (celui de `git log --all --graph`) ; l'auteur vient de `repo.commits`, les parents sont les `short_sha` des nœuds. Le bouton « Liste » / « Graphe » est dans l'en-tête du volet (`pane-tools`), après Masquer et Agrandir.
  - `staging-index` : « Indexé », « Modifié, non indexé », « Non suivi » (groupes vides omis), lettre d'état git en code, nom accessible « Indexé : a.txt, ajouté ». Un clic sélectionne et ne fait rien d'autre (aucun appel au serveur).
  - Le focus et l'unique arrêt de tabulation de la vue survivent à une nouvelle projection ; une sélection dont l'élément a disparu est effacée.
- `js/selection.js` : sélection unique par magasin, partagée par le graphe, la liste et l'index (la base des correspondances d'UX-DR25, hors périmètre ici).
- Écart de 2.3 résolu : chaque volet déclare `projection: { <vue>: (view) => [element_id…] }` à son enregistrement (`panes.js`) ; `acceptViews` (`store.js`) contrôle les types de ces `element_id` contre `elementTypes` du volet et refuse la vue entière sinon (`graph` et `staging` → « Dépôt local »). Les clés qu'aucun volet ne déclare (`repo`, `prompt`, `announce_text`) passent. L'ancienne forme `views[volet].elements[{type}]` disparaît. Types du volet « Dépôt local » : `commit`, `ref`, `tag`, `path` (le `file` de 2.3 n'existe pas dans la grammaire d'AD-2 ; le volet Code le remplace par `path` aussi).
- Annonce (UX-DR37, FR-4) : le magasin garde `announce` (`announce_text` de `state_projected`, avec `command` vrai pour une opération de l'apprenant, faux pour l'ouverture et pour un changement externe annoncé par `external_change`). La région `role="status"` du panneau Scénario dit « Commande terminée. Vues mises à jour : … » ; une annonce identique est relue (vidage avant écriture).
- `css/repo.css` (jetons seulement), `index.html` (une ligne), `dom.js` (`svg()`), `tests/js/minidom.mjs` (`createElementNS`).
- Tests : `tests/test_repo_dom.py` — projections réelles (`build_views` sur un vrai dépôt : fusion `--no-ff`, tag annoté, `origin/main`, index en trois groupes, HEAD détachée, commit perdu) posées dans le magasin, sous Node : nœuds, arêtes, refs, icônes, marques, nom accessible repris du serveur, HEAD détachée, perdu, badges, sélection partagée graphe/liste, `commit-list`, index sans appel réseau, état vide, vue refusée, annonces (commande, externe, ouverture), focus conservé, contrastes WCAG clair et sombre des paires ajoutées, feuille sans couleur en dur. `test_layout_js.py` suit la nouvelle forme de `acceptViews`.

## Décisions

- Une rangée par commit (comme `git log --graph` et la maquette) : le rang du serveur n'est pas une ordonnée, car deux commits de rang égal peuvent exister ; l'ordonnée est l'index dans `nodes`. L'arête part du disque de l'enfant, descend en diagonale d'une rangée vers sa `column`, longe cette colonne, et rejoint le parent par une diagonale d'une rangée ; si les deux rangées se suivent, un seul segment.
- Le bouton Liste/Graphe est le dernier outil de l'en-tête pour garder « Masquer » comme premier arrêt du focus itinérant (test 2.3 inchangé).
- Sélection : persistante et unique, effacée par un nouveau clic ; elle vit côté front (état de présentation, pas d'état du dépôt, AD-2).
- Le volet « Terminal » (vue `prompt`) n'est pas câblé ici : 2.4 y déclare sa `projection`.

## Reports

- Lettres d'état (`M`, `A`, `D`, `R`, `C`, `T`, `U`, `?`) dites en toutes lettres dans le nom accessible de l'index par une table du front, faute de `a11y_name_text` dans `StagingItem` : à passer côté serveur avec le catalogue d'explications (AD-2).
- Cas non rendus (stories de désignation et de correspondances) : tirets `primary` des éléments désignables (Epic 5), liaison entre vues et « + Nom · lié » (UX-DR25), explication attachée « i » / Entrée (NFR-13, catalogue d'explications), `terminal-lit`.
- Phrase « Arbre de travail propre : rien à indexer. » : texte du front quand des commits existent et que l'index est vide ; à confirmer par l'UX.
- Quand deux commits d'un même rang précèdent le parent dans l'ordre d'affichage, une arête qui longe la colonne d'un commit de même rang que son parent peut le frôler : le serveur garantit l'absence de croisement entre les rangs, pas entre les rangées d'un même rang. À regarder dans un vrai navigateur.
- Rendu réel non vérifiable sous la doublure de DOM : alignement des voies sur les boutons, tailles, focus visible, défilement dans les deux sens, lecture au lecteur d'écran, thème sombre.
