---
story: "9.1"
key: 9-1-se-situer-grâce-au-bandeau-de-la-chaîne
title: Se situer grâce au bandeau de la chaîne
status: review
branch: story/9-1-bandeau-chaine
ad: [AD-2, AD-7]
---

# Story 9.1 : Se situer grâce au bandeau de la chaîne

Source : `epics.md`, section « Story 9.1 » ; UX-DR32 ; `DESIGN.md` (`chain-band`, `chain-band-height`) ; `EXPERIENCE.md` (bandeau).

## Livré

- Serveur (`web/catalogue.py`) : `chain_body(station)` fournit les textes du bandeau (AD-2) : « Station 1 · Poste local », « Station 2 · PR et CI », « Station 3 · Sécurité et qualité », « Station 4 · Livraison », « Vous êtes ici », « CI | CD », frontière après la Station 3, station courante. `GET /api/workspaces/<id>` ajoute `chain` (null si le scénario ne déclare pas de `station` entre 1 et 4).
- Scénario (AD-7) : le champ `station` existait déjà dans le modèle ; `bac-a-sable-libre.A.yaml` déclare `station: 1`. Les gabarits d'exercice (empreintes de 2.11) restent inchangés.
- Front (ajouts sans toucher `layout.js` ni le calcul des volets) : `workspace.js` reçoit `chain` (option de `mountWorkspace`) et insère `buildChainBand` en tête de la grille de l'espace ; `main.js` le transmet. Station courante : classe `is-current`, `aria-current="step"`, fond `discipline-harness-soft`, trait bas, pilule « Vous êtes ici ». « CI | CD » encadré de deux traits `hosting-boundary` entre les Stations 3 et 4. Sans `chain`, rien ne change.
- CSS (`workspace.css`) : le bandeau (`chain-band-height`, 44 px au minimum) est la première rangée de la grille `.workspace`, sur toute la largeur (`grid-template-rows: auto minmax(0, 1fr)`). L'espace garde sa hauteur (`100vh - 230px`, `min-height: 520px`, comme sans bandeau) ; seule la rangée du panneau et des vues rétrécit, de la hauteur effective du bandeau (même s'il passe sur deux lignes) plus l'écart. À 640 px ou moins (une colonne), hauteur automatique et bandeau en tête de colonne. Entre 641 et 1279 px, la disposition à une vue agrandie de la 2.3 s'applique, bandeau inclus.
- Tests : `test_catalogue` (textes serveur, `chain` dans l'en-tête), `test_chain_band_dom` (Node : rendu, une seule station courante, ordre de la frontière, aucune vue masquée, menu Volets et zones F6 inchangés, absence de bandeau sans station), paires de contraste (`ink` sur `discipline-harness-soft`, trait et frontière sur `surface-raised`).

## Décisions

- Le bandeau n'est ni une zone F6 ni un élément du menu Volets (qui ne le gère pas).
- Les stations ne sont pas cliquables et « Carte ▾ » n'est pas rendu : ils appartiennent à la Story 9.2 (carte de la chaîne).
- Le bandeau est une `section` nommée contenant une liste ordonnée ; la frontière est un élément de liste de texte « CI | CD », masqué des technologies d'assistance (`aria-hidden`, la liste compte quatre stations) et lu comme description de la Station 4 (`aria-describedby`).
- Le scénario déclare `station` entre 0 et 4 (`le=4` ajouté) ; 0 ou absent : pas de bandeau.

## Reports

- Carte de la chaîne, bouton « Carte ▾ », stations cliquables, vues `inert` : Story 9.2.
- Noms des stations dans `CHAIN_STATIONS` (`web/catalogue.py`) : à déplacer dans `content/` avec la carte de la chaîne (Story 9.2), qui en aura besoin avec ses descriptions.
- À vérifier dans un vrai navigateur : rendu à 1280 et 1920 px ; bandeau sur deux lignes (fenêtre étroite ou zoom 200 %) sans débordement ni défilement de la page au-delà de l'existant ; hauteur effective des vues (`100vh - 230px` vient de la 2.3) ; lecture NVDA (« liste de 4 éléments », « étape actuelle », frontière annoncée sur la Station 4) ; thème sombre.

## Revue

Revue unique (Opus), sur la liste du second avis (Haiku), après rebase sur `main` (686e84a).

- medium · second avis 1 · corrigé · `.workspace.has-chain-band` à `100vh - 282px` avec `min-height: 520px` : la page défilait plus tôt qu'avant et les vues cessaient de rétrécir. Le bandeau devient la première rangée de la grille ; l'espace garde la hauteur et le seuil de défilement d'avant ; la constante `282px` disparaît.
- medium · second avis 2 · corrigé · bandeau sur deux lignes plus haut que 44 px dans un espace de hauteur fixe : débordement. La rangée `auto` absorbe la hauteur réelle ; le retour à la ligne est conservé (refusion, WCAG 1.4.10).
- low · second avis 3 · corrigé · « CI | CD » compté comme cinquième élément de la liste : `aria-hidden` sur la frontière, `aria-describedby` sur la Station 4.
- low · second avis 4 · corrigé en partie · `station: 7` accepté : `le=4` et test. Noms des stations en dur : reporté à la 9.2 (voir Reports) ; AD-2 est respecté, le serveur fournit les textes.
- low · second avis 5 · corrigé · assertions du test DOM affaiblies (suffixe, ensemble) : premier montage détruit et menu retiré, puis comparaison de listes exactes et non vides. Constat annexe : `destroy()` ne retire pas le menu Volets de l'en-tête ; sans effet en production (un seul montage par page), laissé en l'état.
- low · second avis 6 · corrigé · phrase « Sous 1280 px (colonne) » fausse (la colonne commence à 640 px) : section Livré réécrite.
