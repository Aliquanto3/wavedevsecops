---
story: "5.6"
key: 5-6-le-scénario-b-env-committé
title: Le scénario B « .env committé »
status: review
branch: story/5-6-scenario-b-env
ad: [AD-7, AD-18]
---

# Story 5.6 : Le scénario B « `.env` committé »

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.6 » ; FR-12, UJ-2, UX-DR8. S'appuie sur les actes de l'agent B (5.1), la désignation (5.2, 5.3, 5.5) et le format des scénarios (6.2).

## Livré

`content/scenarios/add-commit.B.yaml`, `tracks: [llm, no_ai]`, même setup pour les deux parcours (empreinte `4056f1bb…`, stable sur deux générations).

- Setup : l'état propre de l'apprenant (README, `bonjour.py`, poussés), puis deux commits de l'agent B : « Ajoute le client de l'API » (`src/client.py`) et « Ajoute la configuration de l'API » (`.env`, avec `API_KEY=cle-factice-…`). Rien n'est poussé : la clé n'a pas quitté le poste, on répare par une réécriture locale.
- Étape `designer` (`designate`, question « Qu'a fait l'agent ? ») : accepte `commit`, `path`, `diffline`. Bonnes réponses : le commit (principal, donc aussi son SHA une fois résolu), `path:head:.env`, la ligne `API_KEY=` (`diffline:<sha>:.env:new:1`). Une réponse fausse (l'autre commit) est corrigée comme à l'ordinaire et ferme l'étape.
- Étape `retirer_de_l_historique` (nouveau type `history_clean`) : validée dès qu'aucun commit accessible depuis une ref (branche, tag, distant, stash) n'ajoute ou ne modifie `.env`, et que `.gitignore` l'ignore. Quelle que soit la suite de commandes (`reset --soft` ou `--hard`, `rebase`, `filter-branch`…). Raisons d'échec écrites par le serveur : historique encore contaminé (avec les commits cités), ou fichier retiré mais non ignoré.
- Trois paliers d'indice par étape ; le premier ne donne pas la réponse. Vouvoiement.

## Ajouts localisés au code partagé

- Op de setup `diff_line` (module seul, découverte automatique) : produit l'alias d'une ligne de diff d'un commit (`@commit`, `path`, `line`, `side`, `contains` pour vérifier le contenu). Les SHA n'étant connus qu'à l'exécution, c'est le moyen de citer un `diffline` en bonne réponse.
- Type d'étape `history_clean` (module seul). `RepoState` ne détaille pas le contenu des commits : l'étape interroge git en lecture seule (`git log --all --diff-filter=AMRC -- :(literal).env`, `git check-ignore --no-index`).
- `StepContext.git` : fabrique facultative du `Git` de l'espace, renseignée par `StepRunner` (`engine/steps.py`) ; résolue seulement si un type l'appelle.

## Reports

- Encart « Ce qui l'aurait bloqué » (gitleaks, station 1, étiquette « Arrive en v0.2 ») : stories 8.x, comme le dit la spec 9-3 ; le catalogue ne le porte pas encore.
- Vues Code et terminal : la désignation d'une ligne de diff ou d'un fichier de commit suppose leur marquage `data-designable` par la vue Code (reports 5.3 et 5.5) ; le test couvre la correction côté serveur, pas le clic dans ces vues.
- Cas non couvert : un commit qui contiendrait `.env` sans jamais l'ajouter ni le modifier (impossible dans un dépôt cohérent) ; un `.env` renommé en un autre nom n'est pas suivi.
- Contrôles dans un navigateur réel pour Anaël : lecture de l'étape de désignation avec la vue Code d'un commit.

## Tests

`tests/test_scenario_b_env.py` : lint du contenu (paliers, vouvoiement), setup dans les deux parcours (deux commits d'agent, `.env` ajouté, `origin` intact), désignation juste par le commit, le fichier, la ligne et le SHA résolu, désignation fausse (premier essai consigné), réparation (solution à cinq commandes, `reset --hard`, suppression dans un nouveau commit refusée, `--amend` refusé, fichier non ignoré signalé, branche de sauvegarde qui garde le fichier, lecture seule silencieuse). Empreintes : `tests/test_fingerprints.py`.
