---
story: "1.3"
key: 1-3-coquille-d-interface-wavestack
title: Afficher la coquille d'interface avec l'identité WaveStack
status: review
branch: story/1-3-coquille-ui
ad: [AD-13, AD-19, AD-2, convention Front]
---

# Story 1.3 : Afficher la coquille d'interface avec l'identité WaveStack

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 1.3 ». UX : DESIGN.md (jetons), EXPERIENCE.md (en-tête).

## Livré

- `web/static/` (modules ES sans build ni framework) : `index.html`, `css/tokens.css` (les 110 jetons de couleur de DESIGN.md, clair et sombre, `terminal-*`, `focus-on-ink`, typographie en 10 rôles, espacements, arrondis, relief plein), `css/fonts.css`, `css/shell.css`, `js/` (`main`, `display`, `nav`, `health`, `actions`, `panes`, `theme-init`).
- Polices WOFF2 locales dans `static/fonts/` (Fredoka et JetBrains Mono variables, Atkinson Hyperlegible 400, 400 italique et 700), sous-ensemble latin, avec les trois licences `OFL-*.txt`.
- `web/shell.py` : table des surfaces avec le jalon qui livre chacune ; `web/app.py` : routes des surfaces livrées (`/`, `/diagnostic`) qui servent la coquille, `GET /api/shell` (surfaces déclarées par le serveur), `GET /api/health` (sous cookie), `/static`, en-têtes `Content-Security-Policy` (tout en `'self'`, `default-src 'none'`), `nosniff`, `Referrer-Policy: no-referrer`, `no-store` sur `/api/`.
- Menu « Affichage ▾ » : `theme-picker` (select natif Système, Clair, Sombre) et « Réduire les animations ». Application immédiate, mémorisation dans `localStorage` (clé `wds.display`), application avant le premier rendu (`theme-init.js`). `prefers-reduced-motion` et la case coupent transitions et animations.
- Bandeau `role="alert"` : le point de vie est interrogé toutes les 5 s (délai de 4 s, une requête à la fois) ; au deuxième échec consécutif le bandeau dit « WaveDevSecOps ne répond plus. Relancez-le ; votre progression est enregistrée. » et toutes les actions enregistrées deviennent inactives (`actions.js`).
- Boutons : quatre variantes (`btn-primary`, `btn-secondary`, `btn-reset`, `btn-danger`). Un bouton inactif porte `aria-disabled` et sa raison dans un `span` visible relié par `aria-describedby`, reste focalisable, clic neutralisé ; aucune opacité sur le texte, aucun texte sous 12 px.
- `js/panes.js` : registre des volets (`registerPane({id, title, render, elementTypes…})`, `listPanes`, `renderPanes`) ; la disposition ne connaît aucune vue. Texte d'état vide tant qu'aucune n'est enregistrée.
- `tests/static_rules.py` : le contrôle AD-13 (2) s'applique enfin à de vrais fichiers ; les licences `static/fonts/OFL-*.txt` (qui citent des adresses web) sont exclues, tout autre fichier reste contrôlé (test dans `test_offline_rules.py`).
- `tests/test_shell_ui.py` : 19 tests (routes, cookie, en-têtes, fichiers servis, WOFF2, jetons comparés à DESIGN.md, absence d'URL externe, textes attendus).

## Décisions

- Une seule page HTML pour toutes les surfaces ; la surface courante vient de `location.pathname` et de `/api/shell`. Le contenu des surfaces arrive avec leurs stories (Catalogue : 3.x ; Diagnostic : 1.4+).
- `tokens.css` est généré depuis le front matter de DESIGN.md ; un test compare chaque jeton, ce qui détecte une dérive.
- Le thème suit le schéma de WaveStack : `:root` (clair), `@media (prefers-color-scheme: dark)` gardé par `:root:not([data-theme="light"])`, et `:root[data-theme="dark"]`.
- Polices en latin seulement (le français n'a besoin de rien d'autre) ; poids Fredoka 300 à 700 et JetBrains Mono 100 à 800 via fichier variable.
- CSP stricte sans `unsafe-inline` : le front n'utilise ni style ni script en ligne.
- Pas de `Settings` ajouté : le jalon courant est une constante de `web/shell.py` (`create_app(milestone=…)` pour les tests). Pas de changement de `pyproject.toml` (`uv_build` embarque le dossier `static/`).

## Reports

- `diagnostic-badge`, `path-menu` et « Volets ▾ » du `site-nav` : leurs données arrivent avec le diagnostic (1.4), le parcours (catalogue) et les vues (Epic 2). Seuls la marque, les liens et « Affichage ▾ » sont posés.
- Pas de test de navigateur réel : le comportement du front (menu, bandeau, thème) est vérifié par fichiers et textes ; une vérification visuelle reste à faire par l'apprenant ou en revue.
- Zoom 400 % : repli sur une colonne limité à l'en-tête et à `main` ; panneau et catalogue à traiter avec leurs stories.

## Revue

Revue unique (Opus) après rebase sur `main` (story 1.4, sans conflit), avec la liste du second avis (Haiku).

- medium · second avis 1 · corrigé · `health.js` : `fetch` sans délai ni garde ; un serveur figé ne déclenchait jamais le bandeau et les requêtes s'empilaient. Ajout d'un `AbortController` (4 s) et d'une garde de requête en cours ; test Node `test_shell_js.py` (serveur figé détecté, une seule requête en vol), qui échoue sur l'ancien code.
- medium · second avis 2 · corrigé (vérification) · en v0.1 la coquille n'a aucune action métier : le critère se lit comme le mécanisme prêt pour les stories suivantes, et `setOffline` est bien branché sur le point de vie dans `main.js`. Il n'était prouvé que par des sous-chaînes ; test Node sur doublure DOM : `aria-disabled`, raison visible reliée par `aria-describedby`, clic neutralisé, retour à l'état propre de chaque bouton.
- low · second avis 3 · corrigé en partie · un raté isolé faisait basculer le bandeau ; il faut désormais deux échecs consécutifs. Le 401 reste traité comme un arrêt : il ne survient qu'après une relance (nouvelle session), et « Relancez-le » reste la bonne consigne.
- low · second avis 4 · corrigé · `.app-alert:empty` n'est plus en `display:none` (padding et bordure nuls) : la région `role=alert` reste dans l'arbre d'accessibilité et l'annonce part.
- low · second avis 5 · rejeté · l'exclusion vise un `.txt` `OFL-*` dans `static/fonts/` : jamais chargé ni exécuté par la page, et tout `.js`, `.css` ou `.html` reste contrôlé (test dédié).
- medium · revue · corrigé · lien d'évitement illisible en thème sombre (`on-ink` sur `ink` : 1,18:1). Fond passé à `ink-fill`. Test de contraste WCAG ajouté (`test_shell_ui.py`) sur les paires texte/fond de `shell.css` et celles du tableau de DESIGN.md, en clair et en sombre.
- reporté · revue · aucun navigateur réel lancé : vérifier à l'œil le thème sombre, le menu « Affichage ▾ », le bandeau (arrêter le serveur, attendre ~10 s) et son annonce par un lecteur d'écran (NVDA).
