---
story: "1.7"
key: 1-7-installer-l-application-sous-macos-et-linux-sans-droits-administrateur
title: Installer l'application sous macOS et Linux sans droits administrateur
status: review
branch: story/1-7-installeur-unix
ad: [AD-3, AD-15, AD-16, AD-20]
---

# Story 1.7 : Installer l'application sous macOS et Linux sans droits administrateur

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 1.7 ». Modèle : `install.ps1` (story 1.6).

## Livré

- `install.sh` (racine, `sh` POSIX, testé avec sh et dash, aucun `sudo`). Tout le code est dans `main()`, appelée en dernière ligne : un téléchargement tronqué n'exécute rien. Étapes et `install.json` identiques à `install.ps1` : plateforme, dossier de données, proxy, registre `tools.toml`, git, uv, application, `uv sync --frozen`, gitleaks, `install.json`.
- Dossier de données : `WDS_DATA_DIR`, sinon `$XDG_DATA_HOME/WaveDevSecOps` si `XDG_DATA_HOME` est absolu (Linux et macOS, comme platformdirs 4.13), sinon `~/Library/Application Support/WaveDevSecOps` (macOS) ou `~/.local/share/WaveDevSecOps` (Linux), comme `resolved_data_dir()` (test d'égalité sous Linux et macOS en CI, XDG absent, absolu ou relatif).
- Registre : mini-lecteur awk de `tools.toml` (local à côté du script, sinon téléchargé de `raw.githubusercontent.com`). Versions jamais redéclarées dans le script.
- git : git du poste gardé s'il atteint 2.38. Sous macOS, `/usr/bin/git` n'est appelé qu'après `xcode-select -p` réussi (sinon on l'ignore). Sinon pixi 0.82.0 (archive de la release, vérifiée par son `.sha256`) installé dans `<data>/tools/bin`, puis `pixi global install git==2.56.0` avec `PIXI_HOME=<data>/tools` : git exposé en `<data>/tools/bin/git`, chemin déjà attendu par `tools.toml` (`posix`). Un git provisionné suffisant est réutilisé.
- uv : gardé s'il atteint 0.11.0, sinon installeur officiel d'astral 0.13.1 (profil de l'utilisateur, `~/.local/bin`), appelé ensuite par chemin complet.
- Application : voie clone (`-c core.autocrlf=false`, `--depth 1`, dossier `app.partial` puis renommé) ou voie `zip` (archive `tar.gz` de GitHub, sans dépendre de `unzip`, extraction dans `app.new` puis échange). Mise à jour : `fetch` + `reset --hard`, ou remplacement. Un dossier `app` étranger n'est jamais supprimé.
- gitleaks (AD-15, non fait par `install.ps1`) : archive de la release pour l'OS et l'architecture, vérifiée par `gitleaks_<v>_checksums.txt`, extraite dans `<data>/tools/gitleaks/`. Une somme fausse supprime l'archive et arrête l'installation avec un message en français.
- Proxy : `HTTPS_PROXY` exporté (curl, git, uv, pixi le lisent), `UV_SYSTEM_CERTS=true` posé. La commande d'amorçage `curl -fsSL … | sh` respecte `HTTPS_PROXY` nativement (leçon 1.6).
- Reprise : téléchargements en `.part`, clone/archive en dossier temporaire, `install.json` écrit en dernier (atomique, ligne par ligne, relu sans `jq`). Erreurs : étape, cause, variables, voie clone ou zip, « relancez ». Les sous-processus lisent `/dev/null` (le script peut venir d'un tube).
- Mode simulation et réglages de test comme `install.ps1` (`WDS_INSTALL_SIMULATE*`), plus `_OS`, `_ARCH`, `_XCODE`, `_GIT_PATH` ; `WDS_INSTALL_FORCE_PROVISION_GIT=1` (CI : exerce la voie pixi).
- Tests `tests/test_install_sh.py` (ignorés sous Windows) : syntaxe, versions, registre lu comme Python, sommes SHA-256, dossier de données, simulations (git du poste, pixi, xcode-select présent/absent, relance, échecs, somme fausse, archive, dossier étranger, `install.json` futur, proxy), et la commande du README exécutée telle quelle (URL en `file://`).
- CI : `shellcheck -s sh install.sh` (ubuntu) et job `installeur-unix` : `install.sh` réel sur `ubuntu-latest` et `macos-latest`, git du runner ignoré, durée relevée dans le journal.
- README : commande unique et réglages.

## Écarts et reports

- préchargement de `uv-cache` (AD-12/AD-15) : absent, comme dans `install.ps1`. À traiter avec la story du cache hors ligne.
- Le fichier de sommes de gitleaks s'appelle `gitleaks_<v>_checksums.txt` (nom réel des releases), pas `checksums.txt`.
- La voie « zip » récupère une archive `tar.gz` (même contenu, outil `tar` toujours présent).
- Non couvert par la CI : proxy d'entreprise avec inspection TLS, `xcode-select` sur un Mac sans outils Xcode, compte sans droits d'écriture hors profil.

## À vérifier sur un vrai poste macOS / Linux sans droits administrateur

1. Commande du README collée dans un terminal (macOS arm64 et Intel, Linux x64 et arm64) : installation complète, aucune invite de mot de passe, durée sous 10 minutes.
2. Mac sans outils Xcode (`xcode-select -p` échoue) : aucune fenêtre d'installation ne s'ouvre ; git vient de pixi (`<data>/tools/bin/git`).
3. Mac avec outils Xcode : `/usr/bin/git` est gardé s'il atteint 2.38.
4. Avec `HTTPS_PROXY` (proxy d'entreprise, idéalement avec inspection TLS) : script, installeur de uv, pixi, conda-forge, clone, `uv sync` et gitleaks passent par lui ; certificats d'entreprise reconnus par pixi (sinon `SSL_CERT_FILE`).
5. Noms d'archives pixi (`pixi-<triple>.tar.gz` et son `.sha256`) et paquet conda-forge `git==2.56.0` disponibles pour chaque plateforme.
6. Voie `zip` (`WDS_INSTALL_METHOD=zip`) sans git ; relance : `progress.json` intact, `run_count` incrémenté ; coupure réseau pendant le clone puis relance.
7. `XDG_DATA_HOME` posé : l'application et l'installeur lisent le même dossier.
8. Shell de login non POSIX (fish, zsh) : la commande `| sh` fonctionne ; le PATH de uv est visible dans un nouveau terminal.
9. Coupure réseau pendant un clone qui remplace une installation par archive : l'application précédente reste en place ; un téléchargement ou un clone bloqué s'arrête au bout d'environ 60 s sous 1 Ko/s.

## Revue

Revue unique (Opus) après rebase sur `main` (7345b83) ; conflit `ci.yml` résolu en gardant les deux ajouts (`unshare -n`, `autocrlf`, puis `shellcheck` et le job `installeur-unix`).

| Sévérité | Source | Constat | Décision |
|---|---|---|---|
| medium | revue | platformdirs 4.13.4 (verrouillé) lit `XDG_DATA_HOME` aussi sous macOS ; `install.sh` l'ignorait sous macOS, et le correctif CI eda7245 avait masqué l'écart en ne posant la variable que sous Linux : installeur et application visaient deux dossiers. | Corrigé : `XDG_DATA_HOME` absolu pris sous Linux et macOS ; test d'égalité rétabli sur les deux OS. |
| low | second avis 1 | `XDG_DATA_HOME` relatif pris tel quel alors que platformdirs l'ignore. | Corrigé (même correctif) ; cas relatif ajouté au test d'égalité. |
| medium | second avis 2 | Voie zip : git absent jamais provisionné, sans message (`install.sh` et `install.ps1`). | Corrigé en partie : avertissement en français dans les deux installeurs (git requis par les exercices, relancer sans `WDS_INSTALL_METHOD=zip` ou installer git). Provisionnement écarté sur cette voie : elle sert de repli quand le clone ou le provisionnement échoue (« sans git », spec point 6) ; le critère ne vise que le cas où le script provisionne. Tests sh et ps1. |
| low | second avis 3 | Voie clone : `rm -rf app` avant le clone ; une coupure perdait l'application précédente. | Corrigé : `replace_app_dir` commun aux deux voies (clone dans `app.partial`, ancienne version mise de côté puis supprimée, restaurée si l'échange échoue). Test zip, clone en échec, clone réussi. |
| low | second avis 4 | `mv` non vérifiés. | Corrigé : chaque `mv` arrête l'installation avec un message. |
| low | second avis 5 | curl, wget, clone sans délai. | Corrigé : curl `--speed-limit 1024 --speed-time 60`, wget `--timeout=60 --tries=3`, git `http.lowSpeedLimit/Time`. `uv sync` : écarté, uv a déjà son délai (`UV_HTTP_TIMEOUT`, 30 s). |
| low | second avis 6 | `pixi` absent d'`install.json` quand une relance réutilise le git provisionné. | Corrigé : version de pixi relue (sonde) si git provisionné et pixi présent ; test de relance. |
