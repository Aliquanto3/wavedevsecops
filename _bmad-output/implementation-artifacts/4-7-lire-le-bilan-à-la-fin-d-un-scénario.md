---
story: "4.7"
key: 4-7-lire-le-bilan-à-la-fin-d-un-scénario
title: Lire le bilan à la fin d'un scénario
status: review
branch: story/4-7-bilan-scenario
ad: [AD-14, AD-2, AD-1]
---

# Story 4.7 : Lire le bilan à la fin d'un scénario

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 4.7 ».

## Livré

- `progress/summary.py` : `build_summary(ScenarioProgress)` rend le bilan, textes écrits par le serveur (AD-2). Rien n'est écrit : tout vient des états dérivés de `progress.json` (`derive`, story 4.2), donc le bilan est identique après un redémarrage, et un Recommencer ne le change pas (le premier passage fait foi, FR-10).
- Moteur : `StepRunner(settings, progress)` ajoute la clé `summary` au panneau Scénario (`step_panel`) quand le scénario est terminé (`run.json` sans `step_id`), `None` avant. Le gestionnaire passe son `ProgressStore`. Un suivi illisible journalise et laisse `summary` à `None` (le panneau reste lisible).
- Scénario suivant : `summary.next` = `{scenario_id, mode, track, title_text}` du premier scénario du catalogue (ordre des identifiants) de même section, même mode et servant le même parcours, ou `None` (alors `next_none_text`).
- Front : `static/js/summary.js` (`scoreSummary`, `openNext`) ; `scenario.js` place le bilan sous la progression, annonce « Scénario terminé. n sur m du premier coup · k indice(s). » dans la région `role="status"`, et rend le focus aux boutons du bilan après redessin. Les vues et l'explication de la dernière étape restent consultables (rien n'est `inert`). « Scénario suivant » ouvre l'espace par `POST /api/open` (même parcours) puis y navigue ; « Catalogue » va à `/` ; « Recommencer » poste l'intention `restart`. Sans scénario suivant, le bouton est `aria-disabled` et un texte visible, relié par `aria-describedby`, dit pourquoi (UX-DR40).
- `store.js` : un `progress_updated` dont `facts` contient `scenario_completed` demande une relecture de l'état (`resync`) ; le bilan arrive ainsi par le même `step_panel` que celui d'une réouverture. Aucun calcul côté front.
- CSS : bloc `.score-summary*` ajouté à la fin de `workspace.css` (`number-lg` pour le score, `number` pour les indices).
- Tests : `test_summary.py` (accord 0/1/2 indices, gabarit, pas de bilan en cours, bilan lu dans `progress.json`, identique après redémarrage et après remise du pointeur, scénario suivant) ; `test_summary_dom.py` (Node : texte, trois actions, bouton inactif justifié, 0 indice, relecture à la fin).

## Contrat du bilan (pour 6.5, export du rapport)

`step_panel["summary"]` (aussi `build_summary(store.progress(track, scenario_id, mode))` hors panneau) :

| Clé | Sens |
|---|---|
| `quiz_correct`, `quiz_total` | premiers essais justes / posés (faits `quiz_first_attempt`) |
| `hints` | indices ouverts (faits `hint_opened`, un par palier et par étape) |
| `score_text`, `hints_text` | « 3 sur 4 du premier coup » ; « 0 indice », « 1 indice », « 2 indices » |
| `text` | « 3 sur 4 du premier coup · 1 indice » |
| `next`, `next_none_text` | scénario suivant ou `None`, et le texte du bouton inactif |

L'export peut relire les faits (`ProgressStore.all_progress()`) et reprendre `build_summary` : même gabarit, mêmes accords.

## Décisions

- Le bilan est calculé à chaque lecture de l'état plutôt que mémorisé : une seule source (AD-14), pas de cohérence à tenir. Coût : une lecture de `progress.json` par `GET .../state` d'un scénario terminé.
- Sans question dans le scénario, le score dit « Aucune question dans ce scénario » au lieu d'un « 0 sur 0 ».
- Le front relit l'état à la fin du scénario plutôt que de porter le bilan dans l'événement : un seul chemin de rendu, aucun texte inventé.
- Le suivant est cherché dans le même parcours : un scénario qui ne sert pas ce parcours est sauté.

## Reports

- Intention serveur `restart` : elle appartient à la story 4.4 (non fusionnée au moment de cette story). Le bouton « Recommencer » du bilan poste déjà `restart` comme l'encart d'échec de 4.5 ; la confirmation en ligne et « Scénario remis à zéro. » (UX-DR40) viennent avec 4.4.
- Indices (4.6) : le bilan compte déjà les faits `hint_opened` (4.2) ; aucun émetteur n'existe encore, le compte reste donc à 0 jusque-là. Aucun fait dupliqué.
- Désignations (5.2) : une désignation du premier coup doit entrer dans `quiz_total` / `quiz_correct`. `derive` ne compte aujourd'hui que `quiz_first_attempt` ; 5.2 émettra ce fait pour une désignation, ou étendra `derive` (une ligne).
- Classement du « suivant » : par identifiant ; un ordre éditorial (6.1) pourra remplacer `StepRunner._next_scenario`.
- Rendu réel (mise en page, lecteur d'écran, contraste dans les deux thèmes) à vérifier dans un navigateur ; les tests tournent sur la doublure de DOM.
