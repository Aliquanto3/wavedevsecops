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
- Bandeau `role="alert"` : le point de vie est interrogé toutes les 5 s ; au premier échec le bandeau dit « WaveDevSecOps ne répond plus. Relancez-le ; votre progression est enregistrée. » et toutes les actions enregistrées deviennent inactives (`actions.js`).
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
- Contrastes des nouvelles paires non recalculés (jetons repris tels quels de DESIGN.md).
- Zoom 400 % : repli sur une colonne limité à l'en-tête et à `main` ; panneau et catalogue à traiter avec leurs stories.
