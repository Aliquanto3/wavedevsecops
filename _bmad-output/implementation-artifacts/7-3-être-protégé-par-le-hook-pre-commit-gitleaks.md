---
story: "7.3"
key: 7-3-être-protégé-par-le-hook-pre-commit-gitleaks
title: Être protégé par le hook pre-commit gitleaks
status: review
branch: story/7-3-pre-commit-gitleaks
ad: [AD-1, AD-4, AD-9, AD-10, AD-13, AD-14]
---

# Story 7.3 : Être protégé par le hook pre-commit gitleaks

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 7.3 » ; spine AD-4, AD-9, AD-10, AD-14 ; FR-21, FR-33, UX-DR20, UX-DR37. S'appuie sur 3.5 (paquet `hooks`, `install_hooks`, `hooks.refresh`), 7.1 (gitleaks provisionné, `tools.toml`) et 7.2 (section `tools`, `tool-output`, `evidence_seen`).

## Livré

- **Hook `pre-commit`** (`hooks.pre_commit`, ajouté à `HOOK_NAMES` et `HANDLERS`) : même script d'une ligne que `pre-receive` (`install_hooks` avec `hooks: [pre-commit]`). Il n'agit que dans `repo/` (un dossier `.git`, nommé `repo`) et s'il y a un `.pre-commit-config.yaml` ; la racine des données se déduit de l'espace (`<data>/workspaces/<parcours>/<id>`), `hooks` ne lit pas l'environnement. Il lance le vrai `pre-commit run` par `toolrun.spawn_tool` (AD-1 : aucun processus créé par `hooks`), recopie sa sortie sur stderr (git l'affiche telle quelle) et sort avec le code de `pre-commit`.
- **Environnement du hook** (`toolrun.hook_environment`, appelé par `spawn_tool` pour `pre-commit` seulement) : `offline_environment` (dont `PRE_COMMIT_HOME` dans `cache/`), le dossier de gitleaks et celui d'uv résolus par le registre en tête du PATH (les hooks `language: system` du gabarit les cherchent là), `UV_PROJECT_ENVIRONMENT` vers `cache/venv/`. Une seule clé PATH, quelle que soit sa casse (Windows).
- **Outil manquant** : `pre-commit` (environnement d'exercice) ou gitleaks (si la configuration le cite) introuvable ou abîmé : le commit est refusé, en français, avec la raison du diagnostic et un renvoi au diagnostic.
- **Cause du refus sans analyser la sortie** (AD-2, AD-10) : après un échec de `pre-commit run`, le hook relance gitleaks en mode machine sur l'index (`toolrun.findings.collect("gitleaks", ...)` : `--exit-code 3 --redact --report-format json`, rapport dans `cache/`, effacé) et écrit `cache/hook-pre-commit.json` (`tool` = `gitleaks` ou `pre-commit`, fichiers et lignes). Code 3 = secret trouvé, autre code non nul = panne de l'outil (aucun secret attribué) : même convention que le pipeline de 7.4 (`gitleaks dir --exit-code 3`).
- **Terminal** (`terminal/__init__.py`, ajouts localisés) : pour `git commit` quand le hook de l'application est posé, la sortie est tenue jusqu'à la fin ; si la trace d'un refus existe (effacée avant chaque commit), elle est émise en un bloc `tool-output` étiqueté `gitleaks` (ou `pre-commit`), puis « Code de sortie : 1 », puis l'alerte `role="alert"` « Refusé par le hook pre-commit : gitleaks a trouvé un secret. Le commit n'a pas été créé. » suivie d'un lien `fichier:ligne` (`path:worktree:<chemin>`, 3 liens au plus). Sinon la sortie est émise comme avant. Un autre hook en échec : « Refusé par le hook pre-commit. Le commit n'a pas été créé. », sans lien. Le fait `evidence_seen{secret-scan}` est soumis à l'affichage (clé `hook_barriers` du fichier de la liste blanche).
- **Front** (`terminal.js`) : l'alerte `refused` rend ses `spans` en boutons-liens, comme le bloc `tool-output` (fonction commune `appendWithLinks`).
- **`pre-commit install` refusé** (`parse.py`, messages du fichier de la liste blanche) : `install`, `uninstall`, `install-hooks` -> « « pre-commit install » est refusé : les hooks sont posés par le scénario, pas par vous… » suivi de la liste acceptée. Les autres `pre-commit ...` restent « pas une commande de ce terminal » (`pre-commit run` n'est pas ajouté à la section `tools`).
- **Scénario `secret-dans-un-commit.A`** (station 1, `section: stations`, les deux parcours, `tools: [git, gitleaks, pre-commit]`) : gabarit du parcours, configuration `.pre-commit-config.yaml` réduite au seul hook gitleaks (même entrée que le gabarit), commit et push de `main`, puis `install_hooks [pre-commit]`, puis un fichier non committé `src/inventory/reappro.py` avec une fausse clé AWS (`AKIAQ3XTR7WUDNB4HK6P`, détectée par la règle `aws-access-token`). Étape `repo_state` : fichier présent, un commit en avance sur `origin/main`, index propre. Empreintes de référence ajoutées.
- **CI** : `.github/scripts/provisionner_gitleaks.py` pose le gitleaks officiel (somme vérifiée par `checksums.txt`) dans `WDS_EXERCISE_DATA/tools/gitleaks/` avant `pytest`, pour le test du vrai hook.

## Décisions

- Configuration du scénario réduite à gitleaks : le hook ruff du gabarit passe par `uv run`, et le hook pytest lancerait les tests du gabarit à chaque commit ; ruff et pytest ont leurs scénarios (7.2). Le hook lance toute la configuration du dépôt telle quelle : un scénario futur peut garder ruff.
- Sortie du commit tenue jusqu'à la fin quand le hook de l'application est posé (au lieu de couler au fil de l'eau) : il faut savoir si le hook a refusé pour la présenter en bloc `tool-output` sans la dupliquer. Seul un script qui porte l'appel `-m wavedevsecops.hooks pre-commit` est reconnu (`hooks.pre_commit_installed`) ; tout autre hook garde le flux au fil de l'eau.
- Le bloc `tool-output` porte toute la sortie de `pre-commit run` (qui cite gitleaks et son rapport), étiquetée `gitleaks` ; les `spans` du bloc sont vides : gitleaks écrit `File:` et `Line:` sur deux lignes, jamais `fichier:ligne`. Le lien vers la ligne est celui de l'alerte (AC).
- `hooks_enabled` dans `run.json` reste non livré (report de 3.5) : la présence du script dans `hooks/` vaut activation.
- `pre-commit install` est refusé par la garde même si le scénario ne déclare pas `pre-commit` : l'explication ne dépend pas de la déclaration.

## Reports

- Étape qui active ou désactive un hook (`hooks_enabled`) : avec la première étape qui en a besoin.
- Lien vers la bonne ligne dans la vue Code : vue Code (2.8) et segment ligne de l'`element_id` (comme 7.2).
- `gitleaks` et `pre-commit run` tapés dans le terminal : non livrés (les critères ne les demandent pas) ; la section `tools` les accueillerait.
- Pipeline simulé (7.4) : lit `gitleaks dir --exit-code 3` ; aucune dépendance de code entre les deux stories.

## À vérifier sur poste réel

1. Windows (sh de Git), macOS, Linux : `git add src/inventory/reappro.py` puis `git commit -m "..."` dans « Voir un secret refusé avant le commit » : bloc `gitleaks`, alerte avec lien, aucun commit dans le graphe.
2. Retirer la clé, recommiter : le commit passe, l'étape passe.
3. Durée d'un commit avec le hook (démarrage de Python, de `pre-commit` et de gitleaks) : à mesurer.
4. Gitleaks retiré de `<data>/tools/` : le commit est refusé avec le message du diagnostic.

## Tests

`tests/test_pre_commit_hook.py` : script du hook d'une ligne en LF, empreinte indépendante du chemin de Python et `refresh` ; configuration du scénario ; `pre-commit install|uninstall|install-hooks` refusés ; refus par un faux hook reconnu comme le vrai (bloc, alerte, lien, ordre des sorties, aucun commit, `evidence_seen`, autre hook sans lien, commit qui passe ensuite, `--no-verify`) ; outil manquant (pre-commit, gitleaks) ; hook muet hors `repo/` ou sans configuration ; `hook_environment` (PATH, casse) ; constats gitleaks (`parse_gitleaks`, codes 0, 3 et 1 de l'exécution machine) ; vrai `pre-commit run` et vrai gitleaks dans les deux parcours si `WDS_EXERCISE_UV=1` et gitleaks est posé dans `WDS_EXERCISE_DATA` (CI sur les trois systèmes ; local Windows : passé).

## Revue

Revue Opus (une passe, après rebase sur `origin/main` : `content/fingerprints.json` régénéré, stable au second passage).

- H1 (second avis) · secret en clair dans `tool-output` faute de `--redact` · **écarté sur le fond, test corrigé** : sans `-v`, `gitleaks git --pre-commit --staged` n'écrit que le résumé (« leaks found: 1 »), vérifié sur un vrai gitleaks ; le test du vrai hook était bien une tautologie, il vérifie maintenant que la clé n'apparaît dans aucune sortie émise (CI des trois OS).
- M2 (second avis) · `git commit --no-verify` validait l'étape avec la clé committée · **corrigé** : refusé avec une explication (`no_verify`) quand le hook de l'application est posé ; test.
- M3 (second avis) · configuration retirée ou vidée désactivait le hook en silence · **corrigé** : `hooks.config_problem` refuse une configuration absente (comme le vrai `pre-commit`), illisible ou sans hook, avec un message en français et la trace `pre-commit` (alerte « Refusé par le hook pre-commit ») ; tests paramétrés. Reste ouvert : remplacer gitleaks par un autre hook admis (`uv run …`) ; la parade complète est une condition de contenu dans `repo_state` (« la clé n'est pas dans le commit »), **reportée** à la première étape qui en a besoin.
- M4 (second avis) · `repo: https://…` faisait cloner `pre-commit` hors du garde réseau (AD-13) · **corrigé** : seuls `repo: local` (`language: system`, entrée `gitleaks` ou `uv`) et `meta` sont admis ; les configurations du gabarit et du scénario passent (test).
- Revue · `entry:` arbitraire (`curl`, `powershell`…) dans un hook local contournait la liste blanche du terminal · **corrigé** par la même règle que M4.
- L5 (second avis) · l'alerte `refused` rend aussi les liens calculés par le linker (nom de branche) · **écarté** : mêmes liens que les autres lignes du terminal, sans effet de bord.
- L6 (second avis) · somme de contrôle de gitleaks tirée de la même release que l'archive · **noté** : CI seulement ; l'installeur (7.1) porte sa propre vérification.
- L7 (second avis) · conflit `fingerprints.json` · **corrigé** au rebase.
- Complexité : 0 constat (la sortie tenue d'un commit est bornée par une commande).
