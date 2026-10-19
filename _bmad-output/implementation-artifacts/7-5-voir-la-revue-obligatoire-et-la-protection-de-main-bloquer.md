---
story: "7.5"
key: 7-5-voir-la-revue-obligatoire-et-la-protection-de-main-bloquer
title: Voir la revue obligatoire et la protection de main bloquer
status: review
branch: story/7-5-revue-protection
ad: [AD-7, AD-8, AD-14, AD-17]
---

# Story 7.5 : Voir la revue obligatoire et la protection de `main` bloquer (Station 2 · PR et CI)

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 7.5 » ; spine AD-7, AD-8, AD-14 ; FR-22, FR-33, UX-DR19. S'appuie sur la PR et le merge (3.1 à 3.3), le collègue simulé (3.4), le hook `pre-receive` (3.5), le pipeline simulé et son activation par scénario (7.4, report « scénarios de station 2 qui déclarent `pipeline: true` »), les scénarios de la 6.2 et leurs leçons de revue (vouvoiement, libellés réels « Distant + PR » et « Merger », pas de réponse dans le premier palier d'indice, pas d'étape validable par un autre chemin que celui enseigné).

## Livré

- Trois scénarios A de la station 2 (`section: stations`, `station: 2`, deux parcours, même code d'exercice `exercise_stage: auto`), chacun avec le hook de l'origine (`install_hooks`) posé avant la protection de `main`, cinq étapes et trois paliers d'indice par étape :
  - **`check-en-echec`** (« Voir un check en échec bloquer la PR », `pipeline: true`) : `main` exige `ruff`, `pytest` et `gitleaks`. La branche `seuil-rupture` porte un test qui attend `[]` là où `below_threshold()` rend `["vis"]`. Pousser, ouvrir la PR, lire le blocage (le check `pytest` en échec sur les SHA courants et « Merger » inactif avec sa raison), corriger puis pousser (étape validée seulement quand `pytest` est `success` sur le nouveau commit et que la PR est mergeable), merger.
  - **`pr-sans-revue`** (« Voir la revue obligatoire bloquer la PR », `pipeline: true`) : `main` exige les trois checks et une approbation. Étape « constater » : les trois checks sont verts, aucune approbation, la PR n'est pas mergeable ; puis « Demander une revue » (ci-dessous), merger.
  - **`push-direct-main`** (« Voir la protection de main refuser un push direct », sans pipeline) : commit sur `main`, `git push origin main` refusé, puis branche `ajout-changelog`, PR, merge.
- **Refus du push direct** : la sortie réelle de git (le texte du hook `pre-receive`) est déjà suivie de « Refusé par la protection de `main` : tout passe par une PR. » (3.5, `terminal.allowlist`). Ajouts : la preuve `evidence_seen{protection}` est soumise quand ce refus s'affiche (`terminal._explain_protection`), et le terminal dépose `ctx.data["push_refused"] = <branche>`.
- **Nouveau type d'étape `push_refused`** (`scenarios/steps/push_refused.py`, champ `branch`) : le refus ne laisse aucune trace dans le dépôt (`main` locale reste en avance) ; seule l'opération qui explique le refus de cette branche valide l'étape. Un push accepté (`main:ailleurs`), `fetch` ou `status` ne la valident pas.
- **`pr_state` complété** (ajout de champs, sans changer les scénarios existants) : `check_states` (`job_id` vers état, **sur les SHA courants** de la PR : un résultat périmé ne compte pas), `mergeable` (vrai ou faux) et `max_approvals` (0 : la revue manque encore). Les étapes sont jugées après chaque `check_update` de la file (les opérations du pipeline valident déjà).
- **Revue demandée par l'apprenant** : la revue du collègue ne peut pas se lire « checks verts, revue absente » si elle arrive dans la même écriture que le dernier check vert (déclencheur `checks_green`, 3.4). Nouveau déclencheur de réaction `review_requested` (`ReactionTrigger`, `colleague_reaction`) : joue quand l'apprenant demande la revue, si les checks obligatoires sont verts, une fois par `head_sha` (un nouveau commit la réarme). `github_sim.request_review` refuse (409 dit à l'écran) une PR fermée, sans réaction en attente ou aux checks pas verts ; `pending_request` et `checks_green` sont publics. Intention **`pr_request_review{number}`** (`engine/pr_intents.py`) : appelle `request_review`, annonce la PR, soumet la preuve `evidence_seen{review}` (le journal de revue montre alors la réponse).
- **Vue « Distant + PR »** : `ReviewLog` gagne `can_request`, `request_enabled`, `request_disabled_text` (ajouts, AD-17) ; `remote.js` affiche le bouton « Demander une revue » dans l'en-tête du journal de revue (inactif avec sa raison tant que les checks ne sont pas verts, `bindAction`), qui poste `pr_request_review`.
- **Chaîne** (`content/chain.yaml`, station 2) : deux barrières, `review` (« Revue obligatoire ») et `protection` (« Protection de main »), avec leurs liens. Le check en échec prouve la barrière `tests` (« Voir la sortie » de 7.4, inchangé).
- `content/fingerprints.json` : six empreintes de plus (`scripts/update_fingerprints.py`, stables sur deux exécutions ; les autres empreintes n'ont pas changé).
- Tests : `tests/test_stations_pr.py` (lint de contenu, exigences, jeu de bout en bout des trois scénarios dans les deux parcours avec les outils du pipeline remplacés par des Python qui lisent l'arbre testé, refus de merger tant que `pytest` échoue, preuve unique de `tests`, push qui ne corrige pas, demande de revue refusée avant les checks verts ou sans PR, réarmement après un nouveau commit, preuves `review` et `protection`, absence de validation par un autre chemin, barrières de la chaîne, `push_refused` et `check_states` en unité) ; `tests/test_remote_review_dom.py` (bouton inactif puis actif sous Node).

## Décisions

- **Revue demandée plutôt qu'automatique** : sans le déclencheur `review_requested`, le critère « checks verts mais revue manquante, jusqu'à l'approbation du collègue » n'est jamais observable (l'approbation de `checks_green` partage l'écriture du dernier check vert). La demande est aussi le geste réel de GitHub. Le collègue ne répond qu'aux checks verts, comme un relecteur qui attend la CI.
- **Validation par l'état réel** : « lire le blocage » passe par l'échec de `pytest` sur les SHA courants et par `mergeable: false`, « corriger » par le `success` du nouveau commit, jamais par un geste de l'interface qu'un autre chemin pourrait imiter. Si l'apprenant corrige le test avant de pousser, `pytest` ne passe jamais en échec : l'étape « lire le blocage » reste ouverte (l'instruction demande de pousser sans corriger ; l'indice le rappelle). L'étape n'exige pas d'avoir ouvert « Voir la sortie » (la preuve `tests` est soumise séparément).
- **`protection` et `review` comme barrières** : `evidence_seen{barrier_id}` exige un identifiant de `chain.yaml` (9.3) ; deux barrières sont ajoutées plutôt que de réutiliser `tests`.
- **Pas de merge dans le scénario de push direct sans approbation ni check** : la protection de `main` y est réduite au refus du push direct (`required_approvals: 0`), ce qui laisse la PR mergeable (l'étape finale montre le chemin autorisé).

## Reports

- Relecture pédagogique du français (ton, justesse) à faire par Anaël ; identifiants de scénario (`check-en-echec`, `pr-sans-revue`, `push-direct-main`) et titres à valider (catalogue : 9.3).
- Intentions ajoutées au catalogue d'AD-17 : `pr_request_review` (« Demander une revue ») après `check_output_seen` (7.4) : décision à valider par Anaël (alternative : revue automatique, sans geste ni critère observable).
- Les scénarios de station 2 plus riches (couverture, `diff-cover`) et la station 3 : 8.x.
- La sortie de `gitleaks` et le job réel dépendent de l'outil provisionné (7.1) : sans lui le job est en « Erreur de l'outil » et bloque aussi `check-en-echec` et `pr-sans-revue` (reprendre avec « Relancer le check » après installation).

## À vérifier sur poste réel

1. Windows, macOS, Linux : le scénario `check-en-echec` joué avec les vrais ruff, pytest et gitleaks (pytest échoue sur le test du scénario, passe après correction) ; la durée du run reste sous le budget (7.4).
2. `pr-sans-revue` : le bouton « Demander une revue » devient actif quand le dernier check passe au vert, et la réponse du collègue (commentaire puis approbation) apparaît dans le journal.
3. `push-direct-main` : la sortie réelle du hook s'affiche sur les trois OS (le chemin `core.hooksPath` relatif de `origin.git`), suivie de la phrase de l'application.

## Revue

Revue Opus du 2026-10-19, après rebase sur `main` (seul conflit : `content/fingerprints.json`, version de `main` reprise puis régénérée : six ajouts, aucune autre empreinte modifiée, stable sur deux exécutions).

- **High** · second avis 1 · corrigé : les trois scénarios de station 2 manquaient dans `STATION_ORDER` (rang des scénarios hors ordre, avant les stations : « Scénario suivant » et ordre du rapport faussés ; la garde `test_scenarios_de_station_livres_figurent_dans_l_ordre_conseille` et `test_section_stations_rangee_par_station`, qui supposait un seul groupe, cassaient). Ids ajoutés dans `scenarios/order.py`, test adapté à deux stations.
- **Medium** · second avis 2 · corrigé : conflits du rebase et empreintes (ci-dessus).
- **Medium** · second avis 3 · rejeté, décision consignée : `lire_le_blocage` et `constater_la_revue_manquante` se valident sur l'état (check en échec sur les SHA courants, `mergeable: false`, zéro approbation). Aucun autre chemin que celui enseigné n'atteint cet état (il faut pousser la branche non corrigée et ouvrir la PR) ; la leçon 6.2 vise les raccourcis, pas les étapes d'observation. Exiger « Voir la sortie » ferait dépendre l'étape d'un geste d'interface (`check_output_seen` ne valide pas, `validate=False`) et bloquerait l'apprenant qui lit la raison sous « Merger » sans ouvrir la sortie. La preuve `tests` reste soumise par « Voir la sortie ». À trancher par Anaël s'il veut une preuve de lecture.
- **Low** · second avis 4 · rejeté : la preuve `review` est soumise par `pr_request_review` dans l'opération même qui écrit la revue du collègue et réannonce la PR : la réponse est à l'écran au moment de la preuve.
- **Low** · second avis 5 · rejeté : `_reaches_hook` (3.5, hors diff) rend vrai sans ref distante ; une création de `main` protégée est elle aussi refusée par le hook, l'explication reste juste.
- **Low** · second avis 6 · reporté (décision Anaël) : approbation conditionnée au clic « Demander une revue » (voir Décisions et Reports).
- Complexité : 0 constat (`pending_request` parcourt réactions × déclenchements par PR à chaque projection, tailles bornées par le scénario).
