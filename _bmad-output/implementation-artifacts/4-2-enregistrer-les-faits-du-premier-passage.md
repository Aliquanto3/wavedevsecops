---
story: "4.2"
key: 4-2-enregistrer-les-faits-du-premier-passage
title: Enregistrer les faits du premier passage
status: done
branch: story/4-2-faits-premier-passage
ad: [AD-14, AD-20, AD-1, AD-5]
---

# Story 4.2 : Enregistrer les faits du premier passage

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 4.2 ».

## Livré

- `progress/facts.py` : `Fact` (`kind` : `step_validated`, `quiz_first_attempt{correct}`, `hint_opened{tier, delay_ms, read_ms}`, `scenario_completed` ; `track`, `scenario_id`, `mode`, `step_id`, clé `workspace_id/epoch/op_id`, `at`). `ProgressStore.for_dir(data_dir)` : un magasin, donc un verrou, par dossier de données ; `submit(facts)` ajoute à `progress.json["facts"]` (ajout seulement, écriture atomique via `write_json_atomic`) et rend les faits réellement ajoutés ; `facts()` ; `progress(track, scenario_id, mode)`.
- Identité d'un fait = ce qu'il constate : `(kind, parcours, scenario_id, mode, step_id[, palier])`. Le premier fait d'une identité reste ; un doublon (même clé d'idempotence, rejeu après arrêt brutal, Recommencer) est ignoré. La clé `(workspace_id, epoch, op_id)` est consignée dans le fait.
- États dérivés `derive(...)` -> `ScenarioProgress` : `todo | in_progress | done` (aucun fait / au moins un / `scenario_completed`), étapes validées, `first_try_score` (pourcentage de premiers essais justes, `None` sans quiz), nombre d'indices. Rien n'est écrit : tout se recalcule des faits.
- `progress.json` : nouvelle clé `facts` (liste, absente = vide), `schema_version` inchangée (ajout seulement, AD-20). Un fichier de version future n'est pas modifié (`FutureSchemaError`) ; un fichier illisible donne `UnreadableDataError` (devenu `app_error` dans la file, jamais une trace).
- Moteur (`engine/operations.py`, `engine/steps.py`, `engine/manager.py`) : `StepOutcome.facts` (brouillons de faits : `StepRunner` y met `step_validated`, et `scenario_completed` à la dernière étape) ; après `run.json` (écrit par `StepRunner.validate`), la file complète la clé d'idempotence, soumet à `progress`, puis publie `progress_updated{track, scenario_id, mode, facts, step_ids}` s'il y a du neuf. Ordre : `… state_projected → step_verdict → step_explanation → progress_updated → engine_state(repos)`. Paramètres `progress` et `replay` du moteur ; le gestionnaire les branche (`ProgressStore.for_dir(settings.resolved_data_dir())`, `StepRunner.replay`).
- Reprise : au démarrage de la file (avant la projection d'ouverture), `StepRunner.replay` rend les faits que `run.json` établit déjà : les étapes de `run.json["validated"]` (liste des `step_id` réussis, écrite par `validate` avec le nouveau `step_id`, dans la même écriture) et la fin du scénario si `step_id` est `null`. Un `run.json` antérieur, sans `validated`, retombe sur la position (étapes avant l'étape courante). Le magasin n'ajoute que les manquants. Rejouer deux fois n'ajoute rien et n'émet rien.
- Tests : `test_progress_facts.py` (magasin : ajout, doublon, premier passage non remplacé, parcours, indices par palier, score, verrou sous 20 fils, version future, fichier illisible) ; `test_progress_engine.py` (vrai git : fait enregistré après `run.json`, `progress_updated`, commande sans validation muette, fin de scénario et états dérivés, arrêt brutal simulé, rejeu sans doublon, Recommencer) ; `test_steps.py` : séquence d'événements alignée (ajout de `progress_updated`).

## Décisions

- L'ordre `terminal_output` puis `step_verdict` dans une même opération est déjà vérifié, avec la liste complète des événements, par `test_etape_reussie_quelle_que_soit_la_commande` ; il entre dans ce périmètre puisque la séquence y est étendue de `progress_updated`.
- Dédupliquer sur l'identité plutôt que sur la seule clé `(workspace_id, epoch, op_id)` : après un Recommencer, l'`epoch` et l'`op_id` changent, et le fait du premier passage doit rester. La clé seule ne l'assurerait pas ; elle sert de trace.
- `progress_updated` n'est pas dans `SEQUENCE_KINDS` (une opération peut en émettre, par exemple pour un indice) ; il est publié par la file après le verdict.
- Les faits `quiz_first_attempt` et `hint_opened` n'ont pas encore d'émetteur (types de quiz et indices : stories suivantes). Le magasin, l'identité et les états dérivés les gèrent déjà et sont testés directement ; ces stories ajoutent seulement des brouillons à `StepOutcome.facts` (ou soumettent via `ProgressStore`).
- Les brouillons de faits sont des `dict` dans `StepOutcome` pour ne pas faire importer `progress` à `scenarios` ; seule la file construit les `Fact`.
- Aucun changement dans `contracts/`, `events/` ni `config.py` (la charge `ProgressUpdated` reste ouverte, `extra="allow"`).

## API du magasin (pour 4.4, 4.5 et l'Epic 9)

- `ProgressStore.for_dir(settings.resolved_data_dir())` : le magasin partagé (ne pas instancier `ProgressStore` directement hors tests, sinon le verrou n'est plus unique).
- `submit(list[Fact]) -> list[Fact]` : ajoute les faits dont l'identité est nouvelle, rend ceux ajoutés ; lève `FutureSchemaError` / `UnreadableDataError` (`AppError`).
- Depuis une opération de la file, préférer des brouillons dans `StepOutcome.facts` (dict : `kind`, `track`, `scenario_id`, `mode`, `step_id`, plus `correct` ou `tier`/`delay_ms`/`read_ms`) : la file ajoute la clé et publie `progress_updated`. Un fait soumis hors de la file doit écrire d'abord `run.json` s'il doit être rejoué.
- Lecture : `facts()`, `progress(track, scenario_id, mode)`, `all_progress()` (tous les scénarios en un passage).

## Reports

- Émission des faits de quiz/désignation (premier essai) et d'indices, « dernier scénario ouvert », « preuves vues par barrière », remises à zéro consignées : stories 4.4, 4.5 et suivantes.
- Exposition web des états dérivés (accueil, « Reprendre ») et exports : stories de l'Epic 9 et suivantes.
- Le suivi est écrit même si le serveur n'a pas appelé `ensure_progress` (tests, usage hors CLI) : le fichier est alors créé par le magasin, avec les mêmes champs de base.

## Revue

Reviewer (Opus), après rebase sur `origin/main` (4.1, 4.3) sans conflit.

- medium, reviewer : rejeu par position dans le scénario ; une étape insérée ou déplacée avant l'étape courante (mise à jour du contenu, cas prévu par `test_step_id_stable_si_les_etapes_sont_reordonnees`) était enregistrée comme validée à chaque réveil, définitivement. Corrigé : `run.json["validated"]`, rejeu sur cette liste ; test `test_rejeu_apres_reordonnancement_n_invente_aucune_etape` (échouait avant).
- medium, second avis 1 : le test Recommencer ne passait pas par une seconde validation. Corrigé : vrai rétablissement de l'instantané d'installation (nouvel epoch), pointeur remis au début, vraie seconde validation ; ni doublon, ni remplacement, ni `progress_updated`. L'opération Recommencer elle-même n'existe pas encore.
- low, second avis 2 : atomicité non prouvée. Corrigé : test d'arrêt entre l'écriture du temporaire et le renommage (fichier précédent intact, nouvelle soumission ensuite).
- low, second avis 3 : verrou intra-processus. Rejeté : le verrou d'instance unique (`cli`) empêche un second processus ; `ensure_progress` du démarrage précède les moteurs.
- low, second avis 4 : `progress_updated` du rejeu avant la projection d'ouverture, `op_id` nul. Rejeté : hors opération par nature (aucune séquence à respecter), et un client qui se connecte relit l'état ; documenté.
- low, second avis 5 : `progress.json` illisible ou futur, chaque validation donne `app_error`. Rejeté : comportement voulu (AD-20, fichier jamais modifié) ; le message donne l'action (renommer le fichier ou mettre à jour) et les faits manquants sont rejoués au réveil suivant grâce à `validated`.
- low, second avis 6 : clé d'idempotence jamais comparée. Rejeté : une même clé couvre deux faits légitimes (`step_validated` et `scenario_completed` d'une même opération) ; la clé identique est un cas particulier de l'identité, testé (`test_meme_cle_soumise_deux_fois_est_ignoree`).
- low, second avis 7 : `run.json` sans `track` ou `mode`. Rejeté : `prepare_workspace` les écrit toujours ; l'erreur éventuelle devient `app_error`, jamais une trace.
- low, second avis 8 : pas d'émetteur pour le quiz et les indices. Reporté, cohérent avec epics.md (4.5 quiz et désignation, indices ensuite) : magasin, identité et états dérivés testés ; API ci-dessus.
- low, Complexité, reviewer : `progress()` relit tout le fichier ; l'accueil appelé par scénario serait en O(scénarios × faits) (mesuré : 300 scénarios, 3 000 faits, 1,1 s). Corrigé : `all_progress()` en un passage. `submit` reste O(faits) par validation (24 ms à 3 000 faits, borne du programme) : accepté.
- low, reviewer : un rétablissement (4.3) ne touche pas `run.json` ; le rejeu pendant un `restoring` résiduel lit donc un pointeur cohérent. Rien à corriger.
