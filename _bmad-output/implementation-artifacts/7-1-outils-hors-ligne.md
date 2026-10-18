---
story: "7.1"
key: 7-1-outils-hors-ligne
title: Provisionner les outils de la chaîne pour un usage hors ligne
status: review
branch: story/7-1-outils-hors-ligne
ad: [AD-12, AD-13, AD-15, AD-16]
---

# Story 7.1 : Provisionner les outils de la chaîne pour un usage hors ligne

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 7.1 ». Reprend les reports des stories 1.6 (gitleaks sous Windows, préchargement d'`uv-cache`), 1.7 (préchargement) et 2.11 (garde réseau des tests du gabarit).

## Livré

- **gitleaks sous Windows** (`install.ps1`, `Install-Gitleaks`) : archive officielle `gitleaks_<version>_windows_x64.zip` de la release, somme lue dans `gitleaks_<version>_checksums.txt` (`Get-ExpectedChecksum`) et comparée par `Get-FileHash`, extraction dans un dossier `tools/gitleaks.new` puis échange. Une somme fausse supprime l'archive, n'extrait rien et arrête l'installation à l'étape « gitleaks » avec un message en français. Version écrite dans `install.json`. Relancé, un gitleaks à la bonne version est gardé. `install.sh` le faisait déjà (story 1.7).
- **Préchargement d'`uv-cache`** (`Invoke-UvCachePreload`, `preload_uv_cache`), étape « Cache uv hors ligne (uv-cache) » après `uv sync` : pour chaque `uv.lock` trouvé sous `content/` (gabarits d'exercice aujourd'hui, verrous d'états de scénario demain), `uv sync --frozen --all-groups --all-extras` vers un venv jetable, avec `UV_CACHE_DIR=<data>/uv-cache`, `UV_PYTHON_INSTALL_DIR=<data>/uv-cache/python` et `UV_PYTHON_PREFERENCE=only-managed`. Le cache contient donc l'interpréteur géré et chaque paquet verrouillé. Échec : message en français avec les réglages réseau et la voie de repli. Simulation : `uv-cache-preload <chemin>`, échec simulé `preload`.
- **`toolrun`** :
  - `offline_environment` ajoute `UV_PYTHON_INSTALL_DIR` (dans `uv-cache`), `UV_NO_PROGRESS` et `WDS_NETGUARD=1`.
  - `sync_environment(project, venv, settings)` crée ou met à jour `cache/venv/` par `uv sync --offline --frozen --project <repo>` (`UV_PROJECT_ENVIRONMENT`). uv est résolu par le registre. Rien n'est écrit dans le bac à sable.
  - `resolve(..., venv=)` et `run_tool(..., venv=)` : un outil `uv-lock` est cherché dans le venv d'exercice, avec sa version lue dans le `.dist-info` et comparée à `tools.toml` (égal au `uv.lock` du gabarit). Un écart donne `mismatch` « environnement abîmé … (uv sync) ». L'exécutable est pris dans `Scripts/` ou `bin/` du venv, jamais dans le PATH.
  - Helpers : `venv_dir`, `site_packages`, `installed_version`, `python_install_dir`.
- **Garde réseau** (report de la revue 2.11) : `sync_environment` pose `_wds_netguard.py` et `_wds_netguard.pth` dans le `site-packages` du venv. Tout Python du venv (outils, tests du gabarit) importe ce module au démarrage. Quand `WDS_NETGUARD=1`, un hook d'audit `socket.connect` refuse toute adresse hors loopback (`PermissionError` en français). `llmrun` n'aura qu'à ne pas poser la variable.
- **Diagnostic** : un seul groupe « Outils de la chaîne (v0.2+) » réunit gitleaks, ruff, pytest, pytest-cov, coverage, diff-cover, bandit, pip-audit et pre-commit, avec la version requise. Le statut `mismatch` s'affiche « Environnement abîmé », avec `uv sync` comme marche à suivre, et les scénarios touchés sont rendus indisponibles (mécanisme existant).
- **`pyproject.toml`** : `default-groups = ["dev", "chain"]`. Un simple `uv sync` (installeur, marche à suivre du diagnostic) installe ainsi les outils de la chaîne dans l'environnement de l'application. Une ligne `default-groups` s'ajoute à `uv.lock`.
- **CI** :
  - Le préchargement du job `tests` suit la disposition de l'installeur (`WDS_EXERCISE_DATA`).
  - `tests/test_exercise.py` (avec `WDS_EXERCISE_UV=1`, y compris sous `unshare -n`) crée le venv par `toolrun.sync_environment`, vérifie la garde réseau et lance pytest par `toolrun.run_tool`.
  - Après `install.sh` réel (macOS, Linux ; sous Linux dans `unshare -n`), `.github/scripts/verifier_hors_ligne.py` crée un venv hors ligne et résout les outils. Il lance ruff et pytest et vérifie le diagnostic.
  - Nouveau job `installeur-windows` : `install.ps1` réel, puis le même script.
- README : les deux installeurs mentionnent le préchargement, et gitleaks sous Windows.
- Tests :
  - `test_toolrun.py` : résolution dans un venv factice (deux familles), environnement hors ligne, `sync_environment` (argv, env, garde posée, uv absent), garde réseau réelle (loopback permis, `192.0.2.1` refusé).
  - `test_diagnostic.py` : groupe v0.2+, environnement abîmé.
  - `test_install_ps1.py` : gitleaks et préchargement simulés, somme fausse, échec du préchargement, lecture des sommes.
  - `test_install_sh.py` : ordre du préchargement, échec du préchargement.

## Décisions

- L'interpréteur géré va dans `<data>/uv-cache/python` (`UV_PYTHON_INSTALL_DIR`), comme le demande le critère « le cache contient l'interpréteur ». L'environnement hors ligne est ainsi indépendant du dossier Python de uv dans le profil.
- Le préchargement reste dans les installeurs (réseau autorisé), pas dans l'application (AD-13). Il lit les `uv.lock` du contenu plutôt qu'une liste figée : un futur verrou d'état de scénario (version vulnérable puis corrigée, Epic 8) est préchargé sans changer les installeurs.
- Une somme fausse arrête toute l'installation, à l'étape « gitleaks », comme sous macOS et Linux (story 1.7). Rien n'est extrait, et l'archive est supprimée pour que la relance la retélécharge.
- Sous Windows, la somme SHA-256 et l'extraction passent par .NET (`Get-Sha256`, `ZipFile`), pas par `Get-FileHash` ni `Expand-Archive`. Ces modules manquent quand `PSModulePath` vient de PowerShell 7, ce qu'a montré le runner Windows.
- En CI, sous `unshare -n`, le premier `sudo` vide l'environnement : `WDS_DATA_DIR`, `WDS_EXERCISE_UV` et `WDS_EXERCISE_DATA` sont repassés par `env`. Avant ce correctif, l'étape « Scénarios sans réseau » ne testait pas vraiment le venv verrouillé.
- Sous Windows ARM64, c'est l'archive x64 qui est installée (émulation). Le nom d'une archive arm64 Windows n'est pas garanti dans les releases gitleaks.
- La garde réseau est un hook d'audit Python, pas une isolation du système : elle couvre les outils et les tests Python du gabarit, sans droits administrateur et sur les trois OS. `unshare -n` reste le contrôle fort en CI Linux.
- Le diagnostic contrôle les outils de la chaîne dans l'environnement de l'application (groupe `chain`, mêmes versions que le `uv.lock` du gabarit, ce que vérifie le test de cohérence). Le venv d'un espace se contrôle par `resolve(..., venv=)` au moment de l'utiliser.

## Reports

- Station 1 (story 7.2 et suivantes) : appeler `toolrun.sync_environment` à l'ouverture d'un espace, puis `run_tool(..., venv=toolrun.venv_dir(espace))` pour ruff, pytest et pre-commit. Un `mismatch` du venv doit rendre l'étape indisponible.
- `llmrun` (Epic LLM) : lancer le code d'exercice sans `WDS_NETGUARD` et avec les variables de proxy de l'apprenant.
- La garde ne voit pas les connexions ouvertes par du code natif hors Python, ni par un sous-processus non Python. Une isolation du système (par exemple un pare-feu applicatif) demanderait des droits administrateur : hors périmètre.
- Préchargement des verrous d'états de scénario vulnérables puis corrigés : automatique dès qu'un `uv.lock` existe sous `content/` (Epic 8, story 8.2 en cours). Rien à faire ici.

## À vérifier sur poste réel

1. Windows 11 sans droits administrateur : la commande du README installe gitleaks 8.30.1 dans `%LOCALAPPDATA%\WaveDevSecOps\tools\gitleaks\gitleaks.exe`. `gitleaks version` affiche 8.30.1.
2. `%LOCALAPPDATA%\WaveDevSecOps\uv-cache\python` contient un CPython 3.14, et `uv-cache` contient les roues des gabarits.
3. Réseau coupé (Wi-Fi désactivé) : `uv run --project <app> python .github/scripts/verifier_hors_ligne.py` réussit, `WDS_DATA_DIR` désignant le dossier de données.
4. Derrière un proxy d'entreprise (`HTTPS_PROXY`, `UV_SYSTEM_CERTS=true`) : le préchargement et le téléchargement de gitleaks passent.
5. Archive gitleaks altérée à la main dans `cache\downloads` (installation interrompue puis relancée) : message « ne correspond pas », rien dans `tools\gitleaks`.
6. Le diagnostic affiche le groupe « Outils de la chaîne (v0.2+) », tous les outils « Prêt » après installation. Après `uv pip install ruff==0.1.0` dans l'app, ruff passe en « Environnement abîmé » avec `uv sync` comme marche à suivre.
7. macOS (Apple Silicon) et Linux : mêmes points 2, 3 et 6 avec `install.sh`.
8. Lancement par le chemin complet de uv sans `~/.local/bin` dans le PATH : l'ouverture d'un espace crée bien le venv (uv retrouvé par `UV`, posé par `uv run`).

## Revue

Revue unique (Opus) après rebase sur `main` (stories 2.2 et 8.2), sans conflit.

- medium · second avis 1 · corrigé · la garde acceptait tout nom commençant par `127.` (`127.evil.example`). Seuls `localhost` (et ses alias) et les adresses IP littérales loopback (`ipaddress`, `::1` et `::ffff:127.x` compris) passent.
- medium · second avis 2 · corrigé · seul `socket.connect` était audité. `socket.sendto`, `socket.sendmsg` et la résolution d'un nom non loopback (`getaddrinfo`, `gethostbyname[_ex]`) sont refusés. Tests : sous-processus UDP et DNS, plus une table de 14 cas sur le hook.
- low · second avis 3 · noté · `python -S` ou du code natif contournent la garde : c'est un garde-fou pédagogique, pas un bac à sable. La limite est écrite dans la docstring du module posé dans le venv. La preuve reste la CI sous `unshare -n`.
- low · second avis 4 · noté · la coupure réseau n'est prouvée qu'en CI Linux (`unshare -n`). Sous Windows et macOS, la garde Python et le point 3 de « À vérifier sur poste réel » en tiennent lieu.
- low · second avis 5 · rejeté · le groupe `dev` (ruff, pytest) est inclus dans `chain` aux mêmes versions. `default-groups = ["dev", "chain"]` n'installe donc rien de plus chez l'apprenant.
- low · second avis 6 · corrigé · un paquet qui déclare la commande `<id>` dans `console_scripts` sans exécutable dans le venv passe en « Environnement abîmé ». Un greffon sans commande (pytest-cov) reste « Prêt ».
- low · second avis 7 · corrigé · uv absent du PATH est cherché dans `UV` (posé par `uv run`, la commande de lancement donnée par l'installeur), puis dans `UV_INSTALL_DIR` ou `~/.local/bin`.
- low · second avis 8 · rejeté · gitleaks ne publie pas d'archive Windows arm64 (seulement x64, x32, armv6 et armv7). L'archive x64 sous émulation reste le bon choix.
- low · second avis 9 · rejeté · la somme et l'archive viennent de la même release, comme la spec le demande.
