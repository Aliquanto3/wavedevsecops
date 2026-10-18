---
story: "3.5"
key: 3-5-protéger-une-branche-pour-de-vrai-par-un-hook-pre-receive
title: Protéger une branche pour de vrai par un hook pre-receive
status: review
branch: story/3-5-hook-pre-receive
ad: [AD-8, AD-9]
---

# Story 3.5 : Protéger une branche pour de vrai par un hook pre-receive

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 3.5 » ; FR-8, FR-22 (mécanisme), NFR-5.

## Livré

- Paquet `hooks/` : `hook_script(nom, python)` génère le script (`#!/bin/sh` puis une ligne `exec "<python>" -m wavedevsecops.hooks <nom> "$@"`, LF, chemin posix entre guillemets, sans bash, jamais copié du dépôt de l'application) ; `main(argv)` route vers `HANDLERS[nom]` ; `__main__.py` est le point d'entrée appelé par le script.
- Op `install_hooks` (`scenarios/ops/install_hooks.py`) : `hooks` (défaut `[pre-receive]`, noms connus de `hooks.HOOK_NAMES`) ; écrit `hooks/<nom>` par `wsfs.write_executable` (atomique, LF, bit d'exécution) avec `sys.executable`. Produit `output:hook-<nom>` (aucun type d'AD-2 ne désigne un hook).
- Hook `pre-receive` : lit `<ancien> <nouveau> <ref>` sur stdin ; pour chaque `refs/heads/<b>` où `github_sim.direct_push_blocked(layout, b)` (protection avec `block_direct_push`), écrit en français sur stderr « La branche « b » est protégée : un push direct est refusé. » et sort en code 1 ; git l'affiche avec `remote:`. Suppression et création de la branche sont refusées comme une mise à jour ; étiquettes et lignes mal formées sont ignorées.
- Distinction du dépôt (AD-9) : le point d'entrée regarde son dossier de travail ; il n'agit que dans un dépôt nu (`HEAD` et `objects/` à la racine, pas de `.git`) dont le parent est l'espace. Depuis `repo/`, il ne fait rien (code 0). Le contrôle par `GIT_DIR` est écarté : la convention « Réglages » interdit à `hooks` de lire l'environnement.
- Terminal : après un `git push` en échec, si une branche visée (refspec, ou branche courante) est protégée selon `github.json`, il ajoute « Refusé par la protection de `main` : tout passe par une PR. » (clé `protected_branch` de `content/terminal-allowlist.yaml`). La décision vient de l'état du GitHub simulé, pas de l'analyse de la sortie de git (AD-2).
- Ajouts localisés : `github_sim.direct_push_blocked(layout, branche)` (lecture seule ; `github.json` illisible = pas de blocage) ; `wsfs.write_executable`.

## Contrat pour 5.7 et 7.3

- Ajouter un hook : l'ajouter à `hooks.HOOK_NAMES` et à `hooks.HANDLERS` (fonction `(cwd, stdin, stderr) -> code`). `install_hooks` le pose sans autre changement.
- Le hook ne modifie rien ; il lit l'état par `github_sim` et refuse par un code non nul et un texte français sur stderr.
- `pre-commit` (7.3) agit dans `repo/` : le dossier de travail y est la racine du dépôt (un dossier `.git`) ; `origin_layout` rend `None` pour lui. Le hook `pre-commit` doit appeler gitleaks par `toolrun`, pas par un processus direct.
- Push forcé de 5.7 : `--force` ne contourne pas `pre-receive`. Sur une branche non protégée, le hook laisse passer ; l'écrasement du collègue se joue sur `origin` (fast-forward refusé par git sans `--force`).
- Sur le dépôt `origin.git`, git retire `GIT_CONFIG_COUNT` de l'environnement de `receive-pack` pour un push vers un chemin local : le `core.hooksPath` forcé par `gitio` n'y arrive pas. `install_hooks` écrit donc `core.hooksPath=../hooks` (relatif, espace déplaçable) dans la configuration d'`origin.git`. Un hook côté `origin` n'est actif que si `install_hooks` a été joué.
- Le merge de `github_sim` (`update-ref` sur `origin.git`) ne passe pas par `receive-pack` : il n'est jamais bloqué par le hook ; ni `commit_on_origin` (collègue, agent).
- L'empreinte (AD-6) couvre le contenu de `hooks/` : il contient le chemin de Python de la machine ; un instantané ne se rejoue donc pas d'un poste à un autre (les instantanés sont locaux).

## Décisions

- `hooks_enabled` dans `run.json` n'est pas livré : aucune étape ne le déclare encore ; la présence du script dans `hooks/` vaut activation. À ajouter avec la première étape qui active un hook à la volée.
- Message du terminal ciblé par l'état (branche protégée) et non par la raison réelle du refus : un push en échec vers une branche protégée est expliqué même si la cause est autre (non fast-forward). Cas accepté : sur une branche protégée, le push direct est refusé de toute façon.

## Reports

- Étape qui active ou désactive un hook (`hooks_enabled`) : avec 7.3.
- Hook `pre-commit` (gitleaks) : story 7.3.

## Tests

`tests/test_hooks.py` : script d'une ligne en LF sans bash (et bit d'exécution hors Windows), hook inconnu refusé, push direct sur `main` refusé par git (`remote:`, ref inchangée), branche non protégée ou `block_direct_push: false` acceptées, merge de PR hors hook, point d'entrée muet depuis `repo/`, `github.json` illisible sans blocage. `tests/test_terminal.py` : refus du terminal et message explicatif, push d'une autre branche intact. La CI de branche exécute ces tests sur Windows (sh de PortableGit), macOS et Linux.
