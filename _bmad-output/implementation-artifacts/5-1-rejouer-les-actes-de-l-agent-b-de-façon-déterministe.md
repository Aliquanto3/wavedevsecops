---
story: "5.1"
key: 5-1-rejouer-les-actes-de-l-agent-b-de-façon-déterministe
title: Rejouer les actes de l'agent B de façon déterministe
status: review
branch: story/5-1-rejeu-agent-b
ad: [AD-3, AD-7, AD-18]
---

# Story 5.1 : Rejouer les actes de l'agent B de façon déterministe

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.1 » ; FR-12, NFR-3, UX-DR14.

## Livré

Quatre ops de setup (un module chacun dans `scenarios/ops/`, découverte automatique), toutes sous l'identité « Agent B » (`agent-b@exemple.test`, `PERSONAS["agent"]`) et avec une date fixe : `date` de l'op, sinon l'horloge du setup (une minute par acte). Aucun LLM.

| Op | Où | Arguments | `element_id` rendu |
|---|---|---|---|
| `agent_commit` | dépôt local, branche courante | `files` (`path`, `content`), `message`, `date` | `commit:<sha>` |
| `agent_push_force` | `origin.git` | `branch` (défaut `main`), `parent`, `files` (facultatif), `message`, `date` | `ref:refs/remotes/origin/<branch>` |
| `stash` | dépôt local | `message`, `files` (écrits avant), `include_untracked` (vrai), `author` (`agent`), `date` | `commit:<sha du stash>` |
| `agent_rebase_conflict` | dépôt local | `onto`, `branch` (courante), `date` | `ref:refs/heads/<branche>` |

- `agent_commit` n'écrit et n'indexe que les fichiers déclarés : un fichier de l'apprenant déjà présent n'est pas commité.
- `agent_push_force` réécrit une branche d'`origin` : le nouveau commit a pour parent `parent` (SHA, branche d'origin, `main~1`, ou `@alias` d'un commit) et pour arbre celui du parent plus `files`. L'ancien sommet n'est plus accessible depuis la branche. Le dépôt local n'est pas touché : `origin/<branch>` ne bouge qu'au prochain `git fetch` de l'apprenant (c'est le point de départ de l'erreur d'agent « historique écrasé »).
- `stash` refuse un arbre propre. `stash` est ouvert à tous les `author` pour les scénarios où c'est l'apprenant qui met de côté ; l'identité par défaut est l'agent.
- `agent_rebase_conflict` lance `git rebase <onto>` et exige que le rebase s'arrête en conflit (`rebase-merge` présent) ; sinon `SetupError`. Le dépôt reste « rebase en cours » : `RepoState.in_progress == "rebase"`, fichier avec marqueurs de conflit.
- Badge « Agent » : déjà fourni (`projections.ACTORS` reconnaît l'e-mail de l'agent, `repo.js` rend « Agent » en `primary-soft`, jamais en rouge, contraste vérifié par `test_repo_dom.py`). Un test de 5.1 vérifie que les commits de l'agent sortent du graphe avec `actor: agent`.

## Contrat pour 5.6, 5.7 et 5.8

- Un scénario du mode B enchaîne ces ops dans `setup:` avec `as: <alias>` ; les `commit:<sha>` rendus servent de bonnes réponses en alias (5.2). Ordre conseillé : état propre de l'apprenant (`commit`, `push`), puis actes de l'agent.
- Le SHA de chaque acte ne dépend que du scénario : identité, date, message, arbre en LF, `core.autocrlf=false`. Deux rejeux donnent la même empreinte (`engine.fingerprint`), ajoutée au catalogue par `scripts/update_fingerprints.py` quand le scénario existe.
- Réécriture d'`origin` : `commit_on_origin(ctx, persona, branch, files, message, date, start, parent=None, force=False)` accepte un `parent` explicite (résolu par `resolve_on_origin`) ; sans `force`, `parent` doit être le sommet actuel (sinon `SetupError`) ; l'op `agent_push_force` passe `force=True`. Le comportement de 3.4 (`parent=None`) est inchangé.
- Pour qu'un acte laisse l'apprenant dans un état précis : `stash` (entrée `stash@{0}` visible dans `RepoState.stash`), `agent_rebase_conflict` (rebase en cours), `agent_push_force` + `fetch` (divergence entre `main` et `origin/main`).
- `origin.git` est nu, donc sans reflog : après `agent_push_force`, le commit écrasé reste visible depuis le dépôt local (`main` de l'apprenant, `origin/main` avant `fetch`, reflog local), pas depuis `origin`. 5.7 le montre par ce côté.
- `stash` met aussi les fichiers non suivis de côté par défaut (`include_untracked: true`) ; à fixer explicitement dans 5.6 à 5.8 si un fichier non suivi doit rester visible.

## Décisions

- Pas de scénario ajouté au catalogue (c'est l'objet de 5.6 à 5.8) : les empreintes de référence de 5.1 sont celles du test `tests/test_agent.py` (SHA du commit de l'agent, du stash et empreinte de l'espace complet), exécuté par la CI sur les trois systèmes.
- `stash` n'a pas de préfixe `agent_` (critères d'acceptation) : l'identité vient de `author`, par défaut `agent`.

## Reports

- Réactions de l'agent aux revues (`colleague_reaction` accepte déjà `author: agent`) : rien de plus ici.
- Op de rebase qui se termine proprement (résolution automatique) ou `merge` en conflit : aucun scénario ne les demande.
- Scénarios B du catalogue, encart « Ce qui l'aurait bloqué » : 5.6 à 5.8.

## Tests

`tests/test_agent.py` : identité, date et fichiers de `agent_commit` (index limité à ses fichiers) ; badge `agent` dans le graphe ; push forcé (origin réécrit, ancêtre perdu, local intact avant `fetch`, refus sans `force`, parent introuvable) ; stash (identité, date, arbre propre, refus à vide) ; rebase en conflit (`in_progress`, fichier non fusionné, refus sans conflit) ; deux rejeux, même empreinte ; SHA et empreinte de référence en dur.

## Revue

Revue Opus du 2026-10-19 (une passe), avec la liste du second avis (Haiku).

| Sév. | Source | Constat | Suite |
|---|---|---|---|
| medium | second avis M1 | `agent_rebase_conflict` sur un rebase déjà en cours : `git rebase` échoue (128), le `rebase-merge` existant fait passer l'op pour réussie. | Corrigé : refus explicite d'un rebase en cours (`rebase-merge` ou `rebase-apply`) et code 1 exigé ; test `test_rebase_deja_en_cours_refuse` (échoue sur l'ancien code). |
| low | second avis L2 | `date` de `agent_rebase_conflict` sans effet. | Rejeté : `GIT_COMMITTER_DATE` date les commits rejoués avant le conflit ; le créneau d'horloge est voulu. |
| low | second avis L3 | `git commit` sans pathspec prend tout l'index. | Corrigé : `commit -- <fichiers>` (aucune op ne laisse aujourd'hui un fichier indexé, SHA de référence inchangé). |
| low | second avis L4 | `include_untracked` vrai par défaut. | Noté au contrat (5.6 à 5.8). |
| low | second avis L5 | `origin.git` nu, sans reflog. | Noté au contrat : 5.7 montre le commit écrasé par le dépôt local. |
| low | second avis L6 | SHA et empreinte vérifiés sous Windows seulement. | Vérifié par la CI de branche sur les trois systèmes (voir rapport de revue). |
| — | revue | Complexité : 0 constat (aucune structure qui grossit pendant l'exécution). | — |
