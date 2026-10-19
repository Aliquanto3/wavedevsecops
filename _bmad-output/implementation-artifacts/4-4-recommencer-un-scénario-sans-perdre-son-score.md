---
story: "4.4"
key: 4-4-recommencer-un-scénario-sans-perdre-son-score
title: Recommencer un scénario sans perdre son score
status: review
branch: story/4-4-recommencer
ad: [AD-1, AD-6, AD-14, AD-20]
---

# Story 4.4 : Recommencer un scénario sans perdre son score

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 4.4 » ; FR-10, UX-DR40 ; spine AD-1, AD-6, AD-14, AD-20. S'appuie sur les instantanés de la 4.3, le magasin de faits de la 4.2 et les reports des stories 4.5 (quiz), 4.6 (indices), 4.7 (bilan) et 5.2 (désignation).

## Livré

- **Intention `restart {}`** (`engine/restart.py`, enregistrée par `web/app.py`). Opération de la file en état `restoring` (surveillant arrêté, `epoch` incrémenté), déjà exemptée des refus `restore_failed` et `quiz_altered` par `_write_refusal` (4.5). Dans l'ordre : `hints.settle(ctx)` (le palier en lecture devient un fait **avant** de refaire `run.json`, report de la 4.6) ; `run.json` refait par `workspace.initial_run` (étape 1 ; paliers, essais, `hint_pending`, `answers`, `validated`, `quiz`, `quiz_first`, `restore_failed` à zéro) ; retour à l'**instantané 0** (`restore_snapshot`, empreinte vérifiée contre celle du manifeste, AD-6) ; `ctx.set_rest_state("idle")` (sortie de `quiz_altered`, report de la 4.5). `run.json` est refait avant la copie : un arrêt en plein milieu est repris par la reprise de la 4.3 sur un `run.json` déjà remis à zéro.
- **Reconstruction par le setup** quand l'instantané 0 manque, quand sa restauration échoue (`RestoreFailed` ou erreur imprévue) ou quand le `content_hash` du scénario n'est plus celui de `run.json` : `prepare_workspace(replace=True)`, puis comparaison de l'empreinte à `content/fingerprints.json` (clé `<parcours>/<scenario_id>.<mode>` ; fichier ou clé absents : pas de comparaison). Un écart, ou une reconstruction impossible, donne un `app_error` « … » + « Voir le diagnostic, puis recommencez le scénario. » ; l'écart pose aussi `restore_failed` dans `run.json` (seule « Recommencer » reste admise). L'identité de l'espace vient de `workspace_id`, pas de `run.json` : un `run.json` illisible se reconstruit.
- **Faits conservés** : le fait `scenario_reset` (nouveau `FactKind`, identité = `op_id` : un par remise à zéro) s'ajoute à `progress.json` après `run.json` ; aucun autre fait n'est touché, donc le score du premier coup et les indices restent ceux du premier passage. `derive` ignore ce fait : une remise à zéro ne fait pas passer un scénario « À faire » à « En cours ». L'événement `progress_updated` porte `facts: ["scenario_reset"]`.
- **`workspace.initial_run`** : le dictionnaire de `run.json` d'un espace neuf, partagé par le setup et par Recommencer ; `run.json` garde désormais `step_ids` (liste ordonnée des étapes).
- **Contenu modifié (AD-20)** : le panneau porte `content_changed: {text} | null`. Il est posé quand le `content_hash` du fichier diffère de `run.json` **et** que la liste des étapes a changé (`step_ids`, ou à défaut une étape citée par `run.json` qui n'existe plus) : une retouche de texte ne dérange pas l'apprenant. Le front montre l'encart « Scénario mis à jour » avec « Recommencer ».
- **Front** (`static/js/restart.js`, `scenario.js`, `store.js`, `quiz.js`, `workspace.js`, `workspace.css`) : « Recommencer » dans le pied du panneau (`.restart-foot`, après l'explication) ; un clic ouvre la confirmation en ligne « Remettre le scénario à son état initial ? Votre score du premier coup est conservé. » (`role="group"`, focus sur « Annuler », « Remettre à zéro » envoie `restart`). Le bouton du bilan (4.7), celui de l'encart « État inattendu » et celui de « Scénario mis à jour » ouvrent la même confirmation. Le bouton de l'encart d'échec de la 4.5 reste direct (l'état est déjà faux). Après la remise à zéro : annonce « Scénario remis à zéro. » dans la région `role="status"`, focus sur la consigne, verdict effacé, panneau relu (étape 1, plus de bilan). Pendant l'opération : « Remise à zéro du scénario… » (au lieu du texte du rétablissement). Une erreur de l'espace affiche un lien « Voir le diagnostic ».
- **Bilan** (constat L6 de la 4.7) : `store.js` relit le panneau sur `scenario_reset` ; il le relit aussi sur un `step_verdict` réussi sans étape suivante, car la seconde fin d'un scénario n'ajoute aucun fait (le premier passage fait foi) et ne déclencherait pas la relecture par `scenario_completed`. Le bilan du second passage est identique à celui du premier.
- Tests : `tests/test_restart.py` (vrai git : empreinte de l'instantané 0 et étape 1 ; sortie de `restore_failed` et de `quiz_altered` ; instantané 0 corrompu ; indices clos avant la reconstruction et remis à zéro ; `answers` vidées ; faits conservés et score inchangé après un second passage ; un fait par remise à zéro ; bilan absent puis identique ; reconstruction comparée à la référence, écart, scénario disparu ; contenu incompatible puis retouche de texte ; enregistrement par l'application) ; `tests/test_restart_dom.py` (Node : pied et confirmation, annonce et focus, relecture du panneau et bilan, encarts, lien du diagnostic). Réalignés : `tests/test_summary_dom.py` (le bouton du bilan demande confirmation), `tests/test_scenario_panel_dom.py` (pied du panneau et lien d'erreur dans l'ordre des nœuds).

## Décisions

- L'opération passe par l'état `restoring` et non `setup` : le surveillant est arrêté (Windows), l'`epoch` change (une opération produite avant est périmée) et le front a déjà son traitement (vues `inert`).
- L'instantané 0 est préféré à la reconstruction tant que le `content_hash` n'a pas changé : c'est la restauration exacte de la 4.3, vérifiée par empreinte, et elle ne refait pas le setup. Les instantanés suivants (quiz) restent sur disque jusqu'à la rétention ; plus aucun `run.json` ne les cite.
- Le texte « Scénario remis à zéro. » est un libellé fixe du front (comme « Rétabli. » de la 4.5), annoncé à la réception du fait ; le serveur écrit le texte de la confirmation d'échec et de l'encart de contenu.
- Pas de `restore_started` / `restore_ended` : Recommencer n'est pas un rétablissement marqué (`restored`), les vues ne montrent pas « Rétabli ».
- Les faits `hint_opened` d'un premier passage restent seuls comptés : après Recommencer, rouvrir un palier ne crée pas de second fait (identité par palier et par étape).

## Reports

- Le fait `scenario_reset` n'est pas rejoué au réveil (`replay`) : un arrêt brutal entre l'écriture de `run.json` et la soumission perd ce fait, sans effet sur le score. À rejouer si un compte de remises à zéro apparaît dans le bilan ou l'export (6.5).
- Le terminal garde ses sorties d'avant la remise à zéro (seul le front les efface par Ctrl+L) ; à décider avec les prochaines stories du terminal.
- Reconstruction impossible (`prepare_workspace` en échec) : l'espace est supprimé par `prepare_workspace` et l'erreur affichée ; la réouverture depuis le catalogue le recrée. Pas de relance automatique.
- Rendu réel (focus, annonce du lecteur d'écran, thème sombre du pied du panneau) à vérifier dans un navigateur ; les tests tournent sur la doublure de DOM.
- AD-14 (spine) liste les faits du premier passage : y ajouter `scenario_reset` (décision pour Anaël).

## Revue

À faire (second avis, puis reviewer).
