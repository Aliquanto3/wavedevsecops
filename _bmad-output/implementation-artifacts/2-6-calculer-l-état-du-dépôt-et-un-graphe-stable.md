---
story: "2.6"
key: 2-6-calculer-l-état-du-dépôt-et-un-graphe-stable
title: Calculer l'état du dépôt et un graphe stable côté serveur
status: review
branch: story/2-6-etat-graphe
ad: [AD-1, AD-2, AD-3, AD-6, AD-17]
---

# Story 2.6 : Calculer l'état du dépôt et un graphe stable côté serveur

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.6 ».

## Livré

- `contracts` : grammaire `element_id` complète (`ELEMENT_FORMS`) : nombre de segments et contrôle de chaque segment par forme d'AD-2 (SHA de 40 caractères, zone `head|index|worktree`, `old|new`, numéros, `staging|prod`). Segments encodés en pourcentage (`/` et `@` restent lisibles) ; l'analyseur n'accepte que la forme canonique (pas de `%3a` minuscule, pas de `~` encodé, UTF-8 strict) : un élément a un seul nom. Schémas `contracts/repo.py` (`RepoState`, `Commit`, `Ref`, `Head`, `IndexEntry`, `StatusEntry`, `StashEntry`) et `contracts/views.py` (`Views`, `GraphView`, `GraphNode`, `GraphEdge`, `RefLabel`, `StagingView`, `PromptView`), versionnés (`schema_version`), en ajout seulement.
- `projections/` (nouveau composant) :
  - `state.read_repo_state` en contexte interne (`LC_ALL=C`) : `for-each-ref` (tags annotés déréférencés), `rev-list --all --reflog`, `status --porcelain=v2 -z --branch`, `ls-files -s -z`, `ls-files -z`, `stash list`, `log -g` par ref (HEAD, branches, refs distantes). Commits accessibles (refs hors `refs/stash`, et HEAD) puis perdus (cités par un reflog, aucune ref n'y mène) ; refs locales, `origin/*`, tags ; HEAD (attachée, détachée, sans commit, amont, avance/retard) ; index ; statut ; arbre de travail ; stash ; opération en cours (`merge`, `rebase`, `cherry_pick`, `revert`). Rôle de l'auteur (`learner`, `colleague`, `agent`) par l'e-mail des personnages du setup.
  - `graph.place` : placement déterministe (voir Décisions), garanties : une case par nœud, la colonne d'une arête ne croise ni nœud ni autre arête.
  - `views.build_views` : nœuds annotés (`new` par comparaison avec la projection précédente, `lost`, `restored`, `designable`, `a11y_name_text` au gabarit de l'UX, `explain_ref`, `links`), étiquettes de refs (« branche locale feature », « référence distante origin/main », « tag v1.0 », `HEAD`, « HEAD détachée »), arêtes, groupes de `staging-index` (Indexé, Modifié non indexé, Non suivi, avec la lettre git), `terminal-prompt` (branche courante ou « HEAD détachée »), `announce_text` (« Vues mises à jour : 1 commit nouveau, 1 branche nouvelle, HEAD sur feature. »).
  - `spans.Linker` : passages liables d'une sortie (refs dans l'ordre de résolution de git, chemins, `a/…`/`b/…` de diff, `fichier:ligne`, préfixes de SHA d'au moins 7 caractères et sans ambiguïté), seuls les éléments existants sont liés ; positions en unités UTF-16.
- `engine` : `repo_projector` remplace `fingerprint_projector` (empreinte d'AD-6 et vues). `Projection.linker` ; `OpContext.last_views` ; `OpContext.output` remplit `spans` contre le dernier état projeté, et la file publie dans `state_projected.output_spans` les sorties de l'opération dont les passages changent avec le nouvel état (le SHA créé par `git commit`).
- `events` : `Span{start, end, text, element_id}` ; `TerminalOutput.spans: list[Span]` (resserré) ; `StateProjected.output_spans: list[OutputSpans{seq, spans}]` (ajout).
- Tests : `test_element_id` (chaque forme, segments avec `:`, `%`, espaces, Unicode hors plan de base ; formes invalides et non canoniques), `test_graph_layout` (synthétique : même entrée dans tout ordre → même sortie, 150 ajouts successifs sans déplacement, invariants, 800 commits en moins de 2 s), `test_projections` (vrai git : suite commit, branche, merge `--no-ff`, tags léger et annoté, push vers `origin`, HEAD détachée, commit perdu par changement de branche, `reset --hard`, `rebase`, stash, renommage, fichier non suivi accentué ; conformité à `git log --all` et `git status` après chaque état, aucun commit déplacé ; vues annotées ; passages liables ; dépôt vide ; 400 commits par `fast-import` projetés en moins de 10 s, 0,7 s mesurées sous Windows ; publication par la file).

## Forme de `state_projected` (pour 2.3, 2.7 et suivantes)

```text
state_projected {
  fingerprint: str,
  output_spans: [{seq, spans: [Span]}],          # sorties de cette opération, à mettre à jour
  views: {                                       # contracts.Views, schema_version 1
    schema_version, announce_text,
    repo:    RepoState {schema_version, head{detached, ref, commit, upstream, ahead, behind},
                        commits[{sha, parents, tree, author_*, committer_*, committer_ts,
                                 subject, message, actor, lost}],
                        refs[{name, kind, short_name, target, commit, annotated, symref, upstream}],
                        index[{path, mode, oid, stage}],
                        status[{path, kind, index_status, worktree_status, orig_path}],
                        worktree[str], stash[{index, sha, message}], in_progress},
    graph:   {columns, rows, head_text,
              nodes[{element_id, sha, short_sha, subject, actor, column, row, parents[eid],
                     refs[{element_id, kind, name_text, a11y_name_text, explain_ref, current,
                           new, designable, links}],
                     head, detached_head, lost, new, restored, designable,
                     a11y_name_text, explain_ref, links}],      # rang décroissant, puis colonne
              edges[{child, parent, column, kind: first_parent|merge, lost}]},
    staging: {staged[], unstaged[], untracked[]: {element_id, path, letter, orig_path, designable}},
    prompt:  {text, detached, element_id},
  }
}
```

Tracé d'une arête : nœud parent → (`column`, rang du parent + 1) → (`column`, rang de l'enfant − 1) → nœud enfant ; directe si les rangs se suivent. Rang 0 en bas (racines).

## Décisions

- Rang = génération (`1 + max(rang des parents)`) : fixé par les ancêtres, donc par le SHA ; il ne change jamais. Deux commits de branches différentes peuvent partager un rang, dans des colonnes distinctes.
- Colonne : placement glouton dans un ordre topologique où passe d'abord le commit prêt le plus ancien (date du committer, rang, SHA) ; premier parent prolongé si sa colonne est libre, sinon plus petite colonne libre. Les refs n'interviennent pas : c'est plus fort que la règle d'AD-2 (« tant que ses refs et ses parents n'ont pas changé ») ; une branche créée, supprimée, un HEAD détaché ou un tag ne déplacent rien. Contrepartie : `main` n'est pas forcément en colonne 0 (la première branche qui prolonge une ligne la garde).
- `RepoState.commits` suit `git log --all` **sans le stash** : les commits internes d'un stash ne sont pas des nœuds du graphe ; le stash est listé à part. Le test de conformité compare avec `git log --exclude=refs/stash --all`.
- Commits perdus : cités par le reflog de HEAD, d'une branche ou d'une ref distante (pas celui du stash), avec leurs ancêtres inaccessibles.
- Pas de `cat-file` : `for-each-ref` déréférence les tags annotés (`%(*objectname)`) en un seul appel.
- `announce_text` ne répète pas l'avance de la branche courante sur un commit qu'elle vient de créer ; le « Commande terminée, code n » et le verdict de l'étape restent dans leurs événements (`op_exit`, `step_verdict`).
- Rôle de l'auteur : une adresse inconnue est celle de l'apprenant (« par vous »).
- `events` reste une feuille : `views` est transporté en dictionnaire, validé par `projections` (`contracts.Views`).
- Écart léger avec l'AC « chaque ligne de `terminal_output` porte des spans résolus contre le `RepoState` » : la sortie est émise avant la projection (ordre d'AD-1), donc ses `spans` sont résolus contre l'état d'avant, puis complétés par `output_spans` contre l'état d'après.

## Reports

- `content/explanations.yaml` : les clés `graph.commit`, `graph.commit_lost`, `graph.branch`, `graph.remote_ref`, `graph.tag`, `graph.head`, `graph.head_detached` (`projections.EXPLAIN_REFS`) sont à écrire avec le catalogue d'explications.
- Registre des volets côté front : chaque vue déclare ses types d'`element_id` et un test refuse un type non déclaré (AD-2) : 2.3 / 2.7.
- `restored` est porté mais jamais posé : à brancher avec le rétablissement après quiz (`build_views(..., restored=)`).
- `links` d'un nœud = refs qui le visent ; la table complète des correspondances de l'UX (diff, terminal, PR) viendra avec les vues concernées. PR, checks, journal de revue (`github.json`) : Epic 4.
- Refs de `origin.git` lui-même (au-delà des refs distantes du dépôt local) : avec le GitHub simulé.
- Ordre de placement : deux commits créés dans la même seconde sur des lignes différentes peuvent passer l'un avant l'autre selon leur SHA ; sans effet sur les commits plus anciens.
- Le surveillant (`external_change`) calcule désormais la projection complète pour comparer l'empreinte : à alléger (empreinte seule) si le coût se voit.
- `lang` des sorties : fixé par l'appelant de `OpContext.output` (le terminal, 2.4).
