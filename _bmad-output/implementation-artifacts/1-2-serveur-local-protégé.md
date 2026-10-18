---
story: "1.2"
key: 1-2-serveur-local-protégé
title: Lancer l'application sur un serveur local protégé
status: review
branch: story/1-2-serveur-local
ad: [AD-19, AD-20, AD-5, AD-14]
---

# Story 1.2 : Lancer l'application sur un serveur local protégé

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 1.2 ».

## Livré

- `cli/` : commande `wavedevsecops` (point d'entrée `[project.scripts]`), option `--window`. Socket lié à `127.0.0.1:0` (port libre, sans course) et passé à uvicorn ; jeton aléatoire ; `app.lock` ; ouverture du navigateur (`webbrowser`) ; console (adresse sans jeton, rappel `NO_PROXY`, `--window`) ; journal `RotatingFileHandler` dans `<data>/logs/app.log` (accès uvicorn désactivés : l'URL porte le jeton).
- `web/app.py` : `create_app(port, token)`. Middleware : `Host` (`127.0.0.1:<port>`, `localhost:<port>`), `Origin` égale à `http://<Host>` sur tout `POST`, cookie de session `HttpOnly` `SameSite=Strict` obtenu en échange de `/?t=<jeton>` (redirection 303 sans jeton), `/osv/` public en POST seulement. Aucun CORS. Page d'accueil provisoire (la coquille est la Story 1.3).
- `progress/` : `ensure_progress` crée `progress.json` (`schema_version`, `installed_at` lu dans `install.json`, `first_launch_at`), écriture atomique ; version future : fichier intact, `FutureSchemaError` (`AppError` de `contracts`, messages en français).
- `config.py` : `resolved_data_dir()` (platformdirs), `log_max_bytes`, `log_backup_count`. `contracts` : `AppError(cause_text, action_text)`.
- `tests/test_local_server.py` : vrai serveur en fil sur le loopback, dossier temporaire, un test par refus.

## Décisions

- Instance unique : `app.lock` (JSON pid, port, jeton) créé par `os.link` d'un temporaire (exclusif et contenu déjà complet). Vivacité testée par connexion loopback au port ; verrou périmé remplacé. Le second lancement ne lit que le verrou et n'écrit rien.
- Cookie de session distinct du jeton (le jeton n'est pas stocké dans le navigateur).
- `Origin` absente sur un `POST` : refusée.
- Tests sans `httpx` (absent de la table Stack) : `http.client` contre un vrai serveur.

## Reports

- Route `/osv/v1/query` : renvoie 404 pour l'instant (middleware prêt) ; livrée avec la station 3.
- `--window` : seul le repli sans extra est testé ; le test de l'extra pywebview sous Windows reste reporté (déjà noté Story 1.1).
- Diagnostic dans la console (AD-20) : avec la Story 1.4.
- `content_hash`, mise à jour par l'installeur : stories concernées.

## Revue

Revue unique (Opus) sur c19fdc1, avec la liste du second avis (Haiku).

- medium · second avis 1 · corrigé · `OSError` hors `FileExistsError` (droits, disque plein, `os.link` refusé sur FAT ou partage réseau) remontait en trace Python : `main` affiche cause et action en français (dossier, `WDS_DATA_DIR`) et sort en 1. Test `test_erreur_systeme_message_clair_sans_trace`.
- medium · second avis 2 · corrigé · reprise d'un verrou périmé non atomique (`unlink` après lecture : deux lancements simultanés pouvaient garder chacun un serveur). Le périmé est écarté par `os.replace` vers un nom propre au processus, son contenu comparé à celui jugé périmé ; un verrou neuf déplacé par erreur est remis en place. Test `test_verrou_perime_neuf_d_un_concurrent_rendu`.
- low · second avis 3 · reporté · vivacité jugée sur un port qui écoute : une réponse HTTP identifiable ne convient pas tant que le verrou est pris avant le démarrage d'uvicorn (un lancement en cours serait jugé mort). Port d'écoute éphémère réutilisé par un autre service : rare. À reprendre si le cas se présente (piste : vérifier aussi le `pid` du verrou).
- low · second avis 4 · corrigé · le cas nominal du critère (instance vivante) n'écrivait déjà rien ; seul le perdant d'une course écrivait journal et `progress.json` (avec un temporaire `progress.json.tmp` partagé). Le verrou est désormais pris avant le journal et `progress`. Test `test_lancement_concurrent_perdant_n_ecrit_rien`.
- low · second avis 5 · corrigé · mort du fil uvicorn sans demande d'arrêt : message et code 1. Test `test_arret_inattendu_du_serveur_code_1`.
- low · second avis 6 · corrigé · `WDS_DATA_DIR=""` vaut « non fixé » (validateur `data_dir`). Test `test_wds_data_dir_vide_vaut_dossier_par_defaut`.
- low · second avis 7 · corrigé · le critère ne vise que `POST` et les autres méthodes inter-origines passent par un pré-vol que l'absence de CORS bloque déjà ; contrôle d'`Origin` étendu à toute méthode hors `GET`/`HEAD`/`OPTIONS` par défense en profondeur. Test `test_methodes_non_sures_controlent_l_origine`.
- info · revue · noté · `ruff format --check` signale `web/app.py` (chaîne `_INDEX`) ; non exigé par la CI.
