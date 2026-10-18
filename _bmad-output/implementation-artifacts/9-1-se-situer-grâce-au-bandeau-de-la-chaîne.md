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
- Front (ajouts sans toucher `layout.js` ni le calcul des volets) : `workspace.js` reçoit `chain` (option de `mountWorkspace`) et insère `buildChainBand` avant la disposition ; `main.js` le transmet. Station courante : classe `is-current`, `aria-current="step"`, fond `discipline-harness-soft`, trait bas, pilule « Vous êtes ici ». « CI | CD » encadré de deux traits `hosting-boundary` entre les Stations 3 et 4. Sans `chain`, rien ne change.
- CSS (`workspace.css`) : bandeau de `chain-band-height` (44 px) ; la hauteur de l'espace diminue de cette hauteur plus l'écart, seul effet sur la disposition. Sous 1280 px (colonne), hauteur automatique inchangée.
- Tests : `test_catalogue` (textes serveur, `chain` dans l'en-tête), `test_chain_band_dom` (Node : rendu, une seule station courante, ordre de la frontière, aucune vue masquée, menu Volets et zones F6 inchangés, absence de bandeau sans station), paires de contraste (`ink` sur `discipline-harness-soft`, trait et frontière sur `surface-raised`).

## Décisions

- Le bandeau n'est ni une zone F6 ni un élément du menu Volets (qui ne le gère pas).
- Les stations ne sont pas cliquables et « Carte ▾ » n'est pas rendu : ils appartiennent à la Story 9.2 (carte de la chaîne).
- Le bandeau est une `section` nommée contenant une liste ordonnée ; la frontière est un élément de liste de texte « CI | CD ».

## Reports

- Carte de la chaîne, bouton « Carte ▾ », stations cliquables, vues `inert` : Story 9.2.
- À vérifier dans un vrai navigateur : rendu à 1280 et 1920 px, retour à la ligne du bandeau sous ~900 px, hauteur effective des vues (`100vh - 230px` est une estimation de l'existant), thème sombre.
