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
- **Projection serveur** (`web/blockers.py`, `web/shell.py`) : `STATION_MILESTONES` déclare le jalon qui livre chaque station (1 à 3 : v0.2, 4 : v0.3), `station_delivered(station, milestone)`. `blockers_body` écrit l'encart : barrière non livrée = `soon_text` « Arrive en v0.2 », pas de scénario ; livrée = pas d'étiquette, `scenario` (id, titre du catalogue). Le jalon est celui de `create_app(milestone=...)` (`CURRENT_MILESTONE`, v0.1 aujourd'hui).
- **Moteur** (AD-1) : `StepRunner` et `WorkspaceManager` reçoivent un résolveur `blockers` (fourni par `web/app.py`) ; le panneau expose `blockers` quand le scénario est terminé, `None` sinon (aussi sans résolveur ou en cas d'erreur, journalisée). Aucun import du web par l'engine, aucun effet sur le score.
- **Front** (`scenario.js`, `workspace.css`, ajouts minimaux) : `blockersBlock` rend, après la correction et avant « Recommencer », une `step-explanation` à filet `discipline-harness` : par barrière, nom et station, phrase, puis lien (station livrée) ou étiquette en tirets (sinon). Aucun texte écrit côté front hors la structure.

## Décisions et reports

- **`content/barriers.yaml` n'existe pas** : le registre des barrières est `content/chain.yaml` (utilisé par le glossaire 9.4) ; le lint s'appuie sur lui.
- Deux sources de livraison coexistent : `delivered` de `chain.yaml` (bandeau, carte, « Bientôt ») et `STATION_MILESTONES` (encart, d'après la déclaration des jalons côté serveur). 9.5 doit passer `CURRENT_MILESTONE` à `v0.2` ; l'encart bascule alors seul en liens. À unifier si Anaël le souhaite.
- Jalon de la station 4 (v0.3) choisi faute de déclaration ; aucune barrière n'y est encore.
- Le lien du scénario mène au catalogue (`href="/"`, `data-scenario`), comme les liens du vocabulaire (9.4) ; l'ouverture directe du scénario reste à faire avec 9.3.
- Contrôle dans un navigateur réel pour Anaël : fin du scénario `.env`, mise en page de l'encart.

## Tests

`tests/test_blockers.py` : schéma, lint (barrière, station, scénario, doublon), déclarations des quatre B, projection en jalon v0.1 (étiquette, sans lien) et v0.2 (lien, sans étiquette) par paramètre, résolveur du panneau et sa défaillance, rendu sous Node (lien ou étiquette, absence d'encart). Empreintes inchangées (`tests/test_fingerprints.py`).
