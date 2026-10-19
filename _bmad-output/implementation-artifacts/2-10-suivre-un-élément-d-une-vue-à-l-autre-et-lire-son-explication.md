---
story: "2.10"
key: 2-10-suivre-un-élément-d-une-vue-à-l-autre-et-lire-son-explication
title: Suivre un élément d'une vue à l'autre et lire son explication
status: review
branch: story/2-10-suivre-element
ad: [AD-1, AD-2, AD-7, AD-13, AD-17]
---

# Story 2.10 : Suivre un élément d'une vue à l'autre et lire son explication

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.10 ». UX : DESIGN.md (`link-state`, `explain-popover`, terminal), EXPERIENCE.md (« Correspondances entre vues », Interaction Primitives, Accessibility Floor). FR-5, NFR-13, UX-DR7, UX-DR24, UX-DR25, UX-DR37.

## Livré

### Serveur (AD-2 : le front ne calcule aucun lien)

- `Views` gagne trois dictionnaires, en ajout seulement (`contracts/views.py`, calculés par `projections/links.py::annotate`, appelé par `project` une fois la vue Distant assemblée) :
  - `links` : `element_id` → ceux qui lui sont liés. Arêtes **déclarées**, lues dans les deux sens par le front. Sources : `GraphNode.links` et `RefLabel.links`, les `links` des vues Distant + PR, plus : PR ↔ commit de sa branche de tête, check ↔ commit testé (le `head_sha40` de son `element_id`), et chaque fichier du dépôt dans ses trois zones (`path:head|index|worktree:<chemin>`, qui se citent entre elles). Une cible peut être absente de l'écran (un `path:head:…` sans diff ouvert) : le front l'ignore.
  - `names` : nom court de chaque élément projeté (« commit a1b2c3d », « ref origin/main », « branche feature », « PR n°2 », « check lint (PR n°2) », « revue n°1 (PR n°2) », « fichier config.py »). Sert au résumé lu au focus, et de registre des éléments projetés.
  - `explain` : `explain_ref` de chaque élément projeté.
- Diff (`contracts/diff.py`, `projections/diff.py`) : `DiffFile` et `DiffLine` portent `links` (le commit du diff, s'il y en a un, et le fichier dans ses trois zones) ; `DiffFile.explain_ref = "code.file"`. Le diff reste projeté à la demande.
- Terminal : `TerminalOutput.explain_ref` (`terminal.output`) sur les blocs `tool-output`, posé par la file (`EXPLAIN_TOOL_OUTPUT`, `contracts/views.py`).
- `content/explanations.yaml` (fichier pivot, voir « Contrat » ci-dessous) servi par `GET /api/explanations` (`web/explanations.py`) ; absent ou invalide : catalogue vide, journalisé, le « i » le dit.
- `EXPLAIN_REFS` (`projections/views.py`) liste toutes les clés citées par les projections ; le test de contenu exige l'égalité avec les clés du YAML (aucune clé sans texte, aucun texte orphelin).

### Front

- `js/linking.js` : `mountLinking(workspace, …)`, appelé une fois par `workspace.js`. Registre de liens par magasin (`linkingFor`) alimenté par `views.links` et par le diff (`code.js` : `linking.setSource("diff", diffSource(diff))`).
  - Élément actif = survol, sinon focus, sinon sélection. Ses correspondants (et les autres nœuds du même `element_id`, par exemple l'étiquette de ref du graphe et la ligne du volet Distant) prennent `is-linked` ; l'espace porte `data-linking` tant qu'il y a quelque chose à mettre en regard.
  - Terminal : les nœuds de sortie portent `data-span-ids` (les `element_id` de leurs `spans`) ; ceux qui citent un correspondant prennent `terminal-lit`, les autres passent en `terminal-fg-soft`.
  - Éléments qui ne sont pas des boutons (lignes et en-têtes du diff, `data-roving`) : clic, Entrée et Espace les sélectionnent (le clic synthétique d'Entrée passe par la désignation armée) ; la sélection se pose sur `diffline:…` et `path:head|worktree:…`.
  - Résumé « n éléments liés : … » dans une région `visually-hidden` (`#link-summary`), relié par `aria-describedby` à l'élément qui a le **focus** (pas au survol), retiré à la sortie.
  - Vue masquée : la puce devient « + Nom · lié » (classe `is-linked`, `data-linked`) quand la vue contient un correspondant (d'après sa `projection` déclarée, sinon ses `elementTypes`). Clic sur la puce : la vue revient (`workspace.js`) et `reveal` met son premier correspondant en évidence (`is-revealed`, 2,4 s) et y défile. L'ancre est gardée pendant que le pointeur ou le focus atteint les puces.
  - Hors de la zone visible : sur clic seulement, chaque autre vue défile (`scrollIntoView({block: "nearest"})`, sans animation avec `prefers-reduced-motion`) jusqu'à son premier correspondant. Jamais au survol.
- `js/explain.js` : le « i » (`button.explain-trigger`, 24 px, `tabindex="-1"` : atteignable aux flèches de la vue, pas à Tab) est posé à côté de chaque bouton-élément qui a une clé d'explication, d'en-tête de fichier de diff et de bloc `tool-output`. Clic, Entrée ou Espace ouvre un `explain-popover` (`role="dialog"`, titre + deux ou trois phrases, focus dans le popover) ; Échap le ferme **sans** que l'Échap de la disposition ne s'applique, et rend le focus au « i » ; Tab hors du popover le ferme aussi. Jamais au survol. « Voir les éléments liés » déplie la liste des éléments liés ; en choisir un le sélectionne. Sans catalogue, le popover dit « Explication indisponible ».
- `selection.js::selectionIsStale` : une sélection de type énuméré par la projection (`commit`, `ref`, `tag`, `pr`, `check`, `review`) est périmée si son `element_id` a quitté `views.names`. `repo.js` s'en sert à la place de « absent de mon DOM » : **règle le report de la story 3.3** (une sélection `pr:` ou `check:` n'est plus vidée au redessin du volet Dépôt local). Les sélections `diffline:`, `path:` et `output:` ne sont jamais effacées par un autre volet ; la vue Code efface une ligne de diff qui n'est plus dans le diff relu (sans changer la cible du diff).
- `code.js` : la cible du diff est mémorisée. Un commit sélectionné la fixe, l'effacement de la sélection ramène à l'arbre de travail, toute autre sélection (ligne, ref, PR) la laisse : cliquer une ligne d'un diff de commit ne bascule plus sur l'arbre de travail.
- `css/linking.css` : état lié (anneau et fond `discipline-harness`), retrait des autres (décors du graphe passés à `line`/`surface` par la couleur, car le dépôt interdit toute `opacity` en CSS ; étiquettes de refs et lignes de diff sans fond ; **texte en `ink-soft`**), `terminal-lit`, sélection d'une ligne de diff (contour encre 3 px et marque ●), puce liée, `is-revealed`, « i » et `explain-popover`.
- **Désignation (5.3)** : toutes les marques de lien sont sous `:not(.is-designating)` (test CSS). Armé, un clic sur un désignable désigne sans sélectionner (capture de `installDesignation`, qui passe avant) ; le survol marque les liens dans le DOM mais rien ne se voit.
- Ajouts localisés dans des fichiers partagés : `workspace.js` (import, `mountLinking`, puces, `destroy`), `repo.js` (1 import, 1 condition), `code.js` (cible mémorisée, source de diff, élagage), `terminal.js` (`markSpans`, `data-explain-ref`), `store.js` (`explain` de l'entrée de sortie).

## Contrat de `content/explanations.yaml` (pour la story 9.4)

```yaml
schema_version: 1
entries:
  <explain_ref>:          # clé citée par une projection (EXPLAIN_REFS)
    title_text: "…"       # titre du popover
    body_text: "…"        # deux ou trois phrases, vouvoiement, `code` entre accents graves
    barrier_id: ""        # facultatif : id d'une barrière de content/chain.yaml
```

- `GET /api/explanations` rend `{schema_version, entries}` tels quels ; les textes viennent tous d'ici (convention Textes affichés).
- `barrier_id` est le point d'accroche de **9.4** : relier un terme (ou un élément) à sa barrière, c'est renseigner ce champ ; le test de contenu vérifie qu'un `barrier_id` non vide existe dans `chain.yaml`. Rien ne lit encore ce champ côté front.
- Clés actuelles : `graph.commit`, `graph.commit_lost`, `graph.branch`, `graph.remote_ref`, `graph.tag`, `graph.head`, `graph.head_detached`, `index.path`, `remote.pr`, `remote.check`, `remote.review`, `code.file`, `terminal.output`. Une nouvelle clé s'ajoute à la fois à `EXPLAIN_REFS` et au YAML (le test d'égalité le rappelle). Les étapes d'un scénario peuvent déjà citer ces clés dans `explain_ref` (lint du chargeur).

## Décisions

- Les `links` sont dérivés **côté serveur** et déclarés, plutôt que reconstruits par le front depuis les `links` éparpillés des items : une seule table, testable, et la fermeture symétrique est la seule chose que le front fait (une lecture dans les deux sens, aucun lien inféré).
- Une seule table de noms (`names`) sert à la fois au résumé lu au focus et à repérer les éléments qui existent encore (sélection périmée). Pour les éléments du diff, absents de `names`, le résumé retombe sur leur `aria-label`.
- Le « i » est posé après coup à côté du bouton (un bouton ne contient pas un bouton), par `explain.js`, plutôt que de modifier les générateurs de `repo.js`, `remote.js` et `code.js` en cours de modification par 5.5, 2.9 et 7.4. Il est dans l'ordre de lecture et de flèches de la vue, hors de Tab (une vue = un arrêt de tabulation, EXPERIENCE.md).
- Le survol d'une étiquette de ref (`data-ref`) allume les liens de la ref, pas ceux du commit : le plus proche d'abord.

## Reports

- **Fichier dans l'arbre et l'éditeur** (table de l'UX, ligne « Fichier » × Code) : la liste des fichiers et l'éditeur de la vue Code n'ont pas d'`element_id` ; seuls les en-têtes et lignes du diff se lient. À faire avec l'arbre de dossiers de la vue Code (report de 2.8).
- Lignes de diff ↔ « même ligne dans le diff de la PR », ligne de l'éditeur, diff d'une PR : le diff d'une PR n'existe pas encore (report de 2.8/3.3).
- Lignes signalées par un check (`pipeline-tabs`), sorties d'outil ↔ check correspondant, SBOM, carte et barrières : stories 7.4, 9.x. La table `links` s'enrichit par ajout (`annotate`).
- « Voir les éléments liés » n'est atteint que par le popover : un élément sans « i » (ligne de diff) n'a que le résumé `aria-describedby`.
- Les sorties du terminal ne résolvent leurs `spans` que pour les blocs `tool-output` (liens cliquables) ; les lignes ordinaires s'allument sans être des liens. `state_projected.output_spans` (relinkage après coup) n'est pas encore appliqué par le magasin : une ligne ne s'allume qu'avec ses `spans` d'origine.
- À vérifier dans un navigateur par Anaël : placement des « i » (graphe, index, liste des commits, volet Distant, bloc de sortie : position absolue à droite de la ligne, recouvrement du texte long), lisibilité de l'anneau lié et du retrait des autres en clair et en sombre, `terminal-lit` sur les lignes du terminal, défilement jusqu'au correspondant sur clic (dont `prefers-reduced-motion`), puce « + Nom · lié » et mise en évidence, position et débordement du popover près des bords, Échap qui ferme le popover avant la vue agrandie, lecture du résumé `aria-describedby` et du popover au lecteur d'écran, interaction avec le mode Désigner (liens invisibles, clic qui désigne).

## Tests

- `tests/test_links.py` : arêtes déclarées (PR, branche, commit, checks, revues, fichiers dans leurs trois zones), noms et clés d'explication de chaque élément projeté, `element_id` valides et sans doublon, `links` du diff d'un commit et de l'arbre de travail, catalogue d'explications (égalité avec `EXPLAIN_REFS`, 2 à 3 phrases, vouvoiement, pas de lien externe, `barrier_id` connu), catalogue absent ou invalide, `GET /api/explanations`.
- `tests/test_linking_dom.py` (Node, vraies projections) : survol et mêmes `element_id` entre graphe et Distant, sélection unique persistante et effacée, sélections `pr:`, `check:`, `output:` qui survivent au redessin, sélection périmée, diff lié au commit et cible conservée, Entrée sur une ligne, ligne disparue, `terminal-lit`, `aria-describedby`, « i » (jamais au survol, focus, Échap, liste des éléments liés, sortie d'outil sans sélection du bloc, catalogue vide), puces « · lié » et mise en évidence, défilement sur clic seulement, CSS (marques sous `:not(.is-designating)`, aucune `opacity`).
- `tests/test_designation_dom.py` : le mode armé n'est pas gêné (liens posés, clic qui désigne sans sélectionner). `tests/test_terminal_tools.py` : `explain_ref` du bloc d'outil.
