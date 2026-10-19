---
story: "5.9"
key: 5-9-encart-ce-qui-l-aurait-bloqué-dans-les-scénarios-b
title: Encart « Ce qui l'aurait bloqué » dans les scénarios B
status: review
branch: story/5-9-encart-barrieres
ad: [AD-7, AD-17, AD-2]
---

# Story 5.9 : Encart « Ce qui l'aurait bloqué » dans les scénarios B

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.9 » ; FR-12, UX-DR8 (variante « Ce qui l'aurait bloqué »). Arbitrage : cette story livre l'encart ; 9.3 ne fait que retirer l'étiquette et lier le scénario.

## Livré

- **Schéma** (`scenarios/model.py`) : champ optionnel `blocked_by` (liste de `Blocker` : `barrier_id`, `station`, `scenario_id`, `reason_text`). Vide par défaut : un scénario sans liste reste valide.
- **Lint de contenu** : `parse_scenario` / `load_scenario` acceptent `barriers` (barrière -> station de la chaîne) et `scenario_ids` (catalogue). Refus d'une barrière inconnue, d'une station qui n'est pas celle de la chaîne, d'un scénario absent du catalogue, d'un doublon. Sans ces paramètres, pas de vérification (comme `explain_keys`). `web/blockers.py` fournit `chain_barriers` et `catalogue_scenario_titles`.
- **Déclarations** :
  - `add-commit.B` : `secret-scan` (Station 1 · Poste local, gitleaks), joué par `secret-dans-un-commit`.
  - `push-pull.B` : `protection` (Station 2 · PR et CI, protection de `main`), joué par `push-direct-main`.
  - `stash.B` et `rebase.B` : rien. Aucune barrière de `chain.yaml` (secret, lint, tests, couverture, revue, protection, SAST, dépendances) ne protège d'un stash oublié ni d'un rebase laissé en conflit ; un commentaire en tête de fichier le dit.
- **Projection serveur** (`web/blockers.py`) : `blockers_body` écrit l'encart d'après `content/chain.yaml`, seule source de livraison des stations (revue, voir plus bas) : station `delivered: false` = `soon_text` « Arrive en <milestone> » (jalon déclaré par la station, « Bientôt » à défaut), pas de scénario ; livrée = pas d'étiquette, `scenario` (id, titre du catalogue).
- **Moteur** (AD-1) : `StepRunner` et `WorkspaceManager` reçoivent un résolveur `blockers` (fourni par `web/app.py`) ; le panneau expose `blockers` quand le scénario est terminé, `None` sinon (aussi sans résolveur ou en cas d'erreur, journalisée). Aucun import du web par l'engine, aucun effet sur le score.
- **Front** (`scenario.js`, `workspace.css`, ajouts minimaux) : `blockersBlock` rend, après la correction et avant « Recommencer », une `step-explanation` à filet `discipline-harness` : par barrière, nom et station, phrase, puis lien (station livrée) ou étiquette en tirets (sinon). Aucun texte écrit côté front hors la structure.

## Décisions et reports

- **`content/barriers.yaml` n'existe pas** : le registre des barrières est `content/chain.yaml` (utilisé par le glossaire 9.4) ; le lint s'appuie sur lui.
- Jalon de la station 4 (v0.3) choisi faute de déclaration ; aucune barrière n'y est encore.
- Le lien du scénario mène au catalogue (`href="/"`, `data-scenario`), comme les liens du vocabulaire (9.4) ; l'ouverture directe du scénario reste à faire avec 9.3.
- Contrôle dans un navigateur réel pour Anaël : fin du scénario `.env`, mise en page de l'encart.

## Tests

`tests/test_blockers.py` : schéma, lint (barrière, station, scénario, doublon), déclarations des quatre B, projection sur le contenu réel (stations 1 et 2 livrées : liens) et sur une chaîne modifiée (station non livrée : « Arrive en v0.2 » ou « Bientôt », sans lien), cache de l'encart, résolveur du panneau et sa défaillance, rendu sous Node (lien ou étiquette, absence d'encart). Empreintes inchangées (`tests/test_fingerprints.py`).

## Revue

Revue Opus du 2026-10-19, rebasée sur main 1e46ded.

**Décision d'unification (à confirmer par Anaël)** : une seule source dit si une station est livrée, `delivered` de `content/chain.yaml`, déjà lue par le bandeau, la carte et le glossaire. `STATION_MILESTONES` et `station_delivered` sont retirés de `web/shell.py` ; le champ facultatif `milestone` d'une station (`ChainStation`) ne sert qu'au texte « Arrive en <milestone> » d'une station non livrée (station 4 : `v0.3`). Conforme aux arbitrages du 2026-10-19 (stations en aperçu dans la v0.1.0, station 1 livrée) : à v0.1 l'encart montre déjà un lien pour gitleaks et la protection de `main`, comme le bandeau. Conséquences : 9.5 n'a rien à faire pour l'encart (le passage de `CURRENT_MILESTONE` à v0.2 ne concerne que les surfaces de l'en-tête) ; 9.3 n'a plus d'étiquette à retirer pour les stations 1 à 3, seulement le lien direct vers le scénario. L'étiquette « Arrive en v0.2 » des critères ne s'affiche donc aujourd'hui pour aucune barrière déclarée ; elle reste testée sur une chaîne modifiée.

| Sévérité | Source | Constat | Suite | Motif |
|---|---|---|---|---|
| medium | second avis 1 | Deux sources de livraison contradictoires (chain.yaml `delivered: true`, `STATION_MILESTONES` v0.2) : « Arrive en v0.2 » sur la station 1 que le bandeau montre livrée | corrigé | unification sur `chain.yaml` (ci-dessus) |
| medium | revue (complexité) | Le panneau est recalculé à chaque `GET /state` ; une fois le scénario B fini, `blockers_body` relisait `chain.yaml`, le registre et tous les scénarios (~140 ms mesurés) à chaque appel | corrigé | cache dans `StepRunner._blockers_of`, recalcul seulement quand le scénario est relu (fichier modifié) ; test `test_l_encart_est_calcule_une_fois_par_lecture_du_scenario` |
| low | second avis 2 | Docstring « scénario (mode A) » alors que le lint accepte un id B | corrigé | docstring : « mode A en pratique » ; le lint vérifie l'existence au catalogue, pas le mode |
| low | second avis 3 | Scénario cité non chargeable avalé sans log : barrière sans lien ni étiquette | corrigé | avertissement journalisé au chargement et quand une station livrée n'a pas de titre de scénario |
| low | second avis 4 | Pas de cache dans `blockers_body` | corrigé | même correctif que le constat de complexité |
| low | second avis 5 | Lint `blocked_by` opt-in, exercé par les tests seulement | rejeté | même modèle que `explain_keys` (vérifié par les tests de contenu, pas au chargement) ; `test_declarations_des_scenarios_b` lint tous les fichiers de `content/scenarios/` contre la chaîne et le catalogue |
| low | second avis 6 | Lien `href="/"` sans gestionnaire | rejeté | décision documentée : mène au catalogue comme les liens du vocabulaire (9.4) ; ouverture directe du scénario avec 9.3 |
| — | report | Contrôle visuel de l'encart dans un navigateur réel (fin du scénario `.env`) | reporté | à faire par Anaël : finir `add-commit.B`, vérifier l'encart après la correction et le lien vers le catalogue |
