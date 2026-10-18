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

- Une op = un module de `scenarios/ops/` avec `Args` (`op: Literal["<nom>"]`) et `apply(args, ctx) -> element_id` ; le registre découvre le module, aucune autre modification. Pour agir sur `origin` sous une identité fixe, 5.1 réutilise `ops/_origin.commit_on_origin(ctx, persona, branch, files, message, date, start)` (`persona` : `learner`, `colleague` ou `agent`) : `agent_commit` n'a qu'à l'appeler avec `PERSONAS["agent"]`. `agent_push_force` ne peut pas l'appeler tel quel : sur une branche existante, le parent est toujours son sommet (`start` ne sert qu'à une branche absente), donc le commit est toujours fast-forward ; 5.1 devra ajouter un parent explicite (et un `update-ref` qui accepte la réécriture).
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
- Pipeline simulé qui appelle `set_check_state` (ci, AD-10), depuis la file de l'espace (AR-2) : hors périmètre ; aucun scénario du catalogue ne déclare encore de réaction.

## Tests

`tests/test_colleague.py` : commit sur `origin` (identité, date, arbre conservé, local intact), `pull` et badge, SHA de référence, nouvelle branche et racine, refus (`start` absent, chemin hors dépôt, doublon), revues dans l'ordre avec heure et compteur, non-rejeu et filtre `head`, approbation automatique aux checks verts et réarmement après un push, absence d'approbation sur check en échec, empreinte indépendante de l'heure.

## Revue

Revue Opus (une passe), après rebase sur `origin/main` (4.5). Complexité : 0 constat (`_react` parcourt réactions × PR à chaque écriture, tailles de quelques unités).

- low · second avis M1 · corrigé (spec) · `commit_on_origin` ignore `start` sur une branche existante, ce qui est le comportement documenté pour 3.4 ; seule l'affirmation « `agent_push_force` n'a qu'à l'appeler » était fausse : le registre précise maintenant que 5.1 devra ajouter un parent explicite. Pas de code spéculatif pour 5.1.
- low · second avis L2 · rejeté · `add_reaction` et `set_check_state` suivent le même schéma load/_commit que `set_protection` et `open_pr` : l'exclusion vient de l'appelant (setup, ou intention dans la file). `add_reaction` n'est appelé que par le setup ; le pipeline 7.4 devra appeler `set_check_state` depuis la file (noté dans les reports).
- low · second avis L3 · confirmé · le job `ruff + pytest` de la CI tourne sur windows, macos et ubuntu et exécute `tests/test_colleague.py` (`FIXED_SHA`) ; l'arbre est écrit en LF et `gitio` force `core.autocrlf=false`.
- low · second avis L4 · corrigé · test `test_empreinte_d_un_github_json_d_avant_la_3_4_inchangee` : un `github.json` sans `reactions` garde une empreinte de référence écrite en dur.
- info · revue · rejeté · critère 3 (checks verts) joignable seulement par `set_check_state` (tests) ou des checks déclarés `success` à l'ouverture tant que le pipeline simulé n'existe pas : report déjà consigné (AD-10, 7.4).
