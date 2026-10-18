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

## Revue

Revue unique (Opus) sur 98efad4, avec la liste du second avis (Haiku). Critères d'acceptation repris un à un : couverts.

- low · second avis 1 · rejeté · `unavailable_scenarios.length` : afficher la taille d'une liste fournie par le serveur n'est pas un calcul métier ; la liste et son contenu viennent de `diagnostic` (AD-16).
- low · second avis 2 · corrigé · pastille au singulier : `badge_one` / `badge_many` dans `content/diagnostic.yaml` (« Diagnostic, 1 outil absent ou trop ancien »). Test `test_pastille_au_singulier`.
- low · second avis 3 · rejeté · `create_app()` sans `settings` : `get_settings()` est le défaut voulu ; le seul appelant (`cli.start_instance`) et tous les tests passent leurs réglages, et rien n'est écrit avant un `GET /diagnostic`.
- low · second avis 4 · corrigé · marqueur non écrivable : « Continuer vers le catalogue » renvoyait sans fin vers `/diagnostic`. L'instance retient en mémoire que la page a été vue. Test `test_marqueur_non_ecrit_pas_de_boucle`.
- low · second avis 5 · rejeté · POST concurrents sérialisés : le 409 d'AD-17 vise les intentions sur un espace (`/api/ws/<id>/…`) et la file du moteur ; relancer un diagnostic est idempotent et le bouton est inactif pendant la recherche.
- low · second avis 6 · corrigé · une console en échec (encodage, flux fermé) transformait un rapport calculé en 500 : l'écoute est isolée et journalisée. Test `test_console_en_echec_ne_fait_pas_echouer_la_page`.
- low · second avis 7 · rejeté · diagnostic lancé à l'ouverture de l'accueil sans rapport connu : voulu, la pastille de l'en-tête en dépend (critère 4) et la spine prévoit le diagnostic dans la console de lancement.
- low · second avis 8 · rejeté · aucune couverture perdue : `/` avec cookie reste testé (`test_shell_ui` paramétré sur `/`, `test_premier_lancement_…`), le refus d'hôte étranger porte toujours sur `/`.
- low · second avis 9 · rejeté · même convention que `test_shell_js` (Story 1.3) ; Node est présent sur les runners GitHub de la CI.
- low · second avis 10 · corrigé · les lignes Proxy en règle n'avaient pas de « Que faire ? » alors que le critère et la maquette en donnent un à chacune : phrases « Rien à faire. … » (`ok_proxy`, `ok_no_proxy`, `ok_certs`), affichées sans dépliant ; « Proxy détecté » passe en ✓ comme sur la maquette. Test `test_proxy_en_regle_chaque_ligne_a_son_que_faire`.
- low · revue · corrigé · le critère « les lancements suivants ouvrent l'accueil » n'était vérifié que dans une même instance : test `test_lancement_suivant_ouvre_l_accueil` (arrêt puis second lancement sur le même dossier).
- low · revue · reporté · `<data>/diagnostic_seen` n'est pas dans la disposition d'AD-5. Propriétaire unique (`web`), écrit par le serveur lancé (la règle 1.2 « le second lancement n'écrit rien » vise le lancement qui rejoint une instance vivante, il n'écrit toujours rien). À ajouter à la disposition d'AD-5 à la prochaine mise à jour de la spine, ou à remplacer par un fait de `progress` si le suivi en a besoin.
