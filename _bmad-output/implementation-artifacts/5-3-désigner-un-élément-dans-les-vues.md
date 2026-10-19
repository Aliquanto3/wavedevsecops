---
story: "5.3"
key: 5-3-désigner-un-élément-dans-les-vues
title: Désigner un élément dans les vues
status: review
branch: story/5-3-designer-vues
ad: [AD-2, AD-17]
---

# Story 5.3 : Désigner un élément dans les vues

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 5.3 » ; contrat serveur : spec 5.2.

## Livré (front seulement, aucun changement serveur)

- `web/static/js/designation.js` (nouveau) :
  - `designationFor(store)` : état partagé de l'espace (mode armé, choix par case, étape concernée), comme `selectionFor`. Un autre `step_id` (ou plus d'étape de désignation) remet tout à zéro et désarme.
  - `installDesignation(workspace, designation)` : en mode armé, un écouteur de **capture** sur la racine de l'espace place dans la case tout élément `[data-designable="true"]` cliqué (Entrée sur un bouton produit un clic) et ne laisse pas la sélection ordinaire le recevoir. Échap désarme sans vider la case, rend le focus à `designate-button` et ne se propage pas (il ne replie rien d'autre). Désarmé, rien n'est capté : le clic ne sert qu'aux correspondances. Classe `is-designating` sur la racine (tirets et curseur `crosshair`, CSS).
  - `createDesignateBlock` : bloc du panneau Scénario, créé une fois et mis à jour seul (la saisie du SHA et le focus survivent aux redessins) : question du serveur, `designate-button` (« Désigner dans les vues » / « Désignation active · Échap pour quitter », `aria-pressed`, annonce en `role="status"`), une `answer-slot` par case avec ✕ (`aria-label` « Vider la case … ») quand elle est remplie, champ « Ou saisir un SHA », « Valider ma réponse » (`aria-describedby` vers « 1 seul essai »). « Valider » est inactif avec sa raison tant qu'une case est vide ou qu'une opération court (`bindAction`). Il envoie `answer_submit{slots, step_id}` (`step_id` toujours joint). Un nouveau choix remplit la première case vide, sinon remplace la dernière remplie.
  - Champ SHA : Entrée appelle `resolve_sha` (lecture seule, n'engage pas l'essai) ; un commit résolu va dans la case, un échec pose `aria-invalid` et le `reason_text` du serveur en `role="alert"`. Aperçu en direct et liste filtrable restent pour 5.4.
  - `markDesignated` : contour plein (`is-designated`) sur les éléments choisis, à la place des tirets.
- Contrat pour les vues : tout élément désignable porte `data-designable="true|false"` (la valeur de `designable` de la projection) et `data-element-id` (ou `data-designate-id`, pour une ref dans un bouton). `repo.js` le pose sur les nœuds du graphe, les étiquettes de refs, la liste des commits et l'index. Les vues Code, terminal et preuves (lignes de diff, en-têtes de fichier, sorties) n'ont qu'à poser les mêmes attributs et appeler `markDesignated` après leur dessin.
- Fichiers partagés, ajouts localisés : `scenario.js` (paramètre `designation`, bloc inséré après la consigne, clé de focus `data-designate-focus`), `workspace.js` (3 lignes), `repo.js` (attributs, `markDesignated`), `workspace.css` (ajout en fin de fichier).
- Tests : `tests/test_designation_dom.py` (8 tests Node sur la doublure de DOM).

## Décisions

- Le front ne décide pas de ce qui est désignable (AD-2) : il lit `designable`. Un élément non désignable cliqué en mode armé retombe sur la sélection ordinaire.
- Le texte d'un choix vient du nom accessible écrit par le serveur (`aria-label`), jamais composé par le front.
- Échap est géré sur la racine de l'espace (pas sur `document`) pour passer avant l'Échap du menu et de l'agrandissement.

## Reports

- Correction à l'écran après la soumission (`answer_corrected`, marques « Votre choix / Attendu », case « validée », reprise après rechargement) : story 5.5. En attendant, la validation ferme l'étape comme pour 5.2 et le panneau montre « Étape réussie ».
- Liste filtrable `designate-list` et aperçu du SHA en direct : story 5.4.
- Désignation au clavier d'une ref (étiquette dans un bouton de nœud) : seule la souris la atteint pour l'instant ; 5.4 la couvre par la liste.
- Vues Code, lignes de diff, en-têtes de fichier, lignes du terminal : leurs vues posent les attributs ci-dessus quand elles existent (2.8, suivantes).
- Contrôles dans un navigateur réel pour Anaël : tirets et curseur `crosshair`, contraste du bouton armé en clair et en sombre, annonce au lecteur d'écran, ordre de Tab (✕, SHA, Valider) en mode armé, Échap depuis le terminal.

## Revue

- medium · second avis M1 · corrigé · « Valider » sans garde synchrone : un double clic envoyait deux `answer_submit` (le second en 409, affiché en `role="alert"`). Garde posée au clic (« Réponse en cours d'envoi. ») ; levée si l'envoi échoue, sinon au changement d'étape ou au retour du moteur au repos. Test `test_double_clic_sur_valider_n_envoie_qu_une_reponse`.
- medium · second avis M2 · corrigé · conflits du rebase sur `story/4-6-indices-paliers` (bilan 4.7, onglets d'indices 4.6) : tout est gardé ; ordre du panneau progression, bilan, consigne, désignation, indices, quiz (le bloc de désignation, inséré par l'auto-fusion après le quiz, est remonté sous la consigne comme le dit la spec) ; CSS de 5.3 remis en fin de fichier après celui de 4.6.
- low · second avis L3 · corrigé · un SHA résolu après un changement d'étape tombait dans la nouvelle étape ; un commit était placé même si l'étape n'accepte pas `commit`. La résolution est ignorée si l'étape a changé ; un type non attendu affiche « Cette question n'attend pas de commit. » (le serveur l'aurait refusé en 409 sans consommer l'essai). Doublons dans deux cases : rejeté, le serveur juge la réponse et une question peut attendre deux fois le même élément.
- low · second avis L4 · reporté (5.4) · refs non désignables au clavier, déjà dans les reports.
- low · second avis L5 · rejeté · abonnements cumulés par `renderRepo` : même schéma borné que `selectionFor`, un abonnement par vue ouverte, sans croissance pendant l'exécution.
- low · second avis L6 · reporté · armé avec la chaîne ouverte, le premier Échap désarme puis le second ferme la chaîne ; acceptable (deux Échap, aucun état perdu), à revoir avec la priorité globale des Échap.
- Complexité : 0 constat (`markDesignated` et `drawSlots` sont O(éléments affichés) par notification, structures bornées par la vue).
