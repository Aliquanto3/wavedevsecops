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
- L'empreinte (AD-6) couvre le contenu de `hooks/` sans le chemin de Python (`hooks.canonical_script`) : la référence d'AD-18 d'un scénario qui joue `install_hooks` vaut sur les trois systèmes.

## Décisions

- `hooks_enabled` dans `run.json` n'est pas livré : aucune étape ne le déclare encore ; la présence du script dans `hooks/` vaut activation. À ajouter avec la première étape qui active un hook à la volée.
- Message du terminal : il n'apparaît que si la mise à jour a atteint le hook (suppression, push forcé, création ou avance rapide, d'après les refs de `repo/` et d'`origin.git/`). Un push sans avance rapide, refusé par git avant tout hook, n'est pas attribué à la protection (revue). La sortie de git n'est toujours pas analysée (AD-2).
- Pannes : `github.json` illisible laisse passer avec un avertissement en français ; toute autre erreur du hook refuse le push avec un texte en français qui renvoie au diagnostic (AD-9), sans trace Python.
- Interpréteur figé dans le script : le terminal appelle `hooks.refresh` avant chaque `git push`, qui réécrit un hook dont le chemin de Python n'est plus celui de l'application (environnement recréé ou déplacé). Le chemin est échappé pour sh (`\`, `"`, `$`, accent grave).

## Reports

- Étape qui active ou désactive un hook (`hooks_enabled`) : avec 7.3.
- Hook `pre-commit` (gitleaks) : story 7.3.

## Tests

`tests/test_hooks.py` : script d'une ligne en LF sans bash (et bit d'exécution hors Windows), hook inconnu refusé, push direct sur `main` refusé par git (`remote:`, ref inchangée), branche non protégée ou `block_direct_push: false` acceptées, merge de PR hors hook, point d'entrée muet depuis `repo/`, `github.json` illisible sans blocage. `tests/test_terminal.py` : refus du terminal et message explicatif, push d'une autre branche intact. La CI de branche exécute ces tests sur Windows (sh de PortableGit), macOS et Linux.

## Revue

Revue Opus (une passe), sur la branche rebasée sur `origin/main`. Second avis Haiku repris constat par constat.

| Sév. | Source | Constat | Suite |
|---|---|---|---|
| high | revue | Empreinte de `hooks/` dépendante du chemin de Python : le premier scénario qui jouera `install_hooks` aurait une référence d'AD-18 différente sur chaque système (CI rouge), au-delà des seuls instantanés (L9 sous-estimé). | Corrigé : `hooks.canonical_script` dans `engine/fingerprint.py`. |
| medium | second avis M1 | Message « Refusé par la protection » affiché pour un push refusé sans avance rapide, avant le hook (prouvé). | Corrigé autrement que proposé : décision tirée des refs (le push a-t-il atteint le hook ?), pas de la sortie de git, pour respecter AD-2. |
| medium | second avis M2 | Interpréteur figé : environnement recréé ailleurs, `exec` en 127, tous les pushes refusés avec un message sh en anglais. | Corrigé : `hooks.refresh` avant chaque `git push` du terminal (le script reste d'une ligne, critère d'AD-9). |
| medium | second avis M3 | Exception imprévue du hook : trace Python en anglais sous `remote:`. | Corrigé : refus en français avec renvoi au diagnostic (AD-9) ; refus conservé par prudence. |
| low | second avis L4 | `github.json` illisible ignoré sans avertissement. | Corrigé : avertissement en français, le push passe. |
| low | second avis L5 | `git push --all` sans message de protection. | Corrigé : `--all` vise toutes les branches locales ; `--tags` seul n'en vise aucune. |
| low | second avis L6 | Texte du refus du hook en français en dur. | Rejeté : AD-9 exige un refus en français ; c'est une sortie de git, affichée telle quelle. |
| low | second avis L7 | Chemin de Python non échappé pour sh. | Corrigé : `\`, `"`, `$` et accent grave échappés (test). |
| low | second avis L8 | 2 à 4 s par push (import de pydantic via `github_sim`). | Reporté : AD-8 veut une lecture par `github_sim` ; à mesurer avec la story de performance avant d'alléger. |
| low | second avis L9 | Empreinte de `hooks/` dépendante du poste. | Voir le constat high, corrigé. |
| info | second avis | Contournements (HEAD:refs/heads/main, +main, suppression, --no-verify, tags, -c/-C/--git-dir/--receive-pack, confinement). | Confirmé sans faille. |
| — | revue | Complexité : 0 constat (le hook lit `github.json` une fois par push, au lieu d'une fois par ref). | — |
