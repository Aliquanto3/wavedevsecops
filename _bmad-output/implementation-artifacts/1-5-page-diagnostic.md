---
story: "1.5"
key: 1-5-page-diagnostic
title: Consulter la page Diagnostic et savoir quoi régler
status: review
branch: story/1-5-page-diagnostic
ad: [AD-16, AD-2, AD-17, conventions Ton et Textes affichés]
---

# Story 1.5 : Consulter la page Diagnostic et savoir quoi régler

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 1.5 ». UX : EXPERIENCE.md (Diagnostic), DESIGN.md (`notice-card`, `diagnostic-badge`), `mockups/diagnostic.html`.

## Livré

- `diagnostic` : `DiagnosticCheck` porte maintenant `usage_text`, `required_version` (« ≥ 2.38 » ou version exacte), `unavailable_scenarios` (calculé par `run_diagnostic(scenarios=...)`, vide tant qu'aucun scénario n'est déclaré, et vide pour un outil en règle) et `parts` (`CheckPart` : lignes Proxy, NO_PROXY, UV_SYSTEM_CERTS, chacune avec son « Que faire ? »). Nouvelles fonctions : `build_report` (lignes, groupes par jalon, synthèse, pastille, encart git), `plan` (lignes « En cours » et textes de la page), `group_by_milestone`, `console_lines`.
- `content/diagnostic.yaml` : textes de la page (`ui`), états des lignes Proxy (`part_statuses`), commandes des « Que faire ? » entre accents graves (le front les met en `code`).
- `web/app.py` : `GET /api/diagnostic` (plan + dernier rapport), `POST /api/diagnostic/run` (relance toutes les sondes dans un fil, sérialisées par un verrou, contrôle d'origine du POST comme les autres intentions ; échec : texte sans trace, statut 500). `create_app(settings=, on_diagnostic=)`.
- Premier lancement : `/` redirige (303) vers `/diagnostic` tant que `<data>/diagnostic_seen` n'existe pas ; ce marqueur est écrit quand la page Diagnostic est servie. Ensuite `/` sert l'accueil (en-tête seul ici).
- Console de lancement : `cli` passe `on_diagnostic` ; chaque diagnostic lancé depuis la page s'écrit dans la console (`console_lines`, mêmes états et mêmes « Que faire ? »).
- Front : `js/diagnostic.js` (page et pastille), `css/diagnostic.css`, `main.js` (branche la page sur la surface `diagnostic`, la pastille sur toutes les autres). Lignes « En cours » tant que la recherche n'est pas finie (aucun outil dit absent avant la fin), puis état en mots et icône (✓ OK, ⚠ Trop ancien, ✗ Absent) ; tableau groupé par jalon avec `th`, « Que faire ? » dépliable (ouvert pour un outil en défaut), colonne Scénarios indisponibles ; synthèse en `role="status"` ; `notice-card` d'erreur si git est absent ou trop ancien, avec « Continuer vers le catalogue » toujours proposé ; « Relancer le diagnostic » inactif avec sa raison pendant la recherche ; `diagnostic-badge` (décompte, nom du lien « Diagnostic, n outils absents ou trop anciens »), absent quand tout est OK.
- Reporté de la revue 1.4 : `NO_PROXY` et `no_proxy` qui diffèrent sont fusionnés (union des entrées) dans `read_proxy_environment`, donc plus de faux avertissement.
- Tests : `tests/test_diagnostic_page.py` (rapport, synthèse, singulier, groupes, git absent, scénarios, plan, console, API, premier lancement, origine, échec sans trace, NO_PROXY), `tests/test_diagnostic_js.py` (Node : code en ligne, icônes, pastille). `test_local_server.py` et `test_shell_ui.py` ajustés : `/` redirige au premier lancement.

## Décisions

- Le flux SSE et l'enveloppe complète d'événements (`boot_id`, `seq`, `Last-Event-ID`) ne sont pas exigés par les critères : la page utilise une intention `POST` et une réponse JSON, avec les mêmes `DiagnosticCheck` que ceux émis en `diagnostic_check`. Ils arrivent avec la Story 2.2, qui pourra émettre `run_diagnostic(emit=...)` sur le flux.
- Les lignes passent par « En cours » jusqu'à la réponse du serveur, pas une à une : sans flux, le serveur répond après toutes les sondes. L'affichage ligne par ligne vient avec le flux SSE.
- Le groupe d'un outil suit son jalon (`v0.1` : « Outils requis », les autres : « Outils de la chaîne (jalon) »).
- Le registre des volets n'est pas utilisé : la page Diagnostic est une page annexe (pas de volets numérotés).

## Reports

- Flux SSE, enveloppe d'événements, affichage ligne par ligne : Story 2.2.
- Calcul réel des scénarios indisponibles (déclaration des outils par scénario) : story du catalogue ; le paramètre `scenarios` de `run_diagnostic` est prêt.
- Catalogue grisé quand git manque : story du catalogue (l'encart d'erreur est livré ici).
