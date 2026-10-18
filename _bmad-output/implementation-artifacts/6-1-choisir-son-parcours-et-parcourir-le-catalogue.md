---
story: "6.1"
key: 6-1-choisir-son-parcours-et-parcourir-le-catalogue
title: Choisir son parcours et parcourir le catalogue
status: review
branch: story/6-1-parcours-catalogue
ad: [AD-2, AD-5, AD-14, AD-16]
---

# Story 6.1 : Choisir son parcours et parcourir le catalogue

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 6.1 » ; FR-9, FR-16, UX-DR4 (`path-menu`), UX-DR29 ; spine AD-2, AD-5, AD-14, AD-16. Étend le catalogue de la 2.3 sans le remplacer ; s'appuie sur `ProgressStore` (4.2) et sur le registre d'outils (1.4).

## Livré

- **Choix du parcours.** `GET /api/shell` expose `tracks[{key, label, text}]` (source unique : `web/shell.py::TRACKS`, `llm` puis `no_ai`). Le navigateur mémorise seulement la clé choisie (`localStorage`, `wds.track`, lecture et écriture protégées) ; sans elle, ou si le serveur ne la connaît plus, on est au premier passage. `path-picker` (groupe radio de deux pilules, une phrase par option) et `path-menu` (sélecteur de l'en-tête, sur tous les écrans) posent le même choix. Ouvrir un espace fait de son parcours le parcours choisi.
- **Catalogue par parcours.** `GET /api/catalogue[?track=llm|no_ai]` : sans parcours, `track: null`, `sections: []` et `picker.question` (« Choisissez votre parcours. Les deux suivent la même progression ; seul le code d'exercice change. ») : le front n'affiche que `path-picker`. Avec un parcours inconnu : 422. Avec un parcours : la section « Socle git » ne garde que les scénarios dont `tracks` contient ce parcours, dans l'ordre conseillé (FR-9), numérotés (`number`, disque du front), une colonne par mode (`modes[]`, A puis B).
- **États (AD-14).** Chaque mode porte `state` (`todo`, `in_progress`, `done`), `state_text` (« À faire », « En cours », « Terminé ») et `detail_text` (« n sur m du premier coup · k indice(s) », partie « n sur m » omise sans quiz, vide tant que rien n'est commencé), lus par `ProgressStore.all_progress()` pour le parcours choisi seulement : chaque parcours garde sa progression. Le front ne calcule rien.
- **Indisponibilité (AD-16).** Un mode dont un outil de `tools` ne se résout pas (`toolrun.resolve`, une sonde par outil et par requête) a `available: false` et `unavailable{tool_id, tool_label, text: "⊘ Indisponible", needs_text: "Nécessite <outil>", diagnostic_text: "Voir le diagnostic", diagnostic_path: "/diagnostic"}` ; le libellé vient de `content/diagnostic.yaml`. La carte n'a pas de bouton ; `POST /api/open` refuse ce mode en 409 (texte nommant l'outil et renvoyant au diagnostic).
- **Ouverture.** `openMode` poste `track` (le parcours choisi). Chaque scénario prépare son propre état initial (`setup`), indépendamment des autres ; un espace par parcours, scénario et mode (AD-5) : changer de parcours depuis un scénario ramène au catalogue du nouveau parcours, l'ancien espace reste à son étape.
- Front : `web/static/js/track.js` (nouveau : mémorisation, `path-menu`), `catalogue.js` (picker, cartes à disque, colonnes de mode, lien du diagnostic), `main.js`, `index.html` (`<select id="path-menu">`), `css/catalogue.css` (nouveau, sans toucher `workspace.css`).
- Tests : `tests/test_catalogue_parcours.py` (premier passage, ordre et numéros, états et scores séparés par parcours, texte de détail, outil absent, 422, refus d'ouverture, deux espaces), `tests/test_catalogue_dom.py` (Node : picker seul, cartes, carte indisponible sans bouton, `path-menu`, mémorisation résistante, `track` posté) ; `tests/test_catalogue.py` réaligné (`?track=`, champs de mode).

## Contrat du catalogue (pour 6.2, 6.4 et 9.3)

- **Ordre conseillé** : `web/catalogue.py::SOCLE_ORDER` = `add-commit, push-pull, branche, pr-merge, conflit, stash, rebase, recuperation`. **6.2 et 6.3 nomment leurs `scenario_id` ainsi** (fichiers `content/scenarios/<id>.<A|B>.yaml`, `section: socle-git` ou absente, `catalogue: true`). Un id non livré est absent ; un scénario hors liste vient après, par ordre alphabétique (aujourd'hui `bac-a-sable-libre`).
- **Forme d'un mode** : `{mode, tracks, track, workspace_id, state, state_text, detail_text, available[, unavailable]}`. 6.4 (« Reprendre ») ajoute au mode concerné `resume{step_number, step_total}` et un bouton à côté de « Ouvrir » dans `modeColumn` (`catalogue.js`) ; le dernier scénario ouvert se lit dans `progress`/`run.json`, pas dans le navigateur.
- **Sections** : `sections[]` ne contient que « Socle git ». 9.3 ajoute « Stations » en poussant une section de plus dans `catalogue_body` (clé, titre, sous-titres « Station n · Nom » via `scenario.station`) et son rendu dans la boucle de `renderCatalogue` ; le filtre `scenario.section not in (None, SOCLE_SECTION)` est le point à ouvrir. La disponibilité (`available`/`unavailable`) et l'état sont déjà calculés pour tout mode, quelle que soit la section.
- **Parcours** : `shell.TRACKS` est la seule liste ; `track` se passe en paramètre de requête (catalogue) et dans le corps (`/api/open`).

## Décisions

- Le parcours choisi est une préférence d'affichage : navigateur seulement (AD-2 le tolère comme la disposition) ; aucun fichier de données ni réglage. Contrepartie : un autre navigateur redemande le parcours. « Reprendre » (6.4) ne s'en sert pas.
- L'ordre vit dans une constante Python plutôt que dans un YAML : il ne change qu'avec le contenu livré, et les tests le figent.
- Une carte est un scénario ; l'indisponibilité est par mode (les outils d'un mode B peuvent différer).

## Reports

- Contrôles navigateur (Anaël) : pilules et leur focus, `path-menu` aligné dans l'en-tête, largeur des colonnes de mode sur petit écran, disque numéroté, retour au catalogue après changement de parcours depuis un espace, rendu sombre.
- Sections « Stations » et « Savoir en parler », « Reprendre », pied « Exporter mon rapport » : stories 9.3, 6.4, 6.5.
- Aucun scénario du socle n'existe encore hors le bac à sable libre : l'ordre se vérifiera avec 6.2 et 6.3.
- Page Diagnostic : le lien « Voir le diagnostic » mène à `/diagnostic` sans ancre sur l'outil.
