---
story: "2.8"
key: 2-8-éditer-un-fichier-dans-la-vue-code-et-lire-un-diff
title: Éditer un fichier dans la vue Code et lire un diff
status: review
branch: story/2-8-vue-code-diff
ad: [AD-1, AD-2, AD-4, AD-13, AD-17]
---

# Story 2.8 : Éditer un fichier dans la vue Code et lire un diff

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.8 ». UX : DESIGN.md (`diff-view`, `diff-file-header`), EXPERIENCE.md (Code). FR-3, FR-4, UX-DR17, UX-DR18.

## Livré

- Intentions (`engine/code_intents.py`, enregistrées par `create_app`) :
  - `save_file{path, content, base_hash}` : `base_hash` est le SHA-256 des octets du fichier sur le disque (vide : le fichier n'existe pas). Écriture par `wsfs.write_text` (confiné, UTF-8, LF, atomique), dans la file. L'écart d'empreinte est refusé en 409 dès la réception (`reason_text` : « …a changé sur le disque… ») et revérifié dans la file, où le disque a pu bouger (sortie `refused`, code 2, rien d'écrit). Refusés aussi : chemin hors du dépôt ou dans `.git/`, dossier à la place du fichier, dossier parent absent. `git status` voit le changement (test).
  - `open_external{path}` : chemin résolu par `wsfs.confine`, fichier existant exigé ; ouverture par `toolrun.open_in_default_editor` → `procs.open_path` (`os.startfile` / `open` / `xdg-open`, sans shell). Seul `procs` crée le processus (AD-1). `code_intents.OPENER` est remplaçable par les tests.
- Lectures sans essai (`web/code.py`) : `GET …/code/tree` (fichiers, hors `.git/`, `.venv`, `node_modules`, caches ; 2000 au plus), `GET …/code/file?path=` (contenu en LF, `hash`, `editable` ; binaire ou > 512 Kio : non éditable avec une phrase), `GET …/code/diff?target=worktree|<sha>`.
- Diff projeté (`projections/diff.py`, schéma `contracts/diff.py`) : `git diff` en contexte interne (`GIT_OPTIONAL_LOCKS=0`), découpé en fichiers, blocs et lignes. En-tête de fichier `path:<worktree|head>:<chemin>` ; ligne `diffline:<worktree|sha40>:<chemin>:<old|new>:<n>` (côté `old` pour une suppression) ; noms accessibles (« Ligne ajoutée 4 : … ») ; phrases « modifié · +2 −1 », « nouveau fichier · +1 −0 », « renommé depuis … », « fichier binaire » ; marqueurs de conflit signalés (`conflict`). Coupé à 3000 lignes, et le dit. Cible : arbre de travail depuis HEAD (ou arbre vide sans commit), ou un commit contre son premier parent (SHA 7 à 40 caractères hexadécimaux, résolu par `rev-list`, jamais passé tel quel comme option).
- Front : `js/editor.js` (composant d'édition), `js/code.js` (volet « Code »), `css/code.css`.
  - Liste des fichiers, ouverture, un tampon par fichier ; point plein « ● » et texte « non enregistré » (masqué visuellement dans la liste, visible dans le titre) tant que le tampon diffère du disque. Ctrl+S / Cmd+S ou « Enregistrer ».
  - 409 : le front relit le fichier ; si l'empreinte du disque a changé, barre `role="alert"` « Garder ma version » (ré-enregistre sur l'empreinte du disque) ou « Recharger » (prend le contenu du disque). Sinon, la phrase du serveur s'affiche.
  - « Ouvrir dans mon éditeur » : `open_external`.
  - Diff : onglet « Diff » ou sélection d'un commit (graphe, liste) ; « Arbre de travail » efface la sélection. En-têtes et lignes : `data-element-id`, `tabindex`, `data-roving` (focus itinérant du volet), 24 px (`--diff-line-height`), « + » sur `accent-soft`, « − » sur `danger-soft`, le marqueur ne porte pas seul l'information (nom accessible).
  - Marqueurs de conflit : texte éditable ; la gouttière les marque « ⚠ n » et un trait, avec la phrase « Marqueurs de conflit aux lignes … ».
  - Le volet recharge la liste, un fichier propre et le diff affiché à chaque nouvelle projection (commande du terminal, changement externe).
- Choix du composant d'édition (AD-13), consigné dans le spine, section Deferred : `<textarea>` natif avec gouttière. Aucune bibliothèque à vendoriser ni à tenir à jour hors ligne ; clavier, lecteur d'écran et zoom du système conservés ; pas de build.
- `views.js` : le volet Code déclare `diffline` parmi ses types et rend `renderCode` (une ligne). `tests/test_repo_dom.py` : la doublure de `fetch` ne compte plus les lectures `/code/`, qu'un clic sur un commit déclenche désormais.
- Tests : `tests/test_code_view.py` (vrai git et vraie file : enregistrement LF, `git status`, création, empreinte périmée avant et dans la file, chemins refusés, `open_external` avec ouvreur factice, diff de l'arbre et d'un commit, grammaire et unicité des `element_id`, renommage, binaire, conflit, coupure, lectures HTTP) et `tests/test_code_dom.py` (Node : liste, point plein, Ctrl+S, conflit, ouverture externe, gouttière, diff, feuille).

## Décisions

- Les lectures de la vue Code sont des `GET` hors file, comme `resolve_sha` (AD-17) : elles ne changent rien. Le diff n'est pas dans `state_projected.views` (il dépend d'une cible choisie par l'apprenant et pèserait sur chaque événement) ; il est projeté à la demande, avec le même schéma d'`element_id`.
- `base_hash` porte sur les octets du disque (CRLF compris), pas sur le texte normalisé : un fichier modifié par un éditeur externe en CRLF est bien vu comme changé.
- Après le 202 de `save_file`, le front attend que le disque porte le contenu envoyé (relecture, 20 essais) avant d'effacer le point plein : la file écrit après la réponse.
- Les fichiers non suivis ne figurent pas dans le diff de l'arbre de travail (git ne les compare à rien) ; l'index de « Dépôt local » les montre.

## Reports

- Coloration syntaxique et recherche dans l'éditeur (hors besoin pédagogique v0.1).
- Liaison entre vues sur les `element_id` du diff, désignation (Epic 5) et explication attachée : les lignes portent déjà leurs identifiants, focalisables, mais n'y réagissent pas.
- Diff d'une PR (le volet accepte le type `pr`, la lecture ne connaît que l'arbre de travail et les commits).
- Arbre de dossiers repliables : la liste est à plat (chemins complets).
- À vérifier dans un navigateur par Anaël : alignement ligne à ligne de la gouttière et du `textarea` (défilement, police), hauteur réelle de 24 px, focus visible, thème sombre, lecture au lecteur d'écran du point plein et des lignes de diff, ouverture réelle par l'éditeur du système.

## Revue

(à remplir par l'orchestrateur)
