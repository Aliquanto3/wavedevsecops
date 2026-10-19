# WaveDevSecOps

> 🟢 **Version 0.2.0** : le socle git de la v0.1.0, plus les stations 1 à 3 de la chaîne DevSecOps (poste local, PR et CI, sécurité et qualité), dans les deux parcours, hors ligne. Notes de version : [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md).

Application pédagogique locale pour apprendre git et GitHub, puis la chaîne CI/CD et les
concepts DevSecOps, pensée pour les personnes qui codent avec des agents (vibe coding) et
doivent comprendre ce que l'agent fait sur leur dépôt. Pédagogie inspirée de
[WaveStack](https://github.com/Aliquanto3/agentic-harness-training-demo).

## Ce que l'application propose

La version 0.2.0 couvre le socle git et les stations 1 à 3 de la chaîne DevSecOps. La station 4 (livraison) arrive ensuite (voir [Jalons](#jalons)).

- **Du vrai git, hors ligne** : un dépôt bac à sable, un dépôt distant local et un GitHub
  simulé (PR, revue, merge, commits d'un collègue), dans des vues synchronisées.
- **Deux façons d'apprendre** : taper les commandes et voir leur effet ; puis lire ce qu'un
  agent scénarisé a fait sur le dépôt (erreurs réalistes comprises) et décider.
- **Quiz** où la mauvaise commande est exécutée pour de vrai, expliquée, puis annulée.
- **Deux parcours** : un code qui appelle un LLM puis devient un mini-harnais (prompt système,
  outils, boucle), ou un code minimal sans IA.
- **Chaîne DevSecOps en quatre stations** (les stations 1 à 3 sont livrées en v0.2, la 4 en v0.3), avec des outils légers (ruff, pytest, pre-commit,
  gitleaks, bandit, pip-audit) : poste local, PR et CI, sécurité et qualité, livraison.
  Jenkins, GitHub Actions, GitLab CI et Sonar sont montrés comme équivalents.
- **Barrières de la v0.2**, chacune avec un scénario où elle bloque : gitleaks (secret), ruff et
  pytest, protection de `main` et revue obligatoire, bandit (code vulnérable), pip-audit et SBOM
  (dépendance vulnérable), `uv lock --check`, quality gate de 80 % de couverture du nouveau code.
- **Savoir en parler à un RSSI** : scénario d'entretien et fiche barrière → risque → preuve. (v0.3)

## Installer sous Windows (sans droits administrateur)

Dans PowerShell (Windows 10 ou 11), un compte standard suffit :

```powershell
[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; $w = New-Object Net.WebClient; if ($env:HTTPS_PROXY) { $w.Proxy = New-Object Net.WebProxy($env:HTTPS_PROXY, $true); $w.Proxy.UseDefaultCredentials = $true }; iex ([Text.Encoding]::UTF8.GetString($w.DownloadData('https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/install.ps1')).TrimStart([char]0xFEFF))
```

L'installeur place uv dans votre profil, récupère l'application dans
`%LOCALAPPDATA%\WaveDevSecOps\app` (clone avec `core.autocrlf=false`), installe PortableGit
seulement si git est absent ou antérieur à 2.38, lance `uv sync`, précharge le cache uv
(`uv-cache` : Python géré et paquets des exercices, pour travailler ensuite hors ligne), installe
gitleaks (archive vérifiée par la somme SHA-256 de la release), puis écrit `install.json`.
Relancez la même commande pour mettre à jour : `progress.json` est conservé, et une
installation interrompue reprend là où elle s'est arrêtée.

- **Derrière un proxy** : posez `HTTPS_PROXY` (et `NO_PROXY=127.0.0.1,localhost`) avant la commande ;
  la commande et l'installeur passent par lui (sinon par le proxy système), et l'installeur pose `UV_SYSTEM_CERTS=true`.
- **Sans git ou si le clone échoue** : `$env:WDS_INSTALL_METHOD = 'zip'` avant la commande.
- **Autre dossier** : `$env:WDS_DATA_DIR`. Autre branche ou version : `$env:WDS_INSTALL_REF`.
- **Version 0.2.0 exactement** (la commande ci-dessus installe la tête de `main`) :
  `$env:WDS_INSTALL_REF = 'v0.2.0'` avant la commande, et `/v0.2.0/install.ps1` à la place de `/main/install.ps1`.

## Installer sous macOS et Linux (sans droits administrateur)

Dans un terminal, un compte standard suffit (aucun `sudo`) :

```sh
curl -fsSL https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/install.sh | sh
```

L'installeur (`sh` POSIX) place uv dans votre profil, récupère l'application dans
`~/Library/Application Support/WaveDevSecOps/app` (macOS) ou `~/.local/share/WaveDevSecOps/app`
(Linux, ou `$XDG_DATA_HOME`), avec un clone `core.autocrlf=false`. Si git est absent ou antérieur à 2.38, il
installe pixi 0.82.0 dans le profil puis git (conda-forge) ; sous macOS, il ne lance `/usr/bin/git`
qu'après `xcode-select -p`, pour ne pas ouvrir la fenêtre d'installation des outils Xcode. Il lance `uv sync`,
précharge le cache uv (`uv-cache` : Python géré et paquets des exercices, pour travailler ensuite hors ligne),
installe gitleaks (archive vérifiée par la somme SHA-256 de la release), puis écrit `install.json`.
Relancez la même commande pour mettre à jour : `progress.json` est conservé, et une installation
interrompue reprend là où elle s'est arrêtée.

- **Derrière un proxy** : `export HTTPS_PROXY=http://proxy.entreprise:8080` (et `NO_PROXY=127.0.0.1,localhost`) avant la
  commande ; `curl` et l'installeur passent par lui, et l'installeur pose `UV_SYSTEM_CERTS=true`.
- **Sans git ou si le clone échoue** : `export WDS_INSTALL_METHOD=zip` avant la commande (archive `tar.gz` de GitHub).
- **Autre dossier** : `WDS_DATA_DIR`. Autre branche ou version : `WDS_INSTALL_REF`.
- **Version 0.2.0 exactement** (la commande ci-dessus installe la tête de `main`) :
  `curl -fsSL https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/v0.2.0/install.sh | WDS_INSTALL_REF=v0.2.0 sh`.

## Confidentialité et réseau

L'application n'envoie aucune télémétrie et ne fait aucun appel réseau, sauf l'exécution facultative
du code LLM (parcours LLM, sur confirmation de votre part) ; seules l'installation et sa mise à jour
téléchargent (uv, git si besoin, les paquets, gitleaks). Le serveur n'écoute que sur `127.0.0.1`,
et toute l'interface est servie par l'application elle-même, sans ressource externe.

## Lancer

Une fois l'installation faite, depuis le dossier de l'application (`app`, voir plus haut) :

```sh
uv run wavedevsecops
```

L'application ouvre votre navigateur sur une adresse locale protégée par un jeton. Relancer la
commande rouvre l'instance déjà en cours. Option : `uv run wavedevsecops --window` (fenêtre dédiée,
après `uv sync --extra window`).

## Temps d'installation

L'installeur mesure sa durée et l'écrit dans `install.json` (champ `duration_s`, dossier des
données). Objectif : moins de 10 minutes, sans droits administrateur (AD-18, SM-2). La mesure
chronométrée de la v0.1.0 est consignée dans les [notes de version](docs/releases/v0.1.0.md#temps-dinstallation).

## Jalons

`v0.1` socle git (version 0.1.0) → `v0.2` stations 1 à 3 (version 0.2.0) → `v0.3` livraison → `v1.0` présentation.

## Documents

- [Idée forgée](docs/forge/forged-idea.md) : décisions, options rejetées, points à trancher.
- [Rapport de la session](docs/forge/forge-report.html).

## Licence

Apache 2.0, voir [LICENSE](LICENSE) et [NOTICE](NOTICE).
