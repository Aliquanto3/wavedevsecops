---
story: "9.4"
key: 9-4-relier-chaque-terme-du-vocabulaire-à-sa-barrière
title: Relier chaque terme du vocabulaire à sa barrière
status: review
branch: story/9-4-vocabulaire-barrieres
ad: [AD-2, AD-7]
---

# Story 9.4 : Relier chaque terme du vocabulaire à sa barrière

Source : `epics.md`, section « Story 9.4 » ; FR-33, UX-DR33 ; `EXPERIENCE.md` (Vocabulaire) ; reports des specs 2-10 (`barrier_id`) et 9-2 (cibles des liens).

## Livré

- Contenu (AD-2, AD-7) : `content/glossary.yaml` (textes de la page et neuf termes : secrets scanning, SAST, SCA, SBOM, quality gate, quatre yeux, protection de branche, traçabilité, DAST), défini en deux phrases chacun. `barrier_id` pointe une barrière de `content/chain.yaml` (test de lint), `scenario_id` le scénario qui la joue. `chain.yaml` gagne deux barrières de la Station 2 (`human-review`, `branch-protection`) pour quatre yeux et protection de branche.
- Serveur : `web/glossary.py` (schéma pydantic strict, `GET /api/glossary`). Il résout la barrière (nom, station) et le scénario (titre depuis le catalogue). Fichier absent ou invalide : vocabulaire vide, journalisé. Jalon courant : `CURRENT_MILESTONE = "v0.2"`, ce qui livre la surface « Vocabulaire » de l'en-tête (déclarée v0.2 dans `shell.py`).
- Page Vocabulaire (`js/glossary.js`, `css/glossary.css`, branche dans `main.js`) : une entrée par terme, « Voir la barrière » (`aria-expanded`, `aria-controls`) déplie la barrière, sa station et « La voir jouer : scénario <nom> » en lien ; sans scénario livré, « Scénario à venir ». DAST porte « Nommé seulement » (tirets) et n'a ni bouton ni barrière. Traçabilité n'a pas de barrière : elle renvoie, en texte, aux PR et aux checks.
- `glossary-term` dans les explications : `[[id|texte]]` dans `explanations.yaml` devient un bouton souligné en pointillés qui ouvre la définition dans un popover (Échap, focus rendu au « i »). Posé sur `remote.check` (quality gate, secrets scanning) et `remote.review` (quatre yeux).
- « Voir la barrière » dans un espace : la carte de la chaîne s'enregistre (`registerBarrierShower`), s'ouvre sur la zone de la barrière et la sélectionne ; sans carte portant la barrière, le détail s'affiche dans le popover.
- Tests : `tests/test_glossary.py` (contenu, lint barrières, dégradation, 404/vide, route, rendu Node de la page, du terme et du renvoi) ; `test_shell_ui` suit le jalon v0.2.

## Décisions

- La barrière « dans l'état courant » est celle que la carte de l'espace ouvert porte : elle y est sélectionnée. Sur la page Vocabulaire (hors espace), il n'y a pas de carte : le détail se déplie sur place, avec le scénario en lien vers le catalogue (`/`).
- Passage à `CURRENT_MILESTONE = "v0.2"` dans cette story, faute de quoi la page n'est pas accessible ; la release 9.5 ne touche donc que `pyproject.toml` et le tag.

## Reports

- Barrières pas encore jouables, sans scénario (« Scénario à venir ») : SAST (`static-analysis`, bandit), SCA et SBOM (`dependencies`), quatre yeux (`human-review`), protection de branche (`branch-protection`). Renseigner `scenario_id` dans `glossary.yaml` quand les scénarios de l'Epic 7 et 8 sont livrés.
- Le lien du scénario mène au catalogue, pas à la carte du scénario (pas d'ancre dans le catalogue).
- Traçabilité : pas de lien actif vers les vues PR et checks (hors espace, elles n'existent pas).
- À vérifier dans un navigateur : soulignement pointillé, popover au-dessus de la carte, lecture NVDA.
