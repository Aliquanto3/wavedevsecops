---
story: "9.2"
key: 9-2-déplier-la-carte-de-la-chaîne
title: Déplier la carte de la chaîne
status: review
branch: story/9-2-carte-chaine
ad: [AD-2]
---

# Story 9.2 : Déplier la carte de la chaîne

Source : `epics.md`, section « Story 9.2 » ; UX-DR32, UX-DR36 ; `DESIGN.md` (`chain-map`) ; `EXPERIENCE.md` (carte dépliée).

## Livré

- Contenu (AD-2) : `content/chain.yaml` porte tous les textes de la chaîne (noms des stations, « Vous êtes ici », « CI | CD », « Carte ▾ », « Bientôt », libellés), les outils (identifiants de `tools.toml`), les barrières et leurs liens (`check`, `hook`, `term`). `CHAIN_STATIONS` disparaît de `web/catalogue.py` (report de la 9.1) ; `chain_body(station, settings)` lit le fichier et ajoute `map` et, par station, `description`, `delivered`, `tools`, `barriers`. Le contenu est validé par un schéma pydantic (`ChainTexts` : champs inconnus refusés, stations numérotées 1 à n, `boundary_after` dans la plage, libellé pour chaque type de lien) ; la disponibilité d'un outil vient de `toolrun.resolve` (sonde du diagnostic), dans un fil (`asyncio.to_thread`). Fichier absent ou invalide : journalisé avec le champ fautif, pas de bandeau, pas d'exception.
- Front : nouveau module `js/chain.js` (bandeau et carte, hors de `layout.js` et du calcul des volets) ; `workspace.js` l'importe, lui passe `[panneau Scénario, vues]` à rendre `inert`, et ferme la carte sur Échap (après le menu Affichage) et au `destroy()`. `buildChainBand` reste exporté par `workspace.js`.
- Comportement : « Carte ▾ » (`aria-expanded`, `aria-controls="chain-map"`) ou un clic sur une station déplie `chain-map` ; le focus va sur le titre de la zone demandée (station courante pour le bouton) ; les vues dessous sont `inert` ; Échap ferme et rend le focus au bouton ; le bouton referme aussi. Un clic sur une autre station carte ouverte déplace le focus. Sans `chain.map`, le bandeau reste celui de la 9.1 (texte seul).
- Carte : une zone par station (liste de régions nommées), outils et barrières en listes. Un nœud de barrière (bouton `aria-pressed`) affiche, au clic, à Entrée/Espace ou au survol, ses checks, hooks et termes dans une zone `aria-live` : l'information n'est donc jamais au seul survol. Outil indisponible : tirets et « (indisponible) » ; station non livrée (Station 4 en v0.2) : « Bientôt » en tirets, sans outil ni barrière.
- CSS : carte absolument posée sous le bandeau (`top: 100%`), par-dessus les vues, sans les déplacer, avec le relief d'overlay ; zones en grille adaptative.
- Tests : `test_catalogue` (carte fournie par le serveur, fichier absent), `test_chain_band_dom` (Node : ouverture bouton et station, `aria-expanded`/`aria-controls`, focus, `inert`, Échap, survol, tirets, « Bientôt », station courante, menu Volets inchangé, `destroy` rend les vues interactives).

## Décisions

- Les liens (checks, hooks, termes) sont du texte projeté depuis `content/chain.yaml`, sans destination : les vues Checks, le glossaire et les hooks ne sont pas encore livrés. Un champ de cible (`href` ou identifiant de volet) s'ajoutera à `links` quand elles le seront.
- `available` est calculé par le serveur depuis la sonde du poste (`toolrun.resolve`, environ 150 ms par ouverture d'espace), plus déclaré dans le contenu (revue).
- La carte n'est ni une zone F6 ni un élément du menu Volets (cohérent avec la 9.1) ; Tab saute les vues `inert`.

## Reports

- Cibles des liens des nœuds de barrière (vues Checks, glossaire, hooks) quand elles existent  ; contenu de la Station 4 (jalon v0.3).
- `destroy()` ne retire toujours pas le menu Volets de l'en-tête (constat de la 9.1).
- À vérifier dans un vrai navigateur : carte posée sur les vues à 1280/1920 px et à une colonne (hauteur, défilement interne `70vh`), thème sombre, tirets lisibles, anneau de focus visible sur zones et nœuds, lecture NVDA (région « Carte de la chaîne », listes, état pressé, annonce des liens), fermeture par Échap avec focus rendu au bouton.

## Revue

- Medium, second avis M1 : corrigé. `chain.yaml` mal formé levait `KeyError` dans `chain_body`, donc un 500 sur `GET /api/workspaces/<id>` et un espace qui ne s'ouvrait plus. Schéma pydantic `ChainTexts` (dans `web/catalogue.py`), message journalisé en français avec le chemin du champ, six cas testés (`test_chaine_invalide_journalisee_sans_bandeau`).
- Medium, second avis M2 : corrigé. `pip-audit` était déclaré `available: false` alors qu'il est une dépendance installée (`pyproject.toml`), et `gitleaks` déclaré présent alors qu'il manque sur ce poste. `available` vient maintenant de `toolrun.resolve` ; test avec une sonde simulée, l'oracle d'intégration utilise les mêmes réglages que le serveur.
- Low, second avis L8 : corrigé avec M2. `chain_body` (lecture disque et sondes) passe par `asyncio.to_thread`, comme le reste de la route.
- Low, second avis L9 : corrigé. Le focus de l'état fermé était comparé à lui-même ; il est maintenant vérifié hors des zones de la carte.
- Low, second avis L3 : reporté (déjà dans Reports). Les vues Checks, glossaire et hooks ne sont pas livrées, donc aucune cible n'existe encore.
- Low, second avis L4 : rejeté. Le survol sélectionne la barrière comme le clic, et `aria-pressed` suit la sélection affichée. L'annonce `polite` ne se déclenche que sur une action de la souris, qu'un lecteur d'écran n'émet pas.
- Low, second avis L5 : rejeté. `listitem` accepte un nom d'auteur (ARIA 1.2) ; le nom de la zone sert à la navigation par listes.
- Low, second avis L6 : rejeté. `mountWorkspace().destroy()` appelle `chainView.close(false)`, ce qui lève l'`inert` ; le bandeau part avec `container.replaceChildren` au montage suivant.
- Low, second avis L7 : rejeté. Le comportement est voulu par la spec (journalisé, sans bandeau) ; un contenu invalide est maintenant signalé avec le champ fautif.
- Complexité : 0 constat. La carte est construite une fois, et `select` parcourt les boutons de barrière (une dizaine).
- À vérifier dans un vrai navigateur (inchangé) : voir Reports.
