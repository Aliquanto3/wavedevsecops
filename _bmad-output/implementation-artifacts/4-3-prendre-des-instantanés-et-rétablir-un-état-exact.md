---
story: "4.3"
key: 4-3-prendre-des-instantanés-et-rétablir-un-état-exact
title: Prendre des instantanés et rétablir un état exact
status: review
branch: story/4-3-instantanes
ad: [AD-1, AD-5, AD-6, AD-8, AD-12]
---

# Story 4.3 : Prendre des instantanés et rétablir un état exact

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 4.3 » ; AR-7 ; spine AD-6, AD-1.

## API des instantanés (`engine/snapshots.py`, exportée par `engine`)

C'est l'API dont dépendent 4.4 (Recommencer), 4.5 (quiz), 5.x et 6.6 (exécution du code LLM).

- **Contenu** : `snapshots/<id>/` contient `repo/`, `origin.git/`, `github.json`, `hooks/` (`wsfs.SNAPSHOT_ENTRIES`, `Layout.entries()`) et `snapshot.json` : `{schema_version: 1, snapshot_id, reason, fingerprint}`. L'empreinte est **calculée sur la copie** (git borné à la copie). Les verrous de git (`index.lock`, `HEAD.lock` de `.git/` et `origin.git/`) ne sont jamais copiés (AD-12). Ni `ci/`, ni `cache/`, ni `run.json`.
- **Prise** : `take_snapshot(layout, git, settings, *, reason, expected=None) -> Snapshot` est appelé **depuis le corps d'une opération de la file**. La copie est montée dans `snapshots/.staging-<id>/` puis renommée : un instantané n'est jamais à moitié écrit. `expected` (empreinte de l'espace) contrôle la copie et lève `SnapshotError` en cas d'écart. Les identifiants croissent et ne sont jamais réutilisés. `reason` : `setup` (le 0), `quiz` (4.5), `exercise` (6.6), etc.
- **Instantané 0** : pris par `prepare_workspace` juste après l'empreinte de fin de setup (`expected = setup_fingerprint`), dans le même bloc d'erreur que le setup. Il est donc pris avant tout run du pipeline et avant toute édition. Son empreinte est celle de référence (`content/fingerprints.json`, inchangé).
- **Lecture** : `list_snapshots(layout)` donne les instantanés complets, du plus ancien au plus récent ; `get_snapshot(layout, id)` et `latest_snapshot(layout)` en donnent un. `Snapshot{snapshot_id, fingerprint, reason, path}`. Un dossier sans manifeste lisible est ignoré.
- **Rétention** : `prune_snapshots` est appelé après chaque prise. Au plus `Settings.max_snapshots` (20, au moins 2) sont gardés ; les plus anciens partent, sauf le 0 et le dernier. Un seul pool par espace : la 6.6 et la 4.5 le partagent, et la règle « 0 et dernier » protège l'état de départ (cf. Reports).
- **Restauration** : `WorkspaceManager.restore(workspace_id, snapshot_id) -> Future[OpResult]` soumet `restore_operation(snapshot_id, git_path)`. Cette opération `restore_state` est en état `restoring`, `writes=False` (admise en `quiz_altered`, qu'elle quitte : retour à `idle` si elle réussit), sans validation d'étape. Une opération qui a déjà la file peut appeler `restore_snapshot(layout, git, settings, id, epoch=ctx.epoch)` directement.
- **Échec** : `RestoreFailed` (`AppError`) donne « Le rétablissement de l'état a échoué : … » et l'action « Recommencez le scénario… », consignés dans `run.json.restore_failed = {snapshot_id, reason_text}`.

## Livré

- Procédure de restauration (AD-6) : l'`epoch` est incrémenté par la file (`restoring` ∈ `EPOCH_STATES`) et écrit dans `run.json` avec `restoring{snapshot_id, epoch, phase: copy}` avant toute modification. Ensuite, `ci/` est vidé et l'instantané copié dans `snapshots/.restore/staging-<jeton>/` (`phase: swap`). Chaque entrée courante est renommée vers `snapshots/.restore/trash-<jeton>/`, puis remplacée par sa copie, avec `wsfs.move` : trois essais, pauses croissantes `restore_retry_ms` puis `2 × restore_retry_ms`, sur `PermissionError`. Puis `phase: verify` : l'empreinte est comparée à celle du manifeste, la corbeille supprimée (au mieux) et `restoring` et `restore_failed` effacés.
- Si un renommage est refusé après trois essais, un retour arrière (au mieux) remet les entrées d'avant, puis l'espace passe en `restore_failed`. Une empreinte différente, un instantané absent ou une copie en échec donnent aussi `restore_failed`.
- Événements : `restore_started{snapshot_id}` (charge fixée, n'est plus ouverte), puis `restore_ended{status, snapshot_id, reason_text}` (champs ajoutés avec défaut). En échec, `app_error` (cause et action « Recommencer ») suit dans la séquence de la file. Tous portent le nouvel `epoch`.
- Marque `restored` (AD-2) : après une restauration réussie, `OpContext.data["restored"]` conduit `repo_projector` à appeler `projections.project(..., after_restore=True)`. Les commits absents de l'état précédent portent alors `restored` (et « rétabli » dans `a11y_name_text`) au lieu de `new`. Le placement du graphe garde sa mémoire.
- Surveillant : `STOP_WATCH_STATES = {"restoring"}` dans `manager`. Il est **arrêté** (`stop()`), pas suspendu, car sous Windows son handle sur `repo/` bloquerait le renommage. Un nouveau surveillant est créé au retour au repos.
- Reprise au démarrage : `WorkspaceManager._open` lit `run.json`. Si un `restoring` résiduel est présent, il place `resume_operation` en tête de file. `resume_restore` supprime les entrées courantes (état inconnu), recopie l'instantané et vérifie l'empreinte. Un instantané absent ou une reprise en échec donnent `restore_failed`.
- `wsfs` : `SNAPSHOT_ENTRIES`, `Layout.entries()`, `copy_entries` (liens non suivis, verrous de git exclus), `move` (renommage à essais espacés, jamais par-dessus une entrée), `remove_entry`. `config` : `max_snapshots` (20), `restore_retry_ms` (250). `run.json` : clé `restore_failed` ajoutée (`null` au setup), pas de changement de version (ajout seulement, `.get`).
- Tests `tests/test_snapshots.py` (vrai git, un setup par module recopié) :
  - instantané 0 = fin de setup = empreinte de référence ;
  - copie contrôlée ; `index.lock` non copié ; rétention `[0, 3, 4]` ;
  - restauration exacte par empreinte, `ci/` vidé, `epoch` et journal dans `run.json` ;
  - écart d'empreinte et instantané absent → `restore_failed` ;
  - verrou simulé (tous OS) : trois essais, pauses croissantes, retour arrière ;
  - **vrai fichier verrouillé sous Windows** (handle ouvert), puis réussite une fois le fichier libéré ;
  - dans la file : ordre des événements, `epoch`, surveillant arrêté puis relancé, marque `restored`, sortie de `quiz_altered` ;
  - reprise au démarrage, réussie ou en `restore_failed`.

## Décisions

- La copie est montée à côté avant le premier renommage : la phase où l'espace est incomplet se réduit à des renommages, et un retour arrière reste possible. La reprise au démarrage, elle, ne cherche pas à finir un échange : elle repart de l'instantané, seule source fiable.
- `restore_failed` n'est pas un état de `EngineStateName` (liste fixée par AD-1) : c'est un statut de `restore_ended` et une clé de `run.json`. L'espace revient à son état de repos d'avant (il reste en `quiz_altered` si l'échec arrive pendant un quiz).
- La restauration remplace `github.json` par un renommage de `wsfs`. `github_sim` reste le seul à en **écrire** le contenu : la restauration remet un fichier qu'il a écrit.
- Les opérations de restauration sont `writes=False`, sinon elles seraient refusées en `quiz_altered`, alors que c'est le seul moyen d'en sortir.

## Écarts avec la 6.6 (branche `story/6-6-execution-llm`, à raccorder)

- Son `engine/snapshots.py` et `wsfs.copy_entries` sont remplacés par cette API. L'instantané 0 n'est plus pris au premier lancement : il est pris au setup, donc `take_snapshot` ne rend plus un `int` mais un `Snapshot`. Le manifeste remplace `fingerprint.txt`, l'empreinte est calculée sur la copie, et un seul pool par espace (rétention ci-dessus). La 6.6 doit appeler `take_snapshot(..., reason="exercise")` et `restore_snapshot` / `latest_snapshot` de cette API, sans prendre de 0 elle-même.
- La 6.6 retirait les réessais `os.replace` de `wsfs._replace` : ils sont conservés ici.

## Reports

- Intention `restore_state` (bouton « Rétablir ») et son modèle : à brancher par la story de l'UI qui l'expose (4.5 ou 4.6). `WorkspaceManager.restore` est prêt.
- « Seule action Recommencer » en `restore_failed` : le refus des autres intentions et l'effacement de `restore_failed` reviennent à 4.4 (Recommencer, avec reconstruction si le 0 manque ou échoue).
- Arrêt des runs du pipeline de l'espace : à brancher avec `ci` (AD-10). `ci/` est déjà vidé.
- Surveillant pendant `setup` avec `replace=True` (Recommencer par reconstruction, 4.4) : il n'est que suspendu, et le même verrou Windows peut gêner `remove_tree`. 4.4 pourra ajouter `setup` à `STOP_WATCH_STATES`.
- Instantané avant chaque choix de quiz : appel de `take_snapshot(..., reason="quiz")` par 4.5.

## Revue

Rebase sur `origin/main` (2.4) : conflit trivial dans `config.py` (réglages `terminal_timeout_s` et `max_snapshots` / `restore_retry_ms` gardés tous deux).

- high, second avis H1 : corrigé. Une exception autre que `RestoreFailed` (git en échec à la vérification, `run.json` impossible à écrire) ne donnait ni `restore_ended{restore_failed}` ni `restore_failed` dans `run.json`. `_run_restore` la convertit désormais en `RestoreFailed`, avec un test.
- medium, second avis H2 : reporté à 4.4, déjà noté dans les Reports. Après `restore_failed`, l'espace revient au repos et accepte les écritures. Aucune intention ne déclenche encore de restauration (bouton à venir en 4.5/4.6) ; le refus des autres intentions revient à Recommencer (4.4). Vérification à faire : en 4.4, une intention d'écriture est refusée tant que `run.json.restore_failed` est posé.
- medium, second avis M3 : corrigé. Le retour arrière n'avait qu'un essai, et `restoring` était effacé même s'il échouait. Il a maintenant trois essais espacés. S'il reste incomplet, `restoring` est gardé et le démarrage suivant reprend la copie (test).
- medium, second avis M4 : corrigé autrement. Si la reprise échoue, `restoring` est gardé (état inconnu) et le démarrage suivant retente. Le même maintien vaut pour une exception imprévue après la phase `copy`. Les suppressions sans réessai restent, le surveillant étant arrêté pendant `restoring`.
- low, second avis L5 : rejeté en partie. Le test `quiz_altered` tourne sur tous les OS : le `skipif` porte sur le test du fichier verrouillé. L'assertion d'état du moteur a été ajoutée à `test_restore_failed_dans_la_file`.
- low, second avis L6 : rejeté. `.staging-N` est supprimé en cas d'échec et de nouveau avant la prise suivante, et `.restore/` est vidé en fin de restauration réussie. La corbeille d'un échec reste, puis est supprimée à la prochaine restauration.
- low, second avis L7 : reporté. Seuls `index.lock` et `HEAD.lock` sont exclus de la copie (AD-12). Les autres verrous de refs (`*.lock`) sont rares hors d'une commande en cours, et la file sérialise les commandes.
- low, second avis L8 : rejeté. Le libellé suit `restore_ended{status: ok}`, et l'UI de la restauration (4.5/4.6) choisira son texte.
- Complexité : 0 constat. La rétention et la liste des instantanés sont en O(n), avec n ≤ `max_snapshots`, et ne tournent qu'à la prise ou à la restauration.
- API publique inchangée (`take_snapshot`, `restore_snapshot`, `WorkspaceManager.restore`, `resume_restore`) ; `_fail` reçoit `keep_pending` (interne).
