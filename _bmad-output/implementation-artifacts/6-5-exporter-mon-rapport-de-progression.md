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
- `render_html` (Jinja2, autoescape) : fichier autonome, CSS en ligne (thème clair/sombre, impression), polices Atkinson 400 et 700 en data URI (`web/catalogue.py: report_font_css`), aucune URL ni ressource externe. `render_csv` : UTF-8 avec BOM, séparateur `;`, fins de ligne CRLF, cellules textuelles commençant par `=+-@` neutralisées (injection de formule).
- Routes (`web/catalogue.py`, sous cookie de session comme le reste) : `GET /api/report` (aperçu JSON) et `GET /api/report/export?format=html|csv` (pièce jointe `rapport-wavedevsecops.<ext>`) ; format inconnu : 422 ; `progress.json` illisible : 500 avec cause et action.
- Front : `static/js/report.js` ; `main.js` ajoute `renderReportEntry` sous le catalogue. Pied : « Exporter mon rapport » + « Rien n'est envoyé : vous choisissez à qui transmettre le fichier. » ; le clic ouvre `report-preview` (dates, une ligne par scénario, texte vide) avec « Exporter en HTML » et « Exporter en CSV ». L'enregistrement passe par `showSaveFilePicker` si disponible, sinon un téléchargement ; l'annulation est silencieuse ; un échec affiche un `notice-card` « Le fichier n'a pas pu être enregistré : <cause>. » avec « Réessayer ».
- pywebview : `webview.settings["ALLOW_DOWNLOADS"] = True` dans `cli._run_window`, pour que le téléchargement ouvre la boîte d'enregistrement du système.
- CSS : bloc `.report-*` en fin de `catalogue.css`.
- Tests : `test_report.py` (contenu, vide, aucun fichier, HTML autonome et échappé, CSV BOM/`;`/formule, routes sous cookie, 422, 500) ; `test_report_dom.py` (Node : pied, aperçu, texte vide, format demandé, échec et Réessayer, cause serveur).

## Décisions

- Le fichier est produit par le serveur et enregistré par le navigateur : le serveur n'écrit rien sur le disque de l'apprenant, donc aucune route d'écriture à protéger.
- Les remises à zéro se lisent dans les faits de type `scenario_reset` (non listé dans `FactKind` : le rapport lit les faits bruts). Sans l'émetteur de 4.4, le compte est 0.
- Le rapport garde les scénarios en cours en plus des terminés ; seul « aucun terminé » déclenche le texte vide.

## Reports

- Remises à zéro (story 4.4, non fusionnée) : elle doit ajouter le fait `scenario_reset` (identité propre : une remise = un fait, `op_id` distinct) et l'ajouter à `FactKind`. `derive` ne doit pas le compter dans le score ni les indices. Aujourd'hui `derive` rend « En cours » pour un scénario qui n'aurait que des remises : sans conséquence tant que 4.4 émet la remise après un premier fait.
- État `exporting` (AD-1) : non implémenté, l'export ne passe pas par la file d'opérations d'un espace (aucune opération d'espace concernée).
- Désignations (5.2) : leur score entrera dans le rapport avec `derive` (voir report de 4.7).
- Rendu réel (boîte d'enregistrement pywebview, impression PDF, contraste) à vérifier dans un navigateur et dans la fenêtre pywebview.
