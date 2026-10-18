# Revue d'actualité technique — ARCHITECTURE-SPINE (2026-10-18)

Méthode : PyPI JSON, code source GitHub (pip-audit, gitleaks, diff-cover, git), documentation officielle (git-scm, Ollama, FastAPI, gitforwindows.org). Les points déjà vérifiés par l'auteur ne sont qu'échantillonnés.

Verdict : l'essentiel tient ; une erreur de seuil (gitleaks), un écart de mécanique (SBOM pip-audit) et quelques points à tester avant d'être figés.

## Fausses ou risquées

| Affirmation | Statut | Correction / source |
|---|---|---|
| AD-16 : gitleaks ≥ 8.19.0 « commande `gitleaks git` » ; AD-4/AD-9 supposent `git --pre-commit --staged` | **Risquée** | `gitleaks git` apparaît en 8.19.0, mais le correctif « handle pre-commit and staged » (#1533) est dans 8.20.0. Relever le minimum à 8.20.0 (la version provisionnée 8.30.1 n'est pas touchée). https://api.github.com/repos/gitleaks/gitleaks/releases (notes v8.19.0 et v8.20.0) |
| AD-11 : « SBOM produit par pip-audit (`-f cyclonedx-json`) dans le même job » que `-f json` | **Fausse en l'état** | `-f` n'accepte qu'un format par exécution (`_cli.py`). Il faut deux exécutions pip-audit (une `-f json` pour les constats, une `-f cyclonedx-json` pour le SBOM) ; le coût est nul hors ligne, mais `pipeline.yaml` doit porter deux commandes machine. https://github.com/pypa/pip-audit/blob/main/pip_audit/_cli.py |
| AD-15 : PortableGit « extraite sans droits administrateur » | **Incomplète** | Les options documentées sont `-y -gm2 -InstallPath="C:\\double\\antislash"` ; `-o` (style 7z) n'est pas documenté pour l'auto-extractible. À consigner dans la story d'installation et à tester. https://gitforwindows.org/zip-archives-extracting-the-released-archives |
| Stack : pywebview 6.2.1 sous Python 3.14 | **Risquée** | Les classifieurs de pywebview s'arrêtent à 3.13. Sous Windows il dépend de `pythonnet` (non épinglé) ; pythonnet 3.2.1 annonce 3.14 (`>=3.11,<3.16`). Acceptable car extra facultatif, mais ajouter un test CI Windows de l'extra `window`. https://pypi.org/pypi/pywebview/json et https://pypi.org/pypi/pythonnet/json |

## Confirmées

- `git merge-tree --write-tree` : nouveau mode annoncé dans les notes de version 2.38.0.
- `GIT_CONFIG_COUNT/KEY_n/VALUE_n` : portée « command », priment sur les fichiers système, global et du dépôt, seul `git -c` les surpasse (https://git-scm.com/docs/git-config). Introduit en 2.31 (connaissance, non relue). Les notes 2.32 citent `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` (donc ≥ 2.32, compatible avec le minimum 2.38).
- pip-audit : `--no-deps`, `--disable-pip`, `--osv-url` (ou `PIP_AUDIT_OSV_URL`), format `cyclonedx-json` existent. Le service OSV fait un `POST` par paquet sur `osv_url`, valeur par défaut `https://api.osv.dev/v1/query` ; le chemin `/osv/v1/query` du spine est donc correct et `querybatch` n'est pas utilisé. Le point local doit gérer la pagination (`next_page_token`) si le client la suit. Rappel : `--no-deps` exige un fichier de dépendances (`-r`) épinglé.
- gitleaks : `git` avec `--staged` et `--pre-commit` existe (cmd/git.go).
- diff-cover : `--format json:report.json` et `--fail-under` existent (`--json-report` est déprécié) ; diff-cover 10.6.0.
- bandit `-f json` : option standard ; bandit 1.9.4 déclare 3.14.
- Python 3.14 : fastapi 0.144.0, uvicorn 0.54.0, watchfiles 1.3.0, bandit, pip-audit, diff-cover déclarent 3.13 et 3.14. pre-commit 4.7.0 : `>=3.11`, sans classifieur (sans risque).
- `fastapi.sse.EventSourceResponse` existe (https://fastapi.tiangolo.com/reference/sse/) ; accepte n'importe quelle méthode HTTP. Le spine n'impose pas son usage ; `Last-Event-ID` reste à gérer par l'application.
- Ollama : `http://localhost:11434/v1/` et `/v1/chat/completions` pris en charge (https://docs.ollama.com/api/openai-compatibility).
- Versions PyPI de la table Stack : toutes cohérentes avec PyPI au 2026-10-18 (échantillon : fastapi, uvicorn, bandit, pip-audit, diff-cover, watchfiles).

## Invérifiables ici (connaissance, à tester en CI)

- `repo: local` + `language: system` sans réseau, `PRE_COMMIT_HOME` : comportement connu de pre-commit, non relu dans la documentation courante.
- `pixi global install git` sans droits administrateur : installation dans `~/.pixi` (documenté), mais la présence des traductions françaises (`share/locale/fr`) dans le paquet conda-forge git n'est pas confirmée ; le diagnostic AD-3/AD-16 la sonde, donc le risque est couvert.
- PortableGit contient bien traductions et bash : plausible, non relu dans les actifs de la release.
- `xcode-select -p` : la recherche n'a pas fourni le code de sortie. Comportement connu : code 2 et message d'erreur si aucun outil installé, 0 sinon, sans ouvrir de fenêtre. À tester sur un Mac vierge (CI `macos-latest` a les outils, donc ce cas n'y sera pas couvert).
- `UV_OFFLINE`, `PIP_NO_INDEX`, `uv sync --offline` depuis un cache préchargé : non relu ; à valider par un test d'intégration (le cache doit contenir aussi les roues de Python 3.14 géré par uv, sinon `uv sync` hors ligne échoue sur l'interpréteur).
