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
- Serveur : `web/glossary.py` (schéma pydantic strict, `GET /api/glossary`). Il résout la barrière (nom, station) et le scénario (titre depuis le catalogue). Fichier absent ou invalide : vocabulaire vide, journalisé. Jalon courant inchangé : `CURRENT_MILESTONE = "v0.1"` ; la surface « Vocabulaire » (déclarée v0.2 dans `shell.py`) reste masquée jusqu'à la release 9.5.
- Page Vocabulaire (`js/glossary.js`, `css/glossary.css`, branche dans `main.js`) : une entrée par terme, « Voir la barrière » (`aria-expanded`, `aria-controls`) déplie la barrière, sa station et « La voir jouer : scénario <nom> » en lien ; sans scénario livré, « Scénario à venir ». DAST porte « Nommé seulement » (tirets) et n'a ni bouton ni barrière. Traçabilité n'a pas de barrière : elle renvoie, en texte, aux PR et aux checks.
- `glossary-term` dans les explications : `[[id|texte]]` dans `explanations.yaml` devient un bouton souligné en pointillés qui ouvre la définition dans un popover (Échap, focus rendu au « i »). Posé sur `remote.check` (quality gate, secrets scanning) et `remote.review` (quatre yeux).
- « Voir la barrière » dans un espace : la carte de la chaîne s'enregistre (`registerBarrierShower`), s'ouvre sur la zone de la barrière et la sélectionne ; sans carte portant la barrière, le détail s'affiche dans le popover.
- Tests : `tests/test_glossary.py` (contenu, lint barrières, dégradation, 404/vide, route, rendu Node de la page, du terme et du renvoi) ; `test_shell_ui` vérifie le masquage en v0.1 et l'affichage en v0.2 (`create_app(milestone=…)`) ; `test_linking_dom` ouvre un terme depuis une explication.

## Décisions

- La barrière « dans l'état courant » est celle que la carte de l'espace ouvert porte : elle y est sélectionnée. Sur la page Vocabulaire (hors espace), il n'y a pas de carte : le détail se déplie sur place, avec le scénario en lien vers le catalogue (`/`).
- Jalon (décision de l'orchestrateur, revue) : la release v0.1.0 (6.7) est publiée depuis main avant 9.5, donc `CURRENT_MILESTONE` reste `"v0.1"` ici. **La story 9.5 doit passer `CURRENT_MILESTONE` à `"v0.2"`** (`web/shell.py`) et mettre à jour `test_surfaces_declarees_par_le_serveur` et `test_surface_non_livree_absente` (`/vocabulaire` sort de la liste masquée).

## Reports

- Barrières pas encore jouables, sans scénario (« Scénario à venir ») : SAST (`static-analysis`, bandit), SCA et SBOM (`dependencies`), quatre yeux (`human-review`), protection de branche (`branch-protection`). Renseigner `scenario_id` dans `glossary.yaml` quand les scénarios de l'Epic 7 et 8 sont livrés.
- Le lien du scénario mène au catalogue, pas à la carte du scénario (pas d'ancre dans le catalogue).
- Traçabilité : pas de lien actif vers les vues PR et checks (hors espace, elles n'existent pas).
- Scénarios de la Station 2 : `human-review` et `branch-protection` restent sans `scenario_id` ; à l'intégration de 7.5, renseigner `pr-sans-revue` (four-eyes) et `push-direct-main` (branch-protection) dans `glossary.yaml` (le test `test_chaque_scenario_du_vocabulaire_existe_au_catalogue` les vérifiera).
- « Voir la barrière » dans un espace sélectionne la barrière sur la carte, mais le détail de la carte ne montre pas « La voir jouer : scénario <nom> » (il vient de `chain.yaml`).
- À vérifier dans un navigateur : soulignement pointillé, popover au-dessus de la carte, lecture NVDA.

## Revue

Revue Opus, une passe, sur de7fe48 (base main 0b7f946, pas de rebase nécessaire).

- M · second avis 1 · corrigé · `CURRENT_MILESTONE` remis à `"v0.1"` (décision de l'orchestrateur) ; 9.5 fera le passage à v0.2.
- M · second avis 2 · corrigé · `test_shell_ui` rétabli (`/vocabulaire` absent en v0.1) et `test_vocabulaire_masque_en_v01_servi_en_v02` (instance réelle, `create_app(milestone=…)`).
- M · second avis 3 · reporté · traçabilité sans lien actif vers PR et checks : la page Vocabulaire est hors espace, et aucune explication ne cite le terme ; un lien demande une navigation vers la vue distante d'un espace ouvert (à faire avec la Fiche ou un `[[traceability|…]]` dans `remote.pr`).
- M · second avis 4 · corrigé · avertissement journalisé si `scenario_id` absent du catalogue, et test que chaque `scenario_id` existe au catalogue.
- L · second avis 5 · reporté · `pr-sans-revue` et `push-direct-main` (7.5, en revue) à renseigner à l'intégration (voir Reports).
- L · second avis 6 · corrigé · marques `[[…]]` mal formées (majuscules, sans `|`) détectées par le test des explications ; le schéma des termes impose déjà des identifiants en minuscules.
- L · second avis 7 · rejeté · `code` chevauchant un terme : aucun contenu ne le fait, et le cas reste lisible (accents graves affichés).
- L · second avis 8 · corrigé · l'espace appelle `chainView.destroy()` (désinscrit « Voir la barrière ») au lieu de `close` ; latent, `mountWorkspace` n'est pas démonté aujourd'hui.
- L · second avis 9 · corrigé en partie · `ui.trace_title`, jamais lu, retiré du contenu et du schéma ; `CLOSE_LABEL` (antérieur) et le texte de repli de la page sans vocabulaire sont gardés : ils servent quand le serveur ne répond pas.
- L · second avis 10 · corrigé · « Voir la barrière » du popover porte `aria-expanded` et `aria-controls`, le détail s'affiche dans une région `aria-live="polite"` (test Node dans `test_linking_dom`).
- L · revue · reporté · détail de la carte sans « La voir jouer : scénario » (voir Reports).
- Complexité : 0 constat (vocabulaire de taille fixe, résolution en O(termes + barrières)).

