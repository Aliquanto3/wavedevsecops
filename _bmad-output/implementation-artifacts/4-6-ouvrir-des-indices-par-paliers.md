---
story: "4.6"
key: 4-6-ouvrir-des-indices-par-paliers
title: Ouvrir des indices par paliers
status: review
branch: story/4-6-indices-paliers
ad: [AD-2, AD-7, AD-14, AD-17]
---

# Story 4.6 : Ouvrir des indices par paliers

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 4.6 » ; FR-13, UX-DR28, décision « délais chiffrés » (solution après un essai ou 20 s sur la commande partielle). S'appuie sur la validation d'étape de la 4.1, le magasin de faits de la 4.2 (le fait `hint_opened` y attendait son émetteur) et le panneau du quiz de la 4.5. La 6.2 s'appuiera sur ces paliers.

## Livré

- **Contenu** (`scenarios/steps/_base.py`) : toute étape peut porter `hints: {lead_text, partial_text, solution_text}` (les trois paliers d'AD-7 ; les blancs de la commande partielle s'écrivent `___`). Absent : l'étape n'a pas d'indice. Lint : avertissement (`Scenario.authoring_warnings`) si la commande partielle n'a aucun blanc.
- **Intention `hint_open {tier}`** (`engine/hints.py`, enregistrée par `web/app.py`). Refus à la réception (409, condition en clair) d'un palier verrouillé ou d'une étape sans indice ; opération `writes=False` (admise en `quiz_altered`), `validate=False`, avec `precheck` dans la file (étape changée, palier déjà ouvert : abandon sans bruit, donc rouvrir ne compte pas deux fois). Elle écrit `run.json`, puis publie `hint_opened{step_id, tier}`.
- **Disponibilité calculée par le serveur (AD-2)** : piste toujours ; commande partielle après la piste ; solution après la commande partielle **et** (un essai sur l'étape ou 20 s depuis l'ouverture de la commande partielle). Le panneau (`engine/steps.py`) donne à l'étape courante `hints{tiers[{tier, label_text, state: open|available|locked, text (ouvert seulement), condition_text (verrouillé)}], solution_unlock_ms, unlocked_text}` et, au niveau du panneau, `has_hints`. Le texte d'un palier fermé n'est jamais envoyé ; aucun compteur n'existe côté serveur ni côté front.
- **Essais** : `terminal_line`, `quiz_choice` et `answer_submit` comptent (`run.json.hints[step].attempts`), incrémentés par `StepRunner.validate` avant le verdict. Début d'étape (`since`) : écrit par `prepare_workspace` (étape 1), par `validate` à chaque réussite (étape suivante) et, pour un espace antérieur, au réveil (`replay`).
- **Faits du premier passage (AD-14)** : `hint_opened{tier, delay_ms, read_ms}`. `delay_ms` = temps entre le début de l'étape et la demande ; `read_ms` = temps entre l'ouverture et l'action suivante (autre palier, commande, choix, changement extérieur, validation). Le fait n'est donc soumis qu'à cette clôture (`run.json.hint_pending` désigne le palier en lecture) ; `run.json` est écrit d'abord, `replay` rejoue les paliers clos après un arrêt brutal, et le magasin garde un fait par palier et par étape. Nouvelle méthode `OpContext.submit_facts` (moteur) pour une opération qui produit des faits hors d'un verdict.
- **Front** (`web/static/js/hints.js`, `scenario.js`, `store.js`, `workspace.css`) : `hint-tabs` en `role="tablist"` / `tab` / `tabpanel`, flèches Début/Fin, onglet verrouillé = cadenas + condition visible + `aria-disabled="true"` mais focalisable ; clic sur un onglet disponible poste `hint_open`, sur un onglet ouvert l'affiche, sur un verrouillé ne fait rien. Commande partielle avec blancs et solution en texte sélectionnable, sans Copier ni Exécuter. L'encart « État inattendu » propose « Ouvrir un indice » (premier palier non ouvert ; inactif avec sa condition s'il est verrouillé, absent quand les trois sont ouverts). Le front relit le panneau (`GET …/state`, `store.setStepPanel`) après `hint_opened`, après une étape réussie (indices de la suivante) et en fin d'action quand la solution attend ; une minuterie locale (`solution_unlock_ms`, sans décompte) relit le panneau au moment du déblocage ; le passage verrouillé -> disponible est annoncé par le serveur (« La solution est disponible. ») dans la région `role="status"`.
- Tests : `tests/test_hints.py` (vrai git : panneau, ordre des paliers, refus 409 avec condition, solution après un essai ou 20 s à la seconde près, rouvrir sans double compte, fait avec palier / délai / lecture, clôture par validation, rejeu, étape sans indice, lint) ; `tests/test_hints_dom.py` (Node : rôles, cadenas, `aria-disabled`, flèches, clic, texte sélectionnable, encart, annonce, relecture et minuterie).

## Décisions

- Le front ne mesure rien et ne décide de rien : les deux temps et la règle des 20 s viennent de l'horloge du serveur (`hints.clock`, remplaçable par les tests).
- Le fait est soumis à la clôture de la lecture et non à l'ouverture : un fait n'est jamais modifié (le magasin est en ajout seulement), et l'AC demande le temps de lecture dans le fait. Conséquence : un palier encore en lecture au moment où l'apprenant quitte l'application ne devient un fait qu'à sa prochaine action (jamais perdu : `hint_pending` survit dans `run.json`).
- `hint_open` passe par l'état `command` (texte « Ouverture de l'indice. »), comme tout ce qui s'exécute dans la file ; il n'émet pas de `state_projected` utile mais la file en publie un, sans effet sur les vues.
- Les trois paliers vivent sur `StepArgs` (tous les types d'étape), pas dans un type : l'API des types d'étape et le chargeur ne changent pas.

## Reports

- Aucun scénario de `content/scenarios/` ne déclare encore `hints` : les contenus viennent avec les scénarios des épics suivants (6.2 s'appuie sur le panneau).
- Le bilan (nombre d'indices, 4.7) lit `ProgressScenario.hints`, déjà dérivé des faits ; « Recommencer » (4.4) reconstruit `run.json`, donc remet à zéro les paliers ouverts et les essais, sans toucher aux faits.
- `answer_submit` (5.2) est déjà dans les intentions qui comptent comme un essai ; son émetteur arrive avec la 5.2.
- Rendu visuel (cadenas, focus, annonce lecteur d'écran) à vérifier dans un navigateur : les tests tournent sur une doublure de DOM.
