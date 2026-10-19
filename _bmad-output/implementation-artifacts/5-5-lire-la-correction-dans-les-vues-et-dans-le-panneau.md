---
story: "5.5"
key: 5-5-lire-la-correction-dans-les-vues-et-dans-le-panneau
title: Lire la correction dans les vues et dans le panneau
status: review
branch: story/5-5-lire-correction
ad: [AD-2, AD-1, AD-17]
---

# Story 5.5 : Lire la correction dans les vues et dans le panneau

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.5 » ; contrat serveur : spec 5.2 ; front de désignation : spec 5.3.

## Livré

- **Serveur** (ajouts localisés) : `SlotMark` (`answer_corrected`) porte deux champs optionnels, `label_text` (intitulé de la case) et `element_texts` (un nom en mots, écrit par le serveur, pour le choix, l'attendu et chaque équivalent, par `describe`). `StepRunner.panel` joint `correction` (la charge de `run.json["answers"][step_id]["payload"]`, même forme que l'événement) à toute étape de désignation terminée qui a une réponse consignée : c'est la reprise après un rechargement ou une réouverture. Une remise à zéro de `answers` (Recommencer, 4.4) la retire d'elle-même.
- `web/static/js/correction.js` (nouveau) :
  - `marksOf(correction)` : par élément, ses marques (choix juste « ✓ Votre choix » ou faux « ✗ Votre choix », principal « ✓ Attendu », équivalents « ≡ Accepté aussi »). Un même élément peut en porter deux (choix juste et attendu, ou choix équivalent). Le front ne décide jamais de ce qui est juste : il lit `correct`, `expected_element_id` et `accepted_element_ids` du serveur.
  - `markCorrection(root, designation)` : même contrat que `markDesignated` (tout nœud `[data-designable]` portant `data-element-id` ou `data-designate-id`). Pose la classe `has-verdict` (+ `is-verdict-right|wrong|expected`) et un `span.verdict-mark` à droite de la rangée, et ajoute la marque au nom accessible (`aria-label` + « — ✗ Votre choix »), restitué quand la marque disparaît. Idempotente, appelée après chaque dessin d'une vue.
  - `correctionBlock(step, {onSelect, onContinue, onRestart})` : `step-explanation` variante correction. Ordre fixe (AD-1) : titre « Correction », résumé du serveur, une case `answer-slot is-validated` par case (« <intitulé> · validée », choix et sa marque, **sans ✕**, phrase du serveur, liste « ✓ Attendu » puis « ≡ Accepté aussi », chacun avec « voir dans les vues » qui sélectionne l'élément, que la réponse soit juste ou non), puis l'explication de l'étape, puis « Continuer » et « Recommencer ».
- `designation.js` : `designation.correction` et `setCorrection` (comparaison par contenu, notification aux vues).
- `store.js` : l'événement `answer_corrected` joint la correction à son étape du panneau (avant `step_verdict`, qui garde le champ).
- `scenario.js` : `correctionOf` choisit la correction à lire : l'étape rouverte par un segment, sinon l'étape qui précède l'étape courante tant que « Continuer » ne l'a pas fermée (aussi après un rechargement). Elle remplace l'explication seule de cette étape. « Continuer » (absent d'une étape rouverte) retire les marques et le bloc, l'explication reste ; « Recommencer » envoie l'intention `restart` (absent quand le bilan le propose déjà). `statusFor` annonce le `summary_text` du serveur (« Désignation fausse… ») au lieu de « Étape réussie » pour une désignation. Le bloc de désignation disparaît avec l'étape (il ne se montre que sur l'étape courante).
- `repo.js` : `markCorrection` à côté de `markDesignated` (2 appels). CSS : ajout en fin de `workspace.css` (verdict > sélection > désignable par spécificité ; tirets `danger` pour un choix faux ; contour plein pour le reste ; le sens passe aussi par le texte ✓ ✗ ≡).
- Tests : `tests/test_correction_dom.py` (6 tests Node : marques fausse/juste/équivalente, liste du panneau et ordre, case validée sans ✕, Continuer, rechargement et Recommencer, étape rouverte), `tests/test_correction_panel.py` (le panneau serveur porte la correction, relue après remise à zéro).

## Décisions

- Marques portées par une donnée du serveur, pas calculées : elles viennent de `answer_corrected` ou du panneau, jamais de la projection `views` (une marque dans `views` changerait l'empreinte et l'annonce du lecteur d'écran à chaque correction, et ne saurait pas quand « Continuer » a été cliqué). Une seule source (`step.correction`) pour le flux, le rechargement et la réouverture.
- « Continuer » est un état d'affichage du front (aucune intention serveur) : après un rechargement, la correction de l'étape précédente revient jusqu'à ce qu'on continue de nouveau ; c'est la reprise que demandaient 5.2 et 5.3.
- `element_texts` et `label_text` sont des ajouts optionnels à la charge : les réponses déjà consignées dans un `run.json` plus ancien se relisent (le front retombe sur la forme courte de l'`element_id` et sur « Votre réponse »).

## Reports

- Marques dans les vues Code, terminal, preuves et distant : elles apparaîtront quand ces vues poseront `data-designable` + `data-element-id` et appelleront `markCorrection` après leur dessin, comme pour `markDesignated` (seul `repo.js` le fait aujourd'hui). 5.6 à 5.8 s'appuient sur ce contrat.
- (Levé en revue : la marque d'une étiquette de ref s'ajoute au nom accessible du nœud qui la contient.)
- Contrôles dans un navigateur réel pour Anaël : contraste des marques et des tirets `danger` en clair et en sombre, tenue du texte « ✓ Votre choix · ✓ Attendu » sur une rangée étroite du graphe (troncature du sujet), lecture au lecteur d'écran (nom du nœud + marque, annonce « Désignation fausse… »), ordre de Tab (voir dans les vues, Continuer, Recommencer), retour du focus sur le titre après « Continuer ».

## Revue

Revue Opus du 2026-10-19, une passe, après rebase sur `origin/main` (6.5, 2.9, 3.5, 3.3, 7.2 ; 4.4 pas encore fusionnée). Second avis Haiku : aucun medium ni high.

- Medium · second avis L2 · corrigé : deux désignations consécutives. Les marques de N restaient pendant que N+1 était armée ; elles masquaient la sélection, et un clic sur un élément marqué remplissait la case avec son nom accessible augmenté (« Commit aaaaaaa — ✓ Attendu », `labelOf`). `markCorrection` ne pose plus de marques en mode armé ou quand une case est remplie ; le bloc de correction reste lisible dans le panneau. Test `test_une_designation_suivante_armee_efface_les_marques_de_la_precedente` (rouge sans le correctif).
- Low · second avis L3 · corrigé : la marque d'une étiquette de ref (sans `aria-label`, dans un bouton nommé) n'était pas lue. Elle s'ajoute au nom du bouton qui la contient (« Commit aaaaaaa — main : ✓ Attendu »), restitué à la fermeture. Test `test_la_marque_d_une_ref_s_entend_dans_le_nom_du_noeud`.
- Low · second avis L1 · écarté : scénario fini sur une désignation. La dernière étape s'affiche alors comme une étape rouverte : correction relue sans « Continuer », et le bilan propose déjà « Recommencer ». Rien à continuer : c'est le comportement voulu.
- Info · second avis L4 · écarté : « Continuer » est client seul, décision de la story (aucune intention serveur, la correction revient après un rechargement).
- Low · second avis L8 · reporté : 4.4 n'est pas sur `main` au rebase, Recommencer reste simulé par `save_run(answers={})`. La 4.4 refait `run.json` par `initial_run` (réponses à zéro), donc l'hypothèse tient. À faire à l'intégration de 4.4 : dans `tests/test_correction_panel.py`, remplacer le `save_run` par l'intention `restart` réelle et vérifier que `correction` disparaît du panneau.
- Low · second avis L9 · écarté : la CI n'installe pas Node, mais les images GitHub (Ubuntu, macOS, Windows) l'embarquent ; les tests DOM tournent en CI : la dernière CI verte de `main` (ubuntu) compte 1084 passed et 27 skipped, alors que les tests Node sautés se compteraient par centaines.
- Info · revue · écarté : AD-2 parle de marques « portées par la projection » ; elles viennent de `answer_corrected` et du panneau serveur, pas de `views`. Le front ne calcule toujours rien. Écart justifié dans les Décisions.
- Complexité : 0 constat. `markCorrection` parcourt les nœuds désignables à chaque dessin, comme `markDesignated` (O(n)). Le reste est en O(étapes) par rendu.
