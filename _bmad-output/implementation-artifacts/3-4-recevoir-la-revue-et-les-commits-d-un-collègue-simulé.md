---
story: "3.4"
key: 3-4-recevoir-la-revue-et-les-commits-d-un-collègue-simulé
title: Recevoir la revue et les commits d'un collègue simulé
status: review
branch: story/3-4-collegue-simule
ad: [AD-3, AD-7, AD-8]
---

# Story 3.4 : Recevoir la revue et les commits d'un collègue simulé

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 3.4 » ; FR-6, FR-7, UX-DR14.

## Livré

- Op `colleague_commit` (`scenarios/ops/colleague_commit.py`) : `branch` (défaut `main`), `files` (`path`, `content`), `message`, `date`, `start`. Le commit est écrit dans `origin.git` sans toucher au dépôt local : index temporaire (`read-tree`, `hash-object -w`, `update-index --cacheinfo`, `write-tree`), `commit-tree` avec l'identité « Sacha Martin » et la date du setup (ou `date`), puis `update-ref` avec l'ancienne valeur attendue. Branche absente : elle part de `start` (branche d'`origin`), sinon commit racine. L'`element_id` rendu est `commit:<sha>`.
- Au `git pull`, le commit arrive dans le graphe local : `projections.ACTORS` reconnaît l'e-mail du collègue et le graphe porte `actor: colleague` (badge « Collègue », déjà rendu par `repo.js`). Le SHA est verrouillé par un test (`FIXED_SHA`), valable sur les trois OS : arbre en LF, identité et dates fixes.
- Réactions déclarées (AD-8) : op `colleague_reaction` (`trigger: pr_opened | checks_green`, `reviews` joués dans l'ordre, `author`, `head` facultatif). Elle écrit dans `github.json` (`reactions`, en ajout, valeur par défaut `[]`, sans nouvelle version de schéma).
- `github_sim` joue les réactions dues dans la même écriture que le recalcul des PR (`_commit`) : `pr_opened` une fois par PR, à l'ouverture ; `checks_green` une fois par `head_sha`, quand la PR a au moins un check obligatoire et que tous sont `success` (un nouveau push remet les checks à `queued` et réarme la réaction). Chaque revue porte auteur, `commit_sha` et `created_at` (heure réelle, ISO 8601 à la milliseconde). Les approbations et `mergeable` sont recalculés après les revues, et la PR figure dans `RefreshResult.updated` : `pr_updated` part par les chemins existants (`pr_open`, `refresh_after_command`).

## Registre d'ops et de réactions (pour 5.1)

- Une op = un module de `scenarios/ops/` avec `Args` (`op: Literal["<nom>"]`) et `apply(args, ctx) -> element_id` ; le registre découvre le module, aucune autre modification. Pour agir sur `origin` sous une identité fixe, 5.1 réutilise `ops/_origin.commit_on_origin(ctx, persona, branch, files, message, date, start)` (`persona` : `learner`, `colleague` ou `agent`) : `agent_commit` et `agent_push_force` n'ont qu'à l'appeler ou à s'en inspirer, avec `PERSONAS["agent"]`.
- Les réactions sont une liste ordonnée dans `github.json` ; un nouveau déclencheur s'ajoute à `ReactionTrigger` (`contracts/github.py`) et à `github_sim._react`. Un auteur `agent` est déjà accepté par `colleague_reaction`.
- `github_sim.set_check_state` est le point d'entrée qu'un pipeline simulé (`ci`) ou un test appelle pour changer l'état d'un check ; il recalcule les PR et joue les réactions.
- Clé YAML : le champ s'appelle `trigger` et non `on`, car YAML 1.1 lit `on` comme le booléen vrai.

## Décisions

- `created_at` et la liste vide `reactions` sont hors empreinte (`canonical_digest`) : l'heure d'une réaction est réelle et un état sans réaction garde l'empreinte d'avant la story. Les `fired` (déterministes) y restent.
- Le déclencheur « push » d'AD-8 n'est pas livré : seuls l'ouverture et les checks verts le sont (critères de la story).
- Le collègue ne réagit qu'aux PR ouvertes ; il n'écrit pas de commentaire sur une ligne (hors périmètre).

## Reports

- Vue Distant + PR (`review-log`, compteur) : story 3.3 ; les données (`reviews[].author`, `created_at`, `approvals`) sont prêtes.
- Réaction qui pousse un commit au déclenchement, déclencheur `push`, `closed` : plus tard si un scénario en a besoin.
- Pipeline simulé qui appelle `set_check_state` (ci, AD-10) : hors périmètre ; aucun scénario du catalogue ne déclare encore de réaction.

## Tests

`tests/test_colleague.py` : commit sur `origin` (identité, date, arbre conservé, local intact), `pull` et badge, SHA de référence, nouvelle branche et racine, refus (`start` absent, chemin hors dépôt, doublon), revues dans l'ordre avec heure et compteur, non-rejeu et filtre `head`, approbation automatique aux checks verts et réarmement après un push, absence d'approbation sur check en échec, empreinte indépendante de l'heure.
