---
story: "2.5"
key: 2-5-utiliser-les-commandes-de-fichiers-confinées-au-bac-à-sable
title: Utiliser les commandes de fichiers, confinées au bac à sable
status: review
branch: story/2-5-commandes-fichiers
ad: [AD-1, AD-3, AD-4, AD-18]
---

# Story 2.5 : Utiliser les commandes de fichiers, confinées au bac à sable

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.5 » ; spine AD-4 (liste blanche, modèle de menace), AD-18 (confinement sur les trois OS) ; FR-2, NFR-5, AR-5.

## Livré

- `content/terminal-allowlist.yaml` : la section `files` (laissée vide par la 2.4) déclare `ls [-a]`, `cat`, `echo`, `touch`, `mkdir [-p]`, `rm [-r|-R] [-f]`, `mv`, `cp [-r|-R]`, `pwd`, `clear` (options, nombre d'arguments, `read`, `globs` pour `rm`/`mv`/`cp`, `redirect` pour `echo`) et les messages associés. La phrase de refus cite déjà ces commandes (`accepted_files`).
- `terminal/allowlist.py` : modèle `FileCommandSpec` (par ajout ; `files` passe de `dict[str, Any]` à `dict[str, FileCommandSpec]`).
- `terminal/parse.py` : `FileCommand` et `check_file`. `parse_line` rend `GitCommand | FileCommand | None`. Une redirection `>` ou `>>` n'est admise qu'avec `echo`, une seule fois, en fin de ligne, avec un nom de fichier ; ailleurs elle reste refusée comme avant (git compris). Les options se valident contre la liste (regroupement `-rf` admis) ; pour `echo`, tout est du texte (`echo -n` affiche `-n`).
- `terminal/files.py` (nouveau) : exécution en Python, sans processus. Chaque chemin passe d'abord par `wsfs.check_relative(portable=True)` (lectures comprises : un nom réservé Windows comme `NUL`, `C:`, `\`, `..`, un chemin absolu ou `.git` est refusé avant d'ouvrir quoi que ce soit), puis par le confinement de `wsfs`. Refus de chemin : flux `refused`, code 2, explication française de `wsfs`. Autre échec (absent, dossier sans `-r`…) : flux `app` « commande : cause. action. » puis `Code de sortie : 1`. Un échec n'arrête pas les autres arguments.
- `wsfs` (ajouts en fin de module) : `SandboxFileError`, `list_dir` (`.git` jamais listé ; les noms à point seulement avec `-a`), `kind_of`, `read_text`, `append_text`, `touch`, `make_directory`, `remove_path`, `move_path`, `copy_path`, `expand_glob`. `rm` et `mv` agissent sur un lien symbolique lui-même, jamais sur sa cible ; `cp -r` copie les liens sans les suivre ; `rm -r` ne suit pas un lien contenu dans le dossier ; `cp` d'un lien sortant est refusé (la cible est résolue par `confine`). Un dossier ne se copie ni ne se déplace dans lui-même.
- Globs : `*` et `?` seulement dans `rm`, `mv`, `cp`, segment par segment, résolus par `wsfs` dans le bac à sable ; un nom à point n'est pris que par un motif à point, `.git` jamais. Motif sans correspondance : erreur (`rm -f` : silence). Plusieurs sources : la destination doit être un dossier existant. Les autres commandes reçoivent `*` et `?` tels quels (pas d'expansion).
- Écritures : `echo > f` / `echo >> f` passent par `wsfs.write_text` / `append_text` (UTF-8 sans BOM, LF).
- `terminal/__init__.py` : `_run_file` et un aiguillage dans `build_terminal_line` (aucune modification d'`AFTER_COMMAND_HOOKS`, du contrat ni du catalogue d'événements). `writes` = faux pour `ls`, `cat`, `pwd`, `clear` et `echo` sans redirection : seules ces lectures passent en `quiz_altered`.
- Front : la ligne `clear` efface l'affichage sans appel serveur (comme Ctrl+L, l'historique reste).

## Décisions

- `pwd` affiche `/repo` (chemin virtuel) : le chemin réel de l'hôte n'est pas montré.
- Un glob entre guillemets est développé aussi : le découpeur ne garde pas l'information de citation (les noms contenant `*` ou `?` sont de toute façon invalides sous Windows).
- `ls` d'un fichier affiche son nom ; `ls -a` n'affiche pas `.git` (inaccessible de toute façon), ni `.` ni `..`.
- `cp`/`mv` écrasent une destination fichier existante (comme un shell sans `-i`).
- `clear` côté serveur est une opération vide (code 0) pour que l'API reste cohérente si la ligne lui parvient.

## Reports

- Variables, tubes, `>` pour d'autres commandes que `echo`, `cat > f` interactif : hors liste blanche, volontairement.
- Rejouer la sortie du terminal après rechargement (déjà reporté en 2.4).
- Les tests de liens symboliques sont ignorés quand le poste ne sait pas en créer (Windows sans droit) : ils s'exécutent sous Linux et macOS en CI. Les lecteurs Windows (`C:`) et noms réservés sont couverts sur les trois OS par la garde de chemin.

## À vérifier dans un vrai navigateur

- Saisie de `echo texte > fichier` puis `cat fichier` dans le volet ; `clear` ; affichage du refus (`role="alert"`) pour `cat ../x`.
