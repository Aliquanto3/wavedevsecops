---
story: "2.2"
key: 2-2-faire-passer-chaque-action-par-la-file-d-opérations
title: Faire passer chaque action par la file d'opérations de l'espace
status: review
branch: story/2-2-file-operations
ad: [AD-1, AD-5, AD-6, AD-17, AD-19, AD-20]
---

# Story 2.2 : Faire passer chaque action par la file d'opérations de l'espace

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.2 ».

## Livré

- `events` (feuille) : catalogue `Kind` des 19 `kind` d'AD-17 et un modèle pydantic par `payload` (`PAYLOADS`, `validate_payload`) ; `SEQUENCE_KINDS` réservés à la file. Enveloppe `Envelope{boot_id, seq, ts, workspace_id, epoch, op_id, kind, payload}` (`ts` ISO 8601 à la milliseconde, `id` SSE `<boot_id>:<seq>`). `EventLog` : `seq` strictement croissant par espace, tampon circulaire de `Settings.event_buffer`, `attach(last_event_id, abonné)` qui rend les événements manqués et abonne sous le même verrou (ni trou ni doublon), ou `None` (`boot_id` différent, `seq` sorti du tampon ou futur) ; `resync_envelope`. `DIAGNOSTIC_CHECK` pointe désormais sur le catalogue.
- `engine/operations.py` : `WorkspaceEngine`, un fil par espace qui exécute les `Operation` en série. Ordre fixe émis par la file seule : `engine_state` → `op_started` → sortie → `op_exit{code, duration_ms}` → `state_projected{views, fingerprint}` → `step_verdict` → `step_explanation` → `engine_state` (repos). `OpContext.emit` refuse les `kind` de la séquence. `epoch` incrémenté à l'entrée de `setup`/`restoring` et écrit dans `run.json` ; une opération produite hors file porte son `epoch` et est rejetée (`StaleOperation`) à l'entrée **et** à l'exécution. Refus en `OperationRefused(reason_text)` : `quiz_altered` pour une écriture, file pleine (`Settings.max_pending_ops`), espace en veille. Exception métier → `app_error{cause_text, action_text}` ; autre exception → texte générique, trace au journal seulement. Projection et validation sont des stratégies injectées (empreinte en 2.2 ; vues en 2.6, verdicts en 4.1).
- `engine/manager.py` : `WorkspaceManager` (un `boot_id` par lancement), `workspace_id` = `<parcours>.<scenario_id>.<mode>`, ouverture paresseuse d'un espace existant, `create()` qui passe le setup par la file (état `setup`), au plus `Settings.max_active_workspaces` espaces actifs (LRU : le moins récent s'endort, file et surveillant arrêtés, réveil à la demande avec l'`epoch` relu ; le journal survit à la veille). Opération `external_change` filtrée par empreinte (pré-vérification silencieuse).
- `engine/watcher.py` : `TreeWatcher` (`watchfiles` sur `repo/`, hors `.git/`), suspendu pendant `command`/`setup`/`restoring`, reprise après `Settings.watch_quiet_ms`.
- `engine/intents.py` : registre des intentions (modèle pydantic + constructeur d'`Operation`) ; `engine/runfile.py` : `run.json` versionné (`load_run` avec migrations numérotées, refus d'une version future ; `save_run`).
- `web/workspaces.py` : `GET /api/ws/<id>/state`, `GET /api/ws/<id>/events` (SSE, `Last-Event-ID` ou `?last_event_id=`, `resync_required` adressé au seul flux, maintien toutes les `Settings.sse_heartbeat_s`), `POST /api/ws/<id>/<intent>` (202 `{op_id}`, 404 inconnu, 422 invalide, 409 + `reason_text`). Derrière les protections d'AD-19 existantes. `shutdown_app` endort les espaces ; `cli.Instance.stop` l'appelle (sinon uvicorn attend les flux SSE).
- `wsfs.read_entry` (report de 2.1) : l'empreinte lit un lien symbolique comme sa cible écrite, sans le suivre ; un lien qui sort de l'espace ou vise `.git/` ne la fait plus échouer.
- `config` : `event_buffer` (1000), `max_active_workspaces` (3), `max_pending_ops` (32), `watch_quiet_ms` (500), `sse_heartbeat_s` (15), `engine_stop_timeout_s` (30).
- Tests : `test_events`, `test_operations` (ordre, série sous concurrence, `epoch` périmé à l'entrée et à l'exécution, `app_error`, `quiz_altered`, file pleine, veille), `test_workspace_manager` (LRU, réveil, surveillant), `test_workspace_api` (vrai serveur et vrai git : ordre SSE, reprise `Last-Event-ID`, `resync_required` sur `boot_id` et sur débordement, 409/404/422, `Origin`), règle statique « seule la file publie une explication » (`test_architecture`), lien symbolique dans l'empreinte (`test_setup`). Synchronisation par `Event`/`Future`, sans `sleep`.

## Décisions

- `events` reste une feuille stricte : les charges dont le schéma vit dans `contracts` (`diagnostic_check`, puis les vues) sont transportées en dictionnaires ; les `kind` dont la story n'est pas faite ont un modèle ouvert (`extra="allow"`) à resserrer par leur story.
- Fils plutôt qu'asyncio pour la file : les opérations appellent git et des outils bloquants ; le flux SSE reçoit les événements par `call_soon_threadsafe`.
- `resync_required` n'entre pas dans le journal : il est émis au `seq` courant sur le seul flux concerné, que le front suit d'un `GET …/state`.
- `op_exit.code = None` quand l'opération n'a pas abouti (après un `app_error`) ; la projection est quand même recalculée (le disque a pu changer), la validation d'étape non.
- Projection d'ouverture : à l'ouverture ou au réveil, la file publie un `state_projected` (sans `op_id`) avant toute opération.
- `quiz_altered` et `idle` sont des états de repos (fixés par une opération via `set_rest_state`) ; `command`, `setup`, `restoring`, `exporting` n'existent que pendant une opération.
- Aucune intention du catalogue n'est enregistrée en 2.2 : la route et le registre sont prêts, `terminal_line` arrive avec 2.4, `save_file` avec 2.8. Les tests enregistrent une intention de test.
- Les routes GET ne créent pas d'espace : seul `WorkspaceManager.create()` lance un setup.

## Reports

- `procs.spawn -> Handle` non bloquant et Job Object Windows (AD-12) : aucune commande longue en 2.2 ; à faire avec le terminal (2.4) et `interrupt` (traité hors file).
- Ouverture d'un scénario depuis l'interface (route qui appelle `create()`), `restart`/`restore_state` (instantanés, AD-6) : leurs stories. La restauration devra arrêter le surveillant (pas seulement le suspendre) : sous Windows il tient un handle sur `repo/`.
- Empreinte de la dernière projection persistée dans `run.json` pour comparer à la reprise (AD-6 « un écart donne un changement externe ») : avec les instantanés.
- Arrêt des runs du pipeline à la mise en veille : avec `ci` (AD-10).
- Front : magasin de projection alimenté par le flux SSE : stories 2.3 et suivantes.
- Interruption de l'opération en cours à la mise en veille (arrêt de l'arbre de processus par `procs`, AD-12) : avec 2.4. En attendant, un espace endormi pendant une opération refuse sa réouverture (409) tant que l'ancienne file tourne ; vérifier en 2.4 qu'une commande bloquée est bien tuée au-delà de `engine_stop_timeout_s`.

## Revue

Revue Opus (2026-10-18), après rebase sur `main` (221000e, sans conflit) et liste du second avis (Haiku).

- high · second avis 1 · corrigé · Réouverture pendant l'arrêt de l'ancienne file : deux écrivains sur le même layout et le même journal (y compris sans dépassement du délai, entre le retrait de l'espace actif et la fin du `join`). `WorkspaceManager` garde les files en cours d'arrêt (`_stopping`) et refuse la réouverture en 409 tant que leur fil vit ; la veille LRU choisit d'abord un espace au repos. Tests `test_pas_de_reouverture_tant_que_l_ancienne_file_ecrit`, `test_la_veille_prefere_un_espace_au_repos`. Interruption de l'opération : reportée à 2.4 (voir Reports).
- medium · second avis 2 · corrigé · `Last-Event-ID` avec un chiffre non ASCII (`²`, `٣`) : `int()` levait (500). Test paramétré dans `test_events`.
- medium · second avis 3 · corrigé · Opérations en attente refusées à la veille sans événement alors que l'apprenant a reçu un 202 : la file publie elle-même (seul écrivain) un `app_error` par opération abandonnée, après celle en cours. Test étendu `test_veille_refuse_les_operations_en_attente`.
- low · second avis 4 · corrigé · Surveillant arrêté avant la file : la file est désormais fermée d'abord (`closed` posé), le surveillant arrêté après son `join`, donc `_follow_state` ne le relance plus.
- low · second avis 5 · corrigé · File d'abonné SSE non bornée : bornée à `Settings.event_buffer` ; au débordement, le flux envoie `resync_required` et se ferme.
- low · second avis 6 · corrigé · Abonné qui fuit si la réponse ne démarre jamais : l'abonnement se fait dans le générateur du flux.
- low · second avis 7 · corrigé · Arrêt en série jusqu'à 90 s : `request_stop` sur toutes les files, puis attente dans un délai commun (`engine_stop_timeout_s`).
- low · second avis 8 · corrigé · Lien de `hooks/` hors de l'espace : l'empreinte lit `hooks/` par `read_entry` (lien = cible écrite). Assertion ajoutée au test des liens de `test_setup` (sautée sous Windows sans droit de lien, exécutée en CI Linux et macOS).
