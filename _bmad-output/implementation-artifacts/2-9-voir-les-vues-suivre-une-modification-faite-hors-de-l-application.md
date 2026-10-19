---
story: "2.9"
key: 2-9-voir-les-vues-suivre-une-modification-faite-hors-de-l-application
title: Voir les vues suivre une modification faite hors de l'application
status: review
branch: story/2-9-modif-hors-appli
ad: [AD-1, AD-6, AD-17]
---

# Story 2.9 : Voir les vues suivre une modification faite hors de l'application

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 2.9 ». UX : DESIGN.md (`external-change-notice`), EXPERIENCE.md (modification externe). FR-3, UX-DR17, décision « délais chiffrés ».

## État de départ

Les stories 2.2 et 2.8 avaient déjà posé : `TreeWatcher` (suspendu pendant `command`, `setup`, `restoring`, `.git/` ignoré), l'opération `external_change` filtrée par l'empreinte et par le `RepoState` relu, l'événement `external_change` (AD-17), le rafraîchissement des vues Code à chaque projection, et le conflit à l'enregistrement. Il manquait le délai chiffré, la ligne `external-change-notice`, le conflit détecté dès que le disque change, et un écart de comportement du surveillant.

## Livré

- `Settings.watch_quiet_ms` : 500 → **300** (délai de silence de l'exigence). Budget de bout en bout : 300 ms de silence + interrogation/debounce du surveillant, soit environ 0,1 à 0,5 s en pratique, sous les 2 s.
- `engine/watcher.py` :
  - **Lot retenu pendant le silence** : une écriture d'éditeur externe juste après une commande tombait dans le délai de silence et était perdue (rien ne la rejouait). Elle est désormais retenue (`_pending`) et proposée à la fin du délai par un `threading.Timer`, une seule fois ; si c'était le bruit de la commande, l'empreinte inchangée l'écarte dans la file. La reprise remplace le lot retenu avant la suspension (la projection de la commande l'a couvert) ; un lot vu **pendant** la suspension (écriture externe entre la projection de la commande et la reprise) est retenu et proposé après le silence (revue) ; `stop()` annule le minuteur.
  - Propriété `suspended` (lecture sous verrou), utilisée par les tests.
  - `rust_timeout` reste à 500 ms : au-dessous du `debounce` (200 ms), `watchfiles` rendait la main avant la fin du debounce et des lots n'arrivaient pas (constaté en essai à 100 ms).
- Front :
  - `store.js` : compteur `externalChange`, incrémenté à chaque événement `external_change`.
  - `code.js` : `external-change-notice` (`<p role="status">`, « Modifié hors de l'application », fond `primary-soft`) en haut du volet Code, affichée à la première modification externe de la vue. `refreshOpen` relit aussi un fichier **non enregistré** : si le disque diffère, la barre de conflit (« Le fichier a changé sur le disque. », « Garder ma version » / « Recharger ») apparaît tout de suite, sans attendre l'enregistrement ; un fichier propre est rechargé comme avant. `CONFLICT_TEXT` devient « Le fichier a changé sur le disque. » (texte de l'exigence).
  - `css/code.css` : style de la ligne.
- Tests :
  - `tests/test_external_changes.py` (vrai surveillant en interrogation, vraie file, projecteur sur le contenu de `repo/a.txt`) : modification suivie en moins de 2 s ; changement sous `.git/` seul ou contenu identique : aucune opération ; fichier écrit par une commande en cours : aucune opération, pendant ni après le silence ; écriture externe juste après une commande : vue ; lot retenu puis proposé une seule fois ; lot oublié si une commande reprend.
  - `tests/test_code_external.py` (Node) : ligne `external-change-notice` et rechargement d'un fichier propre ; fichier non enregistré : barre de conflit, « Recharger ».
  - `tests/test_code_dom.py` : texte du conflit aligné.

## Décisions

- La ligne `external-change-notice` reste affichée jusqu'au rechargement de la vue (pas de minuteur) : elle dit une vérité d'état (« la vue a été mise à jour »), sans bruit animé. Elle porte `role="status"` (annonce polie).
- Les tests du surveillant attendent la reprise (`suspended` faux) avant d'écrire : la file rend le résultat un instant avant l'état de repos, et un changement observé pendant la suspension est écarté par conception. Ils amorcent le surveillant par une écriture réessayée, sans contrainte de délai, jusqu'à la voir : l'état de référence de l'interrogation n'est sûr qu'un instant après le premier tour. Chaque écriture mesurée attend la seconde suivante : le polling de `watchfiles` (crate `notify`) compare les dates de modification à la seconde près (constaté en revue : deuxième écriture dans la même seconde jamais vue). La mesure des 2 s est ensuite stricte : une seule écriture, événement reconnu à son empreinte.
- Les tests utilisent `force_polling` (identique sur Windows, macOS et Linux) ; le mode natif reste couvert par le test existant de `test_workspace_manager.py` (création de fichier).

## Reports

- Persistance/effacement de la ligne `external-change-notice` après une action de l'apprenant (enregistrement, nouvelle commande) : à décider avec l'UX.
- Lot retenu perdu si l'application s'arrête pendant le silence (sans conséquence : l'empreinte est recalculée à la réouverture).
- À vérifier dans un navigateur par Anaël : rendu de la ligne (thème sombre, lecteur d'écran), latence ressentie avec un vrai éditeur (VS Code, Notepad) sous Windows.

## Revue

Revue Opus (une passe), après rebase sur `origin/main` (5.1, 4.6, 7.2), avec la liste du second avis (Haiku).

- Medium · second avis M1 · corrigé : un lot vu pendant la suspension (écriture externe entre la projection d'une commande et la reprise) était perdu. `notify` note `_dropped` pendant la suspension ; `resume` le retient et arme le minuteur, la pré-vérification d'empreinte écarte le bruit de la commande. Tests : `test_ecriture_externe_pendant_la_suspension_proposee_a_la_reprise` (minuteur réel) et `test_ecriture_externe_pendant_une_commande_vue_apres` (vraie file, écriture pendant la projection) ; tous deux échouent sans le correctif.
- Medium · second avis M2 · corrigé : `_edit_until_seen` remplacé par `_edit_and_measure` (une écriture, événement reconnu à son empreinte, délai rendu même au-delà du budget) ; amorce du polling dans `_start`. Cause des réessais trouvée : polling à la seconde près (voir Décisions). Stable sur 5 passages.
- Low · second avis L3 · reporté : fichier ouvert supprimé ou renommé hors de l'application, aucune barre ; l'enregistrement le recrée ou dit l'échec. À trancher avec l'UX (message « fichier supprimé sur le disque »).
- Low · second avis L4 · corrigé : `buffer.conflict` effacé quand le tampon redevient propre ou que le disque revient à la version ouverte (sinon « Recharger » pouvait rendre une version plus ancienne). Test Node `test_conflit_efface_quand_le_tampon_redevient_propre`.
- Low · second avis L5 · corrigé : la ligne ne s'affiche que si le compteur augmente, et se masque quand il repart de 0 (changement d'espace). Test Node `test_notice_masquee_au_changement_d_espace`.
- Low · second avis L6 · corrigé : le minuteur réel est désormais couvert (test d'écriture juste après une commande, mesuré strictement, et test de suspension).
- Low · second avis L7 · corrigé : doc du lot retenu alignée sur le code (section Livré).
- Low · second avis L8 · rejeté : la fenêtre au démarrage du surveillant précède toute vue affichée ; la première projection relit l'arbre.
- Info · second avis (300 ms sans faux « externe », passage par la file, pas de doublon, `base_hash`) · confirmé.
- Complexité : 0 constat (compteur entier côté store, aucun parcours du journal par événement).
