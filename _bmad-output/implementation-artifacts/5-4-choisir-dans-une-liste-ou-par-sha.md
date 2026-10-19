---
story: "5.4"
key: 5-4-choisir-dans-une-liste-ou-par-sha
title: Choisir dans une liste ou par SHA
status: review
branch: story/5-4-liste-sha
ad: [AD-2, AD-17]
---

# Story 5.4 : Choisir dans une liste ou par SHA

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.4 » ; contrat serveur : spec 5.2 ; mode armé et champ SHA : spec 5.3.

## Livré

- `designation.js` (ajouts dans le bloc de désignation) :
  - `collectDesignables(views)` : liste, groupée par vue (Graphe, Index, Distant), de tout ce que la projection marque `designable === true` (commits, refs, fichiers de l'index, branches distantes, PR, contrôles, avis). Le front ne décide de rien (AD-2).
  - « Choisir dans la liste ▾ » (`aria-expanded`, `aria-controls`) ouvre `designate-list` : 240 px au plus, défilement interne, icône de type, SHA court et sujet pour un commit, champ « Filtrer par nom, SHA ou chemin » (insensible à la casse, sur libellé, `element_id` et SHA complet). L'élément choisi porte « choisi » (`aria-pressed="true"`) ; un clic dessus ne fait rien. Les types non attendus par l'étape sont ignorés. Les refs deviennent ainsi désignables au clavier (report de 5.3). Échap dans le filtre referme la liste (sauf en mode armé, où Échap désarme).
  - Aperçu en direct : à partir de 7 caractères (anti-rebond de 250 ms), `resolve_sha` ; le commit s'affiche « `a3f9d21` · Add config · Agent » en `role="status"`, avec « Placer dans la case » (Entrée aussi, sans seconde requête). Inconnu, ambigu ou type refusé : `aria-invalid`, message du serveur en `role="alert"`, rien n'est envoyé (aucun essai consommé). Réponses périmées (frappe ou étape changées) ignorées.
- Serveur : texte du 404 de `resolve_sha` aligné sur l'AC : « Aucun commit ne correspond à ce SHA dans le bac à sable. » (suivi de l'invitation à désigner dans le graphe).
- `workspace.css` : ajout en fin de fichier. Tests : 3 tests Node dans `tests/test_designation_dom.py`.

## Reports

- Contrôles dans un navigateur réel pour Anaël : hauteur et défilement de la liste (240 px), contraste de « choisi » en clair et en sombre, ordre de Tab (bouton liste, filtre, éléments, SHA, Placer, Valider), annonce de l'aperçu au lecteur d'écran, comportement avec les vues Code et terminal (sans désignables pour l'instant).
- Navigation aux flèches dans la liste : non faite, Tab suffit (boutons natifs) ; à revoir si la liste devient longue.
