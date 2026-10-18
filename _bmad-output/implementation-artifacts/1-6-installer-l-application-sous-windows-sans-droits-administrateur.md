---
story: "1.6"
key: 1-6-installer-l-application-sous-windows-sans-droits-administrateur
title: Installer l'application sous Windows sans droits administrateur
status: review
branch: story/1-6-installeur-windows
ad: [AD-3, AD-15, AD-16, AD-20]
---

# Story 1.6 : Installer l'application sous Windows sans droits administrateur

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 1.6 ».

## Livré

- `install.ps1` (racine, UTF-8 avec BOM, Windows PowerShell 5.1, aucune élévation). Étapes : dossier de données (`WDS_DATA_DIR`, sinon `%LOCALAPPDATA%\WaveDevSecOps`, identique à `resolved_data_dir()`), proxy, lecture de `tools.toml`, git, uv, application, `uv sync --frozen`, `install.json`.
- Registre : lu depuis `tools.toml` (local, sinon téléchargé du dépôt) par un mini-lecteur TOML ; versions minimales et provisionnées, jamais redéclarées dans le script.
- git : git du poste gardé s'il atteint `min_version` (2.38) ; sinon PortableGit `provisioned_version.windows` (2.56.0.windows.2) extrait par `-y -gm2 -InstallPath=<data>/tools/git` (chemin `git/cmd/git.exe` du registre). Un PortableGit déjà provisionné suffisant est réutilisé.
- uv : gardé s'il atteint 0.11.0 ; sinon installeur officiel de uv 0.13.1 dans le profil (PATH utilisateur, sans admin). Appelé ensuite par chemin complet.
- Application : voie clone (`-c core.autocrlf=false`, `--depth 1`, dans `app.partial` puis renommé) ou zip (`WDS_INSTALL_METHOD=zip`, extraction dans `app.new` puis échange). Mise à jour : `fetch` + `reset --hard` (clone) ou remplacement (zip). Les données (`progress.json`, etc.) vivent hors de `app/` et ne sont jamais touchées.
- Proxy : `HTTPS_PROXY` utilisé pour les téléchargements (`-Proxy`), `http.sslBackend=schannel` pour git, `UV_SYSTEM_CERTS=true` posé pour le processus.
- Reprise : téléchargements en `.part` renommés à la fin, clone/zip en dossier temporaire, extraction PortableGit nettoyée si interrompue ; `install.json` écrit en dernier (atomique).
- Erreurs en français : étape, cause, variables à régler, voie clone ou zip, « relancez ». Collé par `iex`, l'installeur ne fait pas `exit` (il fermerait la console) ; lancé en fichier, il rend le code 1.
- `install.json` : `schema_version` 1, `installed_at` (première installation, lue par `progress`), `updated_at`, `run_count`, `duration_s`, `method`, `app_dir`, `versions` (`git`, `git_source`, `uv`, `app`). Un `install.json` de version future n'est pas modifié (erreur claire).
- README : commande unique et réglages.
- Tests (`tests/test_install_ps1.py`, exécutés par la matrice CI sous `windows-latest`, ignorés ailleurs) : comparaison de versions, lecture de `tools.toml` comparée au lecteur Python, URL PortableGit, dossier de données identique à `Settings`, parcours simulé (git du poste, git absent ou trop ancien, zip, mise à jour qui conserve `progress.json`, échec de téléchargement puis reprise, échec de `uv sync` puis reprise, méthode inconnue, `install.json` futur, proxy). Mode simulation : `WDS_INSTALL_SIMULATE=1` (+ `_GIT`, `_UV`, `_FAIL`), sans réseau ni installation.

## Décisions

- Pas de job CI dédié : la matrice existante exécute déjà pytest sous `windows-latest`.
- Fichier en UTF-8 avec BOM (PowerShell 5.1 lit sinon en ANSI) ; la commande du README décode les octets en UTF-8 et retire le BOM avant `iex`.
- uv installé avec la modification du PATH utilisateur par défaut de son installeur ; le lancement affiché utilise le chemin complet.

## Reports

- Gitleaks (archive vérifiée par `checksums.txt`) et préchargement de `uv-cache` : hors critères de la story, à traiter avec les stories qui en ont besoin (station 1, AD-12).
- Vérification d'empreinte de PortableGit : Git for Windows ne publie les sommes que dans les notes de release ; à ajouter à `tools.toml` si on veut la contrôler.
- Vérifications sur un vrai poste Windows non administrateur (non reproduites par la CI) : téléchargements réels, extraction PortableGit, installeur de uv, clone et zip réels, proxy d'entreprise avec inspection TLS, exécution collée par `iex`, temps d'installation (objectif 10 minutes).
