---
story: "2.1"
key: 2-1-préparer-un-bac-à-sable-déterministe-à-partir-d-un-yaml
title: Préparer un bac à sable déterministe à partir d'un YAML
status: review
branch: story/2-1-bac-a-sable
ad: [AD-3, AD-5, AD-6, AD-7, AD-12, AD-13, AD-18]
---

# Story 2.1 : Préparer un bac à sable déterministe à partir d'un YAML

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.1 ».

## Livré

- `wsfs` (nouveau) : `Layout` de l'espace (AD-5), chemins confinés (`check_relative`, `confine` : refus de l'absolu, de `..`, de `.git/`, des liens qui sortent ; `\` et `:` refusés à l'écriture seulement), écriture UTF-8 en LF atomique, `read_bytes`, `iter_files`, `write_json` canonique (trié, LF), `remove_tree` (objets git en lecture seule sous Windows).
- `gitio` (ajouts) : `hermetic_environment` (AD-3 complet : `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL=<data>/gitconfig`, `GIT_CONFIG_COUNT` avec les 16 réglages forcés et `core.hooksPath`, `GIT_TERMINAL_PROMPT=0`, éditeurs `:`, variables `GIT_*`, locale, proxy, `EDITOR`/`PAGER` du poste retirées), contexte interne (`LC_ALL=C`) et apprenant (locale sondée). Classe `Git` (`run`, `internal` qui lève `GitError`), lectures plumbing de l'empreinte (`head_record`, `refs`, `reachable_objects`, `index_entries`, `worktree_paths`, `stash_list`).
- `scenarios` (nouveau) : modèle pydantic `Scenario` (`schema_version` 1, `scenario_id`, `mode`, `title_text`, `section`, `station`, `tracks`, `tools`, `template`, `setup`, `steps` — liste vide admise), `StepSpec` (`step_id` + `type`). Chargeur : erreurs en français qui nomment le champ (`setup[1].message`) et la ligne ; règles entre champs (alias `@x` défini avant usage, alias et `step_id` uniques, outils connus de `tools.toml`, nom de fichier = `<scenario_id>.<mode>.yaml`) ; `content_hash` en LF.
- Registre d'ops `scenarios/ops/` : une op par module, découverte automatique (`Args` + `apply(args, ctx) -> element_id`) ; `write_file`, `commit`, `branch`, `switch`, `push`. Toute op porte `as: <alias>`, résolu en `element_id` (AD-2) ; les champs de référence acceptent `@alias`.
- Setup déterministe : identités fixes (apprenant, collègue, agent B), horloge du setup (5 janvier 2026, 9 h UTC, une minute par commit, ou date fixe de l'op), dates au format interne de git, fichiers écrits par `wsfs` en LF, commits `--no-verify`, remote `origin` en `../origin.git`.
- `engine` (nouveau) : `prepare_workspace` (espace `<data>/workspaces/<parcours>/<scenario_id>.<mode>/` avec `repo/`, `origin.git/`, `hooks/`, `run.json` ; nettoyé en cas d'échec ; `replace` pour reconstruire), empreinte canonique d'AD-6 (`canonical_records`, `fingerprint`), empreintes de référence (`compute_references`, `load_references`, `write_references`).
- `contracts` (ajout) : `element_id` / `parse_element_id`, segments encodés en pourcentage. `config` (ajouts) : `git_timeout_s`, `gitconfig_path()`, `workspaces_path()`, `scenarios_path()`.
- Contenu : `content/scenarios/bac-a-sable-libre.A.yaml` (deux commits sur `main`, poussés vers `origin`) et `content/fingerprints.json`, régénéré par `scripts/update_fingerprints.py`.
- Tests : `test_wsfs`, `test_scenarios`, `test_setup` (vrai git, dossier temporaire), `test_fingerprints` (référence par scénario et parcours, pas de référence orpheline) ; règle statique « seul `wsfs` écrit dans le bac à sable » (`scenarios`, `terminal`, `engine`, `github_sim`). Fixture `git_path` : git absent ignoré en local, échec en CI.
- CI : sous Linux, scénarios rejoués dans `sudo unshare --net` (contrôle 4 d'AD-13) ; sous Windows, fichiers réextraits en `core.autocrlf=true` puis empreintes recomparées.

## Décisions

- L'empreinte et la préparation vivent dans `engine` (« instantanés, empreinte » du spine). `engine` importe `gitio` (lectures de l'empreinte) et `toolrun` (résolution de git par le registre) : ces flèches ne figurent pas sur le schéma, mais ne remontent pas.
- Ordre des lignes du stash conservé par un indice (`repo stash <n> <sha>`) avant le tri global. Objets : identifiants seulement (le contenu est déjà haché par git).
- `github.json` n'entre pas encore dans l'empreinte : il n'existe qu'avec `github_sim`.
- `GIT_CEILING_DIRECTORIES` vers la racine de l'espace (ajout à AD-3) : un dépôt abîmé ne fait pas remonter git vers un dossier parent.
- Remote `origin` relatif (`../origin.git`) : l'espace reste déplaçable ; les commandes git tournent toujours avec `cwd=repo/`.
- `template` n'admet que `empty` : les gabarits `content/exercise/<parcours>/` étendront le `Literal` avec leur story.
- Clé de référence `<parcours>/<scenario_id>.<mode>` : les parcours auront des gabarits différents, donc des empreintes différentes.
- La sortie de `procs.run` est décodée en UTF-8 : suffisant pour les lectures plumbing (`-z`, identifiants) ; aucun contenu binaire ne transite par la sortie.

## Reports

- Types d'étape (`scenarios/steps/`, `check -> Verdict`), consigne, indices, bonnes réponses : stories des étapes. `StepSpec` admet des champs libres en attendant.
- Ops `stash`, `colleague_commit`, `agent_commit`, `agent_push_force`, `open_pr`, `set_protection`, `install_hooks` : leurs stories (un module chacune).
- Lint de contenu complet (AD-7 : `job_id`, barrières, clés d'explication) : story du lint ; le chargeur couvre déjà ops, outils, alias et `step_id`.
- Instantanés, restauration, file d'opérations, `epoch` : stories 2.2 et suivantes. `run.json` porte déjà `epoch`, `content_hash`, `setup_fingerprint`, `aliases`, `restoring`.
- `github.json` dans l'empreinte : avec `github_sim`.
- Les steps CI `unshare -n` et `autocrlf=true` n'ont pas pu être exécutés localement (poste Windows) : à confirmer sur le premier run de la branche.
- `ruff format` signale trois fichiers antérieurs (`cli`, `procs`, `web/app.py`) : hors périmètre, non modifiés.
