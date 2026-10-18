# Pass 1 — couverture mécanique (validate.md), après la passe de correction

Fichiers : DESIGN.md (550 lignes), EXPERIENCE.md (522 lignes), status final. Contrôle scripté : YAML des deux frontmatters valide ; 104 références `{…}` résolues ; 55 couleurs claires (hosting-network retiré), chacune avec son jumeau `-dark` (dont `terminal-*` et `focus-on-ink`) ; chaque composant du frontmatter cité dans EXPERIENCE.md.

## 1. Flow coverage — strong
- UJ-1 (Anaël), UJ-2 (Camille), cas limite proxy (Camille), UJ-3 (Camille), UJ-4 (Karim) : protagoniste, étapes numérotées, climax, chemin d'échec (Flow 3 compris).
- Reste : Station 4 (FR-29 à FR-31) sans flow, car le PRD renvoie son parcours au découpage ; composants et règles écrits (section Livraison), flow en question ouverte 1.

## 2. Token completeness — strong
- Verbatim WaveStack + jetons dédiés au terminal et au focus sur encre (valeurs copiées). Tableau de contrastes des combinaisons ajoutées (DESIGN > Colors).
- Reste : tableau à reporter dans `tests/test_web_tokens.py`.

## 3. Component coverage — strong
- Ajoutés : `quiz-choice`, `designate-button`, `designate-list`, `sha-field`, `notice-card`, `review-log`, `sbom-view`, `mode-badge`, `path-badge`, `path-picker`, `catalogue-section`, `commit-list`, `external-change-notice`, `network-run-button`, `report-preview`, `focus-ring`, `build-artifact`, `env-card`, `promotion-gate`. Chacun a une spec visuelle et une règle de comportement.

## 4. State coverage — strong
- Ajoutés : premier passage sans parcours, aucune progression, Code vide, bac à sable indisponible, application arrêtée, port occupé, hook refusé, lint/test en échec, outil en erreur dans le pipeline, bonne réponse de quiz, export impossible, Reprendre.

## 5. Visual reference coverage — strong
- `mockups/` : `espace-travail.html` (DESIGN > Layout & Spacing, Focus/liaison, `pr-check` ; EXPERIENCE > Disposition A), `designation-mode-b.html` (DESIGN > Désignation et correction ; EXPERIENCE > Désignation), `diagnostic.html` et `catalogue.html` (DESIGN > Catalogue, diagnostic, exports ; EXPERIENCE > Catalogue, Diagnostic). Chacune liée inline avec ce qu'elle illustre.
- `imports/wavestack-digest.md` lié à chaque renvoi (§1 à §5).
- « Les spines priment sur toute maquette » écrit une fois, en tête de chaque spine.
- Originaux validés gardés dans `.working/key-*.html` ; les copies de `mockups/` ajoutent le menu de parcours dans l'en-tête, deux cases de thème (forcer clair / forcer sombre, sans JS) et la note « versions minimales illustratives ».
- Reste : pas de maquette pour Rapport, Fiche, Entretien RSSI, carte dépliée et Livraison (spécifiés en texte seulement).
