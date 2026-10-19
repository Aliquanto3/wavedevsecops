---
story: "6.5"
key: 6-5-exporter-mon-rapport-de-progression
title: Exporter mon rapport de progression
status: review
branch: story/6-5-export-rapport
ad: [AD-14, AD-13, AD-2, AD-1]
---

# Story 6.5 : Exporter mon rapport de progression

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 6.5 » (FR-36, NFR-9, UX-DR31).

## Livré

- `progress/report.py` : `build_report(data_dir, titles=, tracks=)` calcule le rapport à la lecture depuis `progress.json` (rien n'est écrit, même contrat que le bilan 4.7 : `ProgressStore.all_progress`, `build_summary`, `catalogue_rank` pour l'ordre). Par parcours et par scénario/mode : état, score du premier coup, indices, remises à zéro, date de fin ; en tête, dates d'installation et de premier lancement. Sans scénario terminé : `empty` + texte « Aucun scénario terminé pour l'instant… ». Sans `progress.json`, rien n'est créé et les dates disent « Non renseigné ».
- `render_html` (Jinja2, autoescape) : fichier autonome, CSS en ligne (thème clair/sombre, impression), polices Atkinson 400 et 700 en data URI (`web/catalogue.py: report_font_css`), aucune URL ni ressource externe. `render_csv` : UTF-8 avec BOM, séparateur `;`, fins de ligne CRLF, toutes les cellules commençant par `=+-@`, tabulation ou retour à la ligne neutralisées par une apostrophe (injection de formule), à un seul endroit.
- Routes (`web/catalogue.py`, sous cookie de session comme le reste) : `GET /api/report` (aperçu JSON) et `GET /api/report/export?format=html|csv` (pièce jointe `rapport-wavedevsecops.<ext>`) ; format inconnu : 422 ; `progress.json` illisible : 500 avec cause et action.
- Front : `static/js/report.js` ; `main.js` ajoute `renderReportEntry` sous le catalogue. Pied : « Exporter mon rapport » + « Rien n'est envoyé : vous choisissez à qui transmettre le fichier. » ; le clic ouvre `report-preview` (dates, une ligne par scénario, texte vide) avec « Exporter en HTML » et « Exporter en CSV ». L'enregistrement passe par `showSaveFilePicker` si disponible, sinon un téléchargement ; l'annulation est silencieuse ; un échec affiche un `notice-card` « Le fichier n'a pas pu être enregistré : <cause>. » avec « Réessayer ».
- pywebview : `webview.settings["ALLOW_DOWNLOADS"] = True` dans `cli._run_window` (clé présente dans pywebview 6.2.1, `ImmutableDict` ; sous WebView2 le téléchargement ouvre un `SaveFileDialog`). Une version sans cette clé journalise un avertissement et la fenêtre s'ouvre quand même.
- CSS : bloc `.report-*` en fin de `catalogue.css`.
- Tests : `test_report.py` (contenu, vide, aucun fichier, HTML autonome et échappé, CSV BOM/`;`/formule, routes sous cookie, 422, 500) ; `test_report_dom.py` (Node : pied, aperçu, texte vide, format demandé, échec et Réessayer, cause serveur).

## Décisions

- Le fichier est produit par le serveur et enregistré par le navigateur : le serveur n'écrit rien sur le disque de l'apprenant, donc aucune route d'écriture à protéger.
- Contrat partagé avec 4.4 : le fait de remise à zéro s'appelle `scenario_reset` (constante `progress.facts.RESTART_KIND`), un fait par remise (`op_id` dans l'identité). `derive` l'exclut de l'état, du score et des indices (même ligne que la branche 4.4) ; le rapport compte ces faits bruts. Tant que 4.4 n'a pas ajouté le kind à `FactKind`, le compte vient des faits bruts.
- Le rapport garde les scénarios en cours en plus des terminés ; seul « aucun terminé » déclenche le texte vide.

## Reports

- Remises à zéro (story 4.4, non fusionnée) : à la fusion, garder `scenario_reset` dans `FactKind` et l'identité par `op_id` (déjà sur la branche 4.4), et faire pointer 4.4 sur `RESTART_KIND`.
- État `exporting` (AD-1) : non implémenté, l'export ne passe pas par la file d'opérations d'un espace (aucune opération d'espace concernée).
- Désignations (5.2) : leur score entrera dans le rapport avec `derive` (voir report de 4.7).
- Rendu réel (boîte d'enregistrement pywebview, impression PDF, contraste) à vérifier dans un navigateur et dans la fenêtre pywebview.

## Revue

Revue Opus (une passe), après rebase sur `origin/main`.

- M1 · second avis · corrigé : `render_csv` passe toutes les cellules (dates d'en-tête, mode, état, nombres, date de fin) par `_cell` ; test par colonne et par charge (`=HYPERLINK`, `=cmd|`, `+`, `-`, `@`, tabulation) et dates brutes non ISO.
- M2 · second avis · corrigé : kind aligné sur la branche 4.4 (`scenario_reset`, `RESTART_KIND` dans `progress.facts`) ; `derive` ignore les remises, une remise seule laisse le scénario « À faire » (test).
- M3 · second avis · corrigé : clé vérifiée dans les sources de pywebview 6.2.1 (`ImmutableDict`, `ALLOW_DOWNLOADS: False`) ; `AttributeError`, `KeyError`, `TypeError` journalisés sans bloquer la fenêtre ; test avec doublure (clé présente, absente, module sans `settings`).
- L4 · second avis · écarté : la fenêtre ne charge que l'application locale (loopback, CSP, aucune URL externe) ; seuls ses téléchargements sont concernés, chacun via la boîte d'enregistrement.
- L5 · second avis · écarté : lecture seule, même comportement que le catalogue et le bilan ; l'écriture refuse déjà un fichier futur (`FutureSchemaError`).
- L6 · second avis · corrigé : le titre de `report-preview` prend le focus à l'ouverture (test) ; l'id fixe est sûr, un seul aperçu à la fois (`replaceChildren`).
- L7 · second avis · corrigé : écriture échouée, le flux de `showSaveFilePicker` est abandonné (`abort`) puis l'erreur remonte au Réessayer (test).
- L8 · second avis · reporté : état `exporting` (AD-1), déjà dans les Reports ; aucune opération d'espace n'est concernée.
- Complexité : aucun constat (le rapport lit `progress.json` une fois par demande, regroupement en O(n)).
- À vérifier à la main : boîte d'enregistrement dans la fenêtre pywebview sous Windows (WebView2), macOS et Linux ; impression PDF du HTML.
