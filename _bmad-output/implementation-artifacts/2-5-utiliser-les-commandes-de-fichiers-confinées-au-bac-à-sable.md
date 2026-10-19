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

## Revue

Revue Opus du 2026-10-18, après rebase sur `origin/main` (6860667, stories 4.1 et 4.3 ; conflit de fin de `wsfs` résolu en gardant les deux ajouts).

- HIGH, second avis n° 1 (élargi) : une jonction Windows (`mklink /J`, sans droit d'administrateur) était vue comme un dossier ; `cp -r d e` (jonction dans `d`) et même `cp -r j k` (la jonction elle-même) recopiaient le contenu de sa cible hors de l'espace, ensuite lisible par `cat`. Prouvé avec `_winapi.CreateJunction`. Corrigé : `kind_of` et `ls` traitent une jonction comme un lien (`rm`/`mv` agissent sur elle, `cp` la refuse par `confine`), `cp -r` refuse un dossier qui contient une jonction (`shutil.copytree` la copie comme un dossier réel même avec `symlinks=True`). Test Windows ajouté (il tourne en local et en CI Windows).
- MEDIUM, second avis n° 2 : écarté. `cp -r` recopie un lien sortant comme lien, comme `cp -R` d'un shell ; aucun contenu hors de l'espace n'est copié et le lien copié reste refusé à la lecture. La phrase « `cp` d'un lien sortant est refusé » vise `cp lien x`. Test POSIX ajouté (`test_cp_r_garde_un_lien_sortant_comme_lien`, CI Linux et macOS).
- MEDIUM, second avis n° 3 (Complexité) : corrigé. `cat` ne lit plus que 256 Kio (`wsfs.READ_LIMIT`) et signale la troncature ; `echo >>` ajoute en fin de fichier au lieu de relire et réécrire tout le fichier (coût linéaire en la taille du fichier à chaque ajout, quadratique sur une série).
- MEDIUM, second avis n° 4 (décision) : comportement gardé. `rm -rf *` vide le dépôt sauf `.git` et les noms à point, comme un shell. AD-4 retient comme modèle de menace l'erreur de l'apprenant, et le bac à sable plus « Recommencer » (AD-6) la réparent ; une garde ajoutée rendrait le terminal moins réaliste. Décision à confirmer par Anaël s'il veut une confirmation ou un refus de `rm -r *` à la racine.
- LOW, second avis n° 5 : corrigé. Écriture refusée pour `CONIN$`, `CONOUT$`, `COM¹²³`, `LPT¹²³` et les caractères `"<>|` et de contrôle (même refus sur les trois OS). `*` et `?` restent admis par la garde (motifs des globs).
- LOW, second avis n° 6 : corrigé. `echo > a/b`, `echo >> a/b` et `touch a/b` refusent un dossier parent absent (« Créez-le avec mkdir »), comme un shell. `wsfs.write_text` garde la création des parents pour le setup.
- LOW, second avis n° 7 : écarté. `cp` et `mv` copient des octets : normaliser fins de ligne ou BOM corromprait un fichier binaire ; la règle UTF-8 sans BOM et LF vise les écritures de texte (`echo`, vue Code).
- LOW, second avis n° 8 : corrigé. `cp -r` ne recopie pas de `.git` imbriqué.
- LOW, second avis n° 9 : corrigé. Une `OSError` de `ls`, du développement d'un glob ou du test de destination de `mv`/`cp` donne « opération impossible » au lieu de remonter.
- Tests, second avis n° 10 : corrigé (jonction sous Windows, lien sortant copié sous POSIX, gros fichier, parent absent, noms non portables, `.git` imbriqué).
- Complexité : 1 constat (n° 3), corrigé ; `expand_glob` et `list_dir` restent linéaires par appel.

### Revue des arbitrages UI (branche chore/arbitrages-ui)

- high, second avis 1 : corrigé. `clears_root` ne voyait pas `rm -rf ?*`, `**`, `*?` (même effet que `*`) : tout motif d'un segment fait de `*`/`?` qui prend tout nom non caché demande confirmation.
- medium, second avis 2 : rejeté. `rm -rf .` efface bien tout hors `.git`, ce que dit le message (« hors historique git »).
- medium, second avis 3 : rejeté. `confirmed` est un garde-fou d'interface pour l'apprenant, pas une frontière de sécurité ; l'app est locale et un POST direct vient de lui.
- low, second avis 4 : corrigé. Clic sur la carte pendant une opération : les boutons restent au lieu de disparaître sans effet.
- low, second avis 5 : rejeté. Le « i » des étiquettes de la liste des commits est cohérent avec celui du graphe.
- low (a11y), second avis 6 : corrigé. Le verdict d'une étiquette de ref revient dans le nom accessible du bouton de son commit (`namedOwner`).
- low, second avis 7 : corrigé. Tests ajoutés (`?*`, `**`, `*?`, `rm -r -f *`, `rm -fr *`, `??*`, `.*`).
- low, revue : rejeté. `rm -rf .*` (cachés seulement, hors `.git`) reste sans confirmation : le message « tout le bac à sable » serait faux.
- vérifié, revue : le `rm` confirmé suit le même chemin qu'avant l'arbitrage ; aucun scénario n'utilise `rm -r` (leçon 6.2 tenue).
- Complexité : 0 constat.
