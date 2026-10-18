---
story: "2.3"
key: 2-3-afficher-la-disposition-principale-et-gérer-les-volets
title: Afficher la disposition principale et gérer les volets
status: review
branch: story/2-3-disposition-volets
ad: [AD-2, AD-17]
---

# Story 2.3 : Afficher la disposition principale et gérer les volets

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.3 » ; UX : `EXPERIENCE.md` (Disposition principale, Masquage, Responsive) et `DESIGN.md` (`pane`, `pane-chip`, `pane-resize-handle`, `pane-menu`).

## Livré

- Serveur (`web/catalogue.py`, ajouts ciblés dans `web/app.py`) :
  - `GET /api/catalogue` : section « Socle git » (scénarios de `content/scenarios/` sans `section` ou en `socle-git`), avec titre, modes, parcours et `workspace_id` du parcours par défaut (sans IA si le scénario le propose). Un YAML invalide est ignoré et journalisé.
  - `POST /api/open {scenario_id, mode, track?}` : prépare l'espace par `WorkspaceManager.create` (202, `preparing: true`) ou rouvre un espace existant (200) ; 404 scénario inconnu, 422 corps illisible ou parcours non proposé, 409 refus de la file. Derrière cookie et `Origin` (AD-19).
  - `GET /api/workspaces/<id>` : titre, mode et parcours (en-tête de l'espace après rechargement) ; `GET /espace/<id>` sert la coquille.
- Front (modules ES sans build, `web/static/`) :
  - `panes.js` : registre étendu sans refonte (`row`, `rowShare`, `share`, `foldRank`, `scroll`, `terminal`, `empty`) ; `assertElementType(paneId, type)` refuse un type d'`element_id` non déclaré. Le rendu DOM quitte `panes.js` (il ne contenait que l'ancien conteneur vide).
  - `views.js` : enregistre Dépôt local, Distant + PR, Code, Terminal avec sous-titres, types d'`element_id` et état vide titré de l'UX.
  - `layout.js` (logique pure, testée sous Node) : parts par défaut (rangées 40/33/27, largeurs 55/45), masquage avec une vue visible au moins, taille minimale 240 x 160, redimensionnement par pas de 16 px, valeurs ARIA des poignées, repli (`effectiveLayout`), focus itinérant, zones F6, mémorisation `localStorage` sous try/catch (`hidden`, `rows`, `widths` ; le volet agrandi ne se mémorise pas).
  - `workspace.js` : panneau Scénario (440 px, « Préparation du bac à sable… » en `role="status"`), vues du registre avec `pane-step`, titre, sous-titre, « — », ⛶ (Échap revient), puces « + Nom », poignées `role="separator"` (souris, flèches par 16 px, double-clic = proportions par défaut), menu « Volets ▾ » (cases, Élargir, Réduire), Tab (un arrêt par vue, flèches dans la vue), F6, Échap (menu Volets puis vue agrandie ; dans le terminal, focus au titre), focus après « — » (puce) et après réaffichage (titre).
  - `store.js` : magasin de projection (AD-17) : `GET …/state` puis SSE repris à `<boot_id>:<seq>`, événements appliqués dans l'ordre de `seq`, `resync_required` ou `boot_id` différent relit l'état ; une projection dont un élément a un type non déclaré est écartée et comptée dans `problems`.
  - `catalogue.js` + `main.js` : l'accueil affiche le catalogue ; un clic sur « Ouvrir en mode A » appelle `/api/open` puis va à `/espace/<id>`. `workspace.css` : disposition, poignées (zone de prise de 32 px), puces, catalogue, repli.
- Repli : sous 1920 x 1080, les vues se replient en puces par `foldRank` croissant (Distant + PR, puis Code ; Dépôt local et Terminal restent) tant que 240 x 160 ne tient pas ; sous 1280 px de large, une seule vue à droite du panneau ; à 640 px ou moins, une colonne (panneau au-dessus). Seules les vues déclarées `scroll: "both"` (Dépôt local, Code, Terminal) défilent dans les deux sens.
- Tests : `test_layout_js` (Node : proportions, masquage, minimum, pas de 16 px, reset, repli, F6 et flèches, mémorisation en échec, registre, magasin et reprise SSE), `test_catalogue` (vrai serveur et vrai git : catalogue, ouverture, réouverture, refus, `Origin`), `test_workspace_ui` (textes de l'UX, la disposition ne nomme aucune vue), paires de contraste des puces dans `test_shell_ui`.

## Décisions

- Le catalogue 2.3 est la première version de 6.1 : pas de choix de parcours, ni d'états, ni de cartes indisponibles ; le parcours sans IA est ouvert par défaut. Les gabarits d'exercice (`gabarit-*`, empreintes de référence de 2.11) portent `catalogue: false` : scénarios internes, absents du catalogue et refusés par `/api/open` (revue).
- Éléments des projections : une vue de `state_projected.views[<pane_id>]` peut porter `elements: [{type, …}]` ; seul le contrôle du type est posé ici, les schémas viennent avec 2.6.
- Proportions stockées en parts relatives (jamais en px) ; un volet masqué garde sa part, donc il revient « à sa dernière taille ». Le redimensionnement convertit les tailles mesurées en parts sans fausser celles des volets masqués.
- Le panneau Scénario ne se masque pas (`[ASSUMPTION]` de l'UX). Un repli automatique n'est pas mémorisé : seul le masquage voulu l'est ; une puce de vue repliée la réaffiche et replie une autre vue à sa place.
- Ordre de repli sans notion d'étape : `foldRank` du registre (« les vues que l'étape n'utilise pas » viendra avec les étapes, UX question ouverte 3).
- Les poignées restent des arrêts de tabulation propres (séparateurs ARIA focalisables), en plus d'un arrêt par vue.

## Reports

- Vérification dans un vrai navigateur (pas de navigateur dans cette session) : glisser à la souris, tailles réelles à 1920 x 1080 / 125 % / 400 %, ordre de Tab et lecteur d'écran, apparence des poignées et des puces. Un essai sous jsdom (hors dépôt) a confirmé l'enchaînement des actions DOM (masquer, puce, focus, agrandir, Échap, flèches, F6, menu).
- Contenu réel des vues (graphe, PR, éditeur, terminal), « + Nom · lié » et vues liées : stories 2.5 à 2.8, 3.x.
- Menu Volets : sa position dans l'en-tête à côté de `path-menu` (6.1) à revoir quand celui-ci existera.
- Écran 6.1 : choix du parcours, états des cartes, cartes indisponibles, « Reprendre ».
- Interruption du `setup` quand la page se ferme pendant la préparation : comportement 2.2 inchangé.

## Revue

Revue unique (Opus), sur 35841d3, avec la liste du second avis (Haiku).

| Sévérité | Source | Constat | Suite |
|---|---|---|---|
| medium | second avis 1 | `gabarit-sans-ia.A` et `gabarit-llm.A`, scénarios internes, proposés au catalogue | corrigé : champ `catalogue: bool = True` du modèle de scénario, `catalogue: false` sur les deux gabarits, filtrés du catalogue et de `/api/open` (404) ; `test_catalogue` mis à jour |
| medium | second avis 2 | `test_workspace_ui` ne vérifiait les critères DOM que par recherche de chaînes | corrigé : doublure de DOM sans dépendance (`tests/js/minidom.mjs`, pas de jsdom ni de réseau) et `tests/test_workspace_dom.py`, qui monte le vrai `workspace.js` avec le vrai registre : proportions, sous-titres, états vides, « Préparation… », poignées `separator` et valeurs ARIA, focus sur la puce après « — » et sur le titre après réaffichage, dernière vue non masquable, mémorisation et rechargement, ⛶ puis Échap (menu Volets fermé d'abord, focus rendu), Échap dans le terminal, un arrêt de Tab par vue et flèches, boucle F6 et Maj+F6, poignée au clavier par 16 px bornée à 240 px, double-clic, une seule vue sous 1280 px. Vérifié par mutation (retrait du focus sur la puce, pas de poignée faussé : les tests échouent) |
| low | second avis 3 | `open_it` non atomique : un double clic lançait deux `setup`, le second en `app_error` | corrigé : vérification et création sous verrou, `setup` en cours suivi par espace ; la seconde demande répond 202 sans second `setup` (test : `epoch` reste 1, échoue sur l'ancien code) |
| low | second avis 4 | pas d'`onerror` sur l'`EventSource` ; arrêt de `connectWorkspace` jamais appelé | corrigé pour `onerror` : flux fermé pour de bon → message dans le panneau Scénario (`STREAM_LOST_TEXT`), reconnexion passagère laissée au navigateur ; test Node. Écarté pour l'arrêt : sans routeur côté client, quitter l'espace recharge la page, rien ne survit à fermer |
| low | second avis 5 | `GET /api/workspaces/<id>` répondait 200 pour un espace jamais ouvert | corrigé : 404 sauf espace sur disque ou `setup` en cours (la redirection juste après `/api/open` reste servie) ; test |
| low | second avis 6 | `skipif(NODE is None)` silencieux | corrigé à moindre coût : `test_node_present_en_ci` échoue si `CI` est posé et Node absent |

### À vérifier dans un vrai navigateur

La doublure de DOM n'a ni mise en page ni moteur de rendu. Restent à constater à la main :

- tailles réelles à 1920 x 1080 (panneau de 440 px, rangées 40/33/27, largeurs 55/45), à 125 % et à 400 % de zoom, et la colonne unique à 640 px ou moins ;
- glisser une poignée à la souris (capture du pointeur, zone de prise de 32 px) et le repli automatique quand on réduit la fenêtre (`ResizeObserver`) ;
- ordre réel de Tab dans la page (en-tête, panneau, puces, vues, poignées), annonces du lecteur d'écran (`role="status"`, raison de « — » inactif) ;
- apparence des poignées, des puces, du menu Volets et de l'anneau de focus, en thème clair et sombre ;
- arrêt du serveur pendant que l'espace est ouvert : message du point de vie et de `STREAM_LOST_TEXT`.
