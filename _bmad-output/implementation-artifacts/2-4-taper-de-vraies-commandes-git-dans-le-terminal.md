---
story: "2.4"
key: 2-4-taper-de-vraies-commandes-git-dans-le-terminal
title: Taper de vraies commandes git dans le terminal
status: review
branch: story/2-4-terminal-git
ad: [AD-1, AD-2, AD-3, AD-4, AD-12, AD-17]
---

# Story 2.4 : Taper de vraies commandes git dans le terminal

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.4 » ; spine AD-3, AD-4, AD-12, AD-17 ; UX-DR13, UX-DR37.

## Livré

- `procs` (AD-12) : `spawn(argv, env, cwd, timeout) -> Handle` non bloquant. `Handle.chunks()` donne les morceaux de stdout et stderr dans l'ordre d'arrivée (deux fils lecteurs, décodage UTF-8 incrémental), plus un battement `None` régulier. Le délai et `terminate()` (appelable depuis un autre fil) arrêtent l'arbre ; après l'arrêt, un descendant qui tient encore les tubes ne retient pas l'appelant au-delà de `KILL_GRACE_S`. **Job Object Windows** (ctypes, `KILL_ON_JOB_CLOSE`) : `terminate_tree(process, job)` termine tout le job, même un descendant dont le parent est sorti. `run` est inchangé.
- `gitio` : `learner_language` (sonde une fois par exécutable), `spawn_learner` (contexte apprenant, sortie au fil de l'eau), `clear_stale_index_lock` (supprime `.git/index.lock` après un arrêt d'arbre, avec reprises sous Windows).
- `content/terminal-allowlist.yaml` : **fichier unique** lu par la garde et par le texte des refus. Il porte les 29 sous-commandes d'AD-4, leurs options (`options`, `value_options`, `choices`, `refused_arguments`, `read` booléen ou conditionnel), la liste des options interdites, tous les textes du terminal (refus, « Code de sortie », « git attend un message de commit… », délai, interruption) et une section `files` vide, où la 2.5 ajoutera les commandes de fichiers sans toucher à la garde.
- `terminal` (nouveau composant) : `allowlist.py` (modèle pydantic du fichier), `parse.py` (découpeur POSIX, refus de `|`, `&&`, `||`, `;`, `&`, `$(…)`, `$VAR`, backquotes, `<`, saut de ligne et de toute redirection, `cd` expliqué, options avant la sous-commande, options interdites ou absentes de la liste, arguments `remote show`/`stash` bornés, `config` limité à `user.name` et `user.email`), `__init__.py` (intention `terminal_line`, exécution, `AFTER_COMMAND_HOOKS`).
- Exécution : git tourne dans `repo/` en contexte apprenant (locale française sondée, sinon anglais), sans shell, stdin fermé, éditeur `:`. stdout et stderr sont émis en `terminal_output` (`lang` = `fr` ou `en`), jamais analysés. Un code non nul ajoute une sortie `exit` (« Code de sortie : n »). `commit` ou `tag -a` sans message qui échoue ajoute le `terminal-app-message` « git attend un message de commit. Ajoutez `-m "…"`. » après la sortie intacte (décidé sur l'argv et le code de sortie seulement). `push`, `pull`, `fetch` : le premier argument doit être un remote existant (`git remote`), sinon refus (chemin, URL, nom inconnu). `git push|pull|fetch` appellent ensuite les crochets `AFTER_COMMAND_HOOKS(ctx, commande, code)` : la 3.1 y branchera `github_sim.refresh` sans que `terminal` l'importe.
- File d'opérations (AD-1) : `OpContext.on_interrupt/interrupt/git_path`, `WorkspaceEngine.interrupt()` (hors file) et `request_stop` qui interrompt l'opération en cours : la **mise en veille arrête l'arbre** de la commande (report de la 2.2). `writes` = faux pour les lectures, donc en `quiz_altered` seules les commandes de lecture passent (409 de la file sinon) ; une ligne refusée par la garde s'affiche toujours.
- Web : `terminal_line {line}` enregistrée au démarrage de l'application ; `POST /api/ws/<id>/interrupt` traité hors file (202 `{interrupted}`). `Settings.terminal_timeout_s` (30 s). Flux `exit` ajouté au catalogue des `stream`.
- Front : `store.js` garde les sorties du terminal (`terminal.entries`, `terminalAppend`, `terminalClear`) ; `terminal.js` monte le volet (région `role="log"`, préfixe masqué « erreur standard : », `lang="en"`, `terminal-stderr` jamais rouge, `terminal-exit-error`, `terminal-app-message` « › », `terminal-refused` en `role="alert"`, « En cours… n s » hors région live après 1 s, saisie en lecture seule et focalisée pendant une commande) ; Entrée, ↑/↓ (historique de la session), Ctrl+C (arrête la commande, ou abandonne la ligne), Ctrl+L (efface l'affichage, pas l'historique), Tab sort, Échap rend le focus au titre (déjà dans `workspace.js`), au-delà de 5 000 lignes les plus anciennes sont masquées avec leur nombre. `terminal.css` (nouveau).
- CI : étape Linux qui génère `fr_FR.UTF-8` pour que le test de git en français s'exécute.

## Décisions

- Les options de `forbidden_options` ne sont pas admises *sauf* si la liste de la sous-commande les nomme (`switch -c` crée une branche, `log -p`, `cat-file -p`, `ls-files -c`) : un test garde la liste de ces exceptions. Avant la sous-commande, aucune option n'est admise. Seule la forme exacte d'une option longue passe (git accepte les abréviations : `--out` ne glisse pas vers `--output`).
- Les commandes `ls`, `cat`, `echo`… ne sont pas implémentées ici (2.5) : elles sont refusées comme « pas une commande de ce terminal », avec la liste tirée du fichier.
- `--no-verify` est admis pour `commit`, `merge` : les hooks sont un sujet d'apprentissage.
- Aucune identité git n'est posée pour l'apprenant : sans `git config user.name`/`user.email`, `git commit` échoue avec le message de git lui-même (le terminal accepte l'écriture de ces deux clés). À revoir si un scénario doit fournir l'identité.
- Les sorties ne sont pas rejouées après un rechargement de la page (le flux SSE reprend à `seq`, sans l'historique du terminal) : l'historique du terminal vit dans la page.
- Les lectures (`quiz_altered`) sont classées par la garde à partir de l'argv (`status`, `log`, `diff`, `show`, `branch` sans argument, `tag -l`, `stash list|show`, `config` en lecture…).
- `Handle` marque une commande comme interrompue tant que `chunks()` n'est pas terminé, même si le chef est déjà sorti (un descendant tient les tubes).

## Reports

- Commandes de fichiers (`ls`, `cat`, `echo`, `touch`, `mkdir`, `rm`, `mv`, `cp`, `pwd`, `clear`) : 2.5, dans la section `files` du fichier.
- Outils de station (`ruff`, `pytest`, `pre-commit run`, `gitleaks`…) acceptés si l'étape les déclare : stories d'outils (7.x) ; `pre-commit install` refusé avec explication : même story.
- `spans` liables de la sortie (2.6/2.7) : le front affiche le texte brut.
- `github_sim.refresh` après `push/pull/fetch` : crochet `terminal.AFTER_COMMAND_HOOKS` (3.1).
- Rétablissement du terminal en lecture seule pendant un quiz (`aria-readonly`, bandeau) : story du quiz.
- Autres verrous que `index.lock` (`HEAD.lock`, `refs/**/*.lock`) laissés par une commande arrêtée : non traités.

## À vérifier dans un vrai navigateur

La doublure de DOM n'a ni mise en page, ni vrai clavier, ni sélection. Restent à constater à la main :

- apparence du volet (fond encre, `stderr` en italique et jamais rouge, bloc de refus, « En cours… n s » hors de la zone annoncée), défilement dans les deux sens, thème clair et sombre ;
- Ctrl+C pendant une vraie commande lente (un hook `pre-commit` qui dort), Ctrl+C avec du texte sélectionné (copie), Ctrl+L, ↑/↓, Tab (sort du terminal), Échap (focus au titre) ;
- lecteur d'écran : annonces de la région `role="log"`, du refus (`role="alert"`) et absence d'annonce du chronomètre ;
- git en français sur un poste qui a la locale `fr_FR.UTF-8`.

## Revue

Rebasée sur `main` (8dd9069 : 2.6, 7.1, 9.1) sans conflit ; le prompt lit `views.prompt.text` de la 2.6 (`main $`, « HEAD détachée $ »). La 3.1 n'est pas encore sur `main` : le crochet `AFTER_COMMAND_HOOKS` reste à brancher sur `github_sim.refresh` à sa fusion.

| # | Sévérité | Source | Constat | Suite |
|---|---|---|---|---|
| 1 | high | second avis (prouvé) | Aucune identité git en contexte apprenant : `commit`, `revert`, `merge/rebase --continue` échouaient (« Author identity unknown ») ; les tests le masquaient par `git config user.*`. | Corrigé : `gitio.learner_gitconfig` écrit `<data>/learner.gitconfig` (identité de l'apprenant du setup, Camille Durand), désigné par `GIT_CONFIG_GLOBAL` en contexte apprenant seulement ; un `git config user.name` tapé (portée du dépôt) prime. Contournement retiré des tests, test de commit sans `identify()`. |
| 2 | medium | second avis (prouvé) | `git remote show <URL\|chemin>` passait en lecture : contact réseau réel ou lecture hors espace, même en `quiz_altered`. | Corrigé : `remote_names_from: 1` dans la liste blanche ; tous les noms de `remote show/get-url` doivent être des remotes existants (refus expliqué sinon). Tests garde et intégration. |
| 3 | medium | second avis | Chemin français exécuté seulement sous Linux. | Limite notée : Git for Windows (et macOS) ne fournit pas les catalogues de git (`share/locale` absent, constaté sur le poste). Le test échoue désormais en CI Linux si la locale manque, au lieu d'être ignoré. |
| 4 | low | second avis | `reflog write` classé lecture. | Corrigé : `write` ajouté aux arguments refusés (`exists` est une vraie lecture). |
| 5 | low | second avis | `commit --no-edit` sans `-m` : pas d'explication si git échoue. | Corrigé : seuls `--amend` et `--allow-empty-message` dispensent du message (explication affichée seulement en cas d'échec : un merge en cours réussit). |
| 6 | low | second avis | Job Object assigné après `Popen` (course). | Rejeté : `Popen` ne rend pas le fil principal pour `ResumeThread` ; la fenêtre précède tout lancement de hook par git, et `taskkill /T` reste le repli. |
| 7 | low | second avis | `index.lock` supprimé sans vérifier qu'aucun processus de l'arbre ne vit. | Corrigé : `Handle.tree_stopped` (Job Object : processus actifs ; Unix : `killpg(…, 0)`), attendu au plus `KILL_GRACE_S` ; sinon le verrou est conservé et journalisé. |
| 8 | low | second avis | Exceptions `-c`/`-p` de la liste blanche. | Rejeté : documentées en tête du fichier et couvertes par les tests de la garde (`-p` admis pour `log/diff/show`, `-c` pour `switch`, interdits ailleurs). |
