# WaveDevSecOps — Relecture d'accessibilité (WCAG 2.2 AA)

Date : 2026-10-18. Périmètre : `DESIGN.md`, `EXPERIENCE.md`, `.memlog.md` (statut draft). Relecture en lecture seule ; aucune maquette n'existe encore (« à venir dans `mockups/` »), donc tout ce qui suit porte sur la spécification. Les ratios sont calculés avec la formule WCAG de luminance relative (script Python, valeurs hexadécimales des jetons de `DESIGN.md`). Seuils : 4,5:1 texte, 3:1 composants et contours non textuels.

## Synthèse

| Sévérité | Nombre |
|---|---|
| critical | 1 |
| high | 5 |
| medium | 10 |
| low | 8 |
| Total | 24 |

Points solides à conserver : tous les couples texte/surface porteurs passent dans les deux thèmes (minimum 5,0:1 hors cas listés) ; l'état n'est presque jamais porté par la couleur seule (✓/✗/⚠ + mots, « Attendu / Votre choix », « perdu · visible par reflog », lettres d'état git, préfixes + / −) ; aucun décompte ni limite de temps n'est imposé (voir « Temps » plus bas) ; le terminal reste lisible dans les deux thèmes (le point ouvert n°11 est levé par le calcul, voir tableau).

## Constats

### A-01 — critical — Mode désignation : parcours clavier incomplet (2.1.1, A)
- Emplacement : EXPERIENCE.md > Accessibility Floor (« Désignation au clavier ») ; > Désignation, points 2 à 4 ; > Flow 5 étape 4.
- Constat : (a) « Tab ne parcourt alors que les éléments désignables » : pendant que le mode est armé, la case de réponse (✕ de retrait), le champ SHA, « Valider ma réponse » et le bouton « Désignation active » ne sont pas atteignables par Tab. Le seul moyen de sortie est Échap, qui désarme, et la spec ne dit pas si la sélection placée survit. Le parcours « armer, parcourir, choisir, retirer, valider » n'est donc pas faisable de bout en bout. (b) Les lignes de diff (« chaque ligne est un élément liable et désignable ») et les blocs de sortie du terminal ne sont pas déclarés focalisables ; parcourir des centaines de lignes une à une par Tab est de plus impraticable. (c) Le Flow 5 fait désigner la sortie de gitleaks « dans le terminal » : or le terminal est une région `role="log"` et capte le clavier ; aucune façon de désigner une ligne ou un bloc au clavier n'est décrite. (d) « Le champ SHA reste l'alternative complète » est faux pour la preuve RSSI : il ne couvre que les commits, pas une sortie d'outil, un check, un SBOM ou un tag.
- Correctif : ne pas restreindre Tab. Le mode armé ajoute seulement un état (`aria-pressed`, annonce) et garde l'ordre normal ; chaque vue expose un seul arrêt de tabulation (focus itinérant) avec flèches pour parcourir ses éléments désignables, Entrée pour placer. Ajouter une commande « Aller à la case de réponse » (raccourci F6 étendu ou lien d'évitement). Faire de chaque bloc de sortie d'outil et de chaque ligne de diff un élément focalisable dans le focus itinérant de sa vue. Prévoir pour les preuves non-commit une alternative saisie ou liste : sélecteur « Choisir une preuve dans la liste » (liste plate des éléments désignables du type attendu, avec nom accessible), équivalent complet du clic. Préciser que Échap désarme sans effacer la case, et que le focus revient sur le bouton « Désigner ».

### A-02 — high — Estompage à 0,35 : texte illisible pendant la mise en correspondance (1.4.3)
- Emplacement : DESIGN.md > `link-state` (`dimmed-opacity: 0.35`) ; EXPERIENCE.md > Interaction Primitives, State Patterns (Restauration en cours).
- Constat : survol ou focus estompe tous les éléments non liés à 0,35. Ratios obtenus : texte `ink` sur surface-raised 2,34:1 (clair) et 2,90:1 (sombre) ; `ink-soft` 1,81:1 et 2,16:1. Le texte estompé reste du contenu actif (pas un composant inactif exempté), et le focus clavier peut y rester longtemps.
- Correctif : ne pas utiliser `opacity` sur le texte. Estomper les décors (remplissages, traits) et garder le texte à ≥ 4,5:1 : opacité minimale 0,56 (`ink`, clair) / 0,51 (sombre) ; 0,76 / 0,69 pour `ink-soft`. En pratique prendre 0,8 et ajouter un signal non coloré pour les éléments liés (déjà l'anneau). Même règle pour l'état « Restauration en cours » (composants inactifs : exemptés, mais lisibles à 0,6 minimum pour que le message reste lu).

### A-03 — high — Annonces lecteur d'écran absentes pour les changements d'état centraux (4.1.3, 1.3.1)
- Emplacement : EXPERIENCE.md > State Patterns (Synchro après commande), Component Patterns (`verdict-mark`, `new-mark`, `scenario-panel`), Accessibility Floor.
- Constat : seule l'explication attachée (`explain-popover`) est dite `aria-live="polite"`. Rien n'annonce : la mise à jour des vues après une commande (« Nouveau » posé), la validation d'étape et l'apparition de l'explication dans le panneau, la correction (« Attendu » / « Votre choix » posés dans d'autres vues, alors que le focus reste sur « Valider »), le passage de `step-progress`, le refus « SHA inconnu », le bilan. Un utilisateur de lecteur d'écran ne sait pas que la commande a eu un effet visuel.
- Correctif : une région `role="status"` (polite) unique, alimentée dans l'ordre FR-4 : « Commande terminée, code 0. Vues mises à jour : 1 commit et 1 branche nouveaux. Étape 3 validée. » ; l'explication d'étape et le verdict en `role="status"` dans le panneau (l'explication reste après les vues). Les `verdict-mark` entrent dans le nom accessible de l'élément (« Commit a1b2c3d, attendu » ; « votre choix, incorrect »). Refus de commande et échec de restauration en `role="alert"`.

### A-04 — high — Graphe git : nom accessible incomplet et relations non exposées (1.3.1, 4.1.2)
- Emplacement : EXPERIENCE.md > Accessibility Floor (« Noms accessibles ») ; Component Patterns (`graph-*`).
- Constat : l'exemple de nom (« Commit a1b2c3d, Add config, par l'agent, pointé par feature et HEAD ») ne couvre ni les parents/enfants (la topologie est ce qu'on apprend : divergence, fusion, commit perdu), ni les états « Nouveau », « perdu · visible par reflog », « origin/… » (distant), « détachée », « sélectionné », « lié », « désignable ». Les arêtes (`graph-edge`) n'ont aucun équivalent texte.
- Correctif : donner à chaque nœud un nom construit par gabarit (SHA, message, auteur, parents « parent : 9f8e7d6 », refs locales, refs distantes, tags, états) et exposer la relation parent par `aria-describedby`/liste. Fournir pour la vue 1 une alternative textuelle équivalente : tableau ou liste « Commits » (SHA, message, parents, refs, état) basculable ou toujours présent en rôle `table` caché visuellement, équivalent de `git log --all --graph`. Les refs (branches, tags, distantes) ont rôle et nom : « branche locale feature », « référence distante origin/main », « tag v0.1.0 ».

### A-05 — high — Cibles trop petites : lignes de diff et disques du graphe (2.5.8)
- Emplacement : DESIGN.md > `graph-commit` (disque de 14 px), `diff-view` (13 px × 1,5 = 19,5 px de hauteur de ligne) ; EXPERIENCE.md > `diff-view`, Désignation.
- Constat : les lignes de diff sont cliquables et désignables, empilées sans espace : 19,5 px de haut, sous 24 px, sans exception d'espacement possible (cibles contiguës). Le disque de commit fait 14 px ; l'exception d'espacement ne tient que si aucun autre cible n'est dans un cercle de 24 px. Contredit `hit-target-min` de 32 px posé par la spec.
- Correctif : hauteur de ligne de diff interactive ≥ 24 px (idéalement 28 px) ; zone cliquable du nœud de graphe = disque + SHA + message, ≥ 24 × 24 px, avec espacement vertical ≥ 28 px entre commits ; l'indication visuelle reste de 14 px mais la zone de clic est étendue. Vérifier de même la pastille d'étape, les puces de référence, « i » (≥ 24 px).

### A-06 — high — Anneau de focus : contraste et distinction insuffisants (2.4.7, 1.4.11)
- Emplacement : EXPERIENCE.md > Accessibility Floor (« focus visible `{colors.primary}` 2 px ») ; DESIGN.md > `terminal`, `button-primary`, `graph-head`.
- Constat : en thème clair, l'anneau `primary` `#451DC7` sur le fond du terminal `#0A0A14` ne fait que 2,11:1 (< 3:1). Sur `button-primary` (fond `primary`) ou sur `graph-head` / `new-mark` (fond encre), un anneau collé de même couleur que le fond est nul (1,00:1) ; aucun décalage n'est spécifié hors `designable`. En sombre, l'anneau `primary-dark` passe partout (≥ 5,0:1).
- Correctif : anneau double (2 px `ink` + 2 px `surface-raised`, ou décalage de 2 px) ; dans le terminal, anneau `on-ink` (blanc, 19,7:1) ou `primary-dark` en thème clair. Ajouter à `tests/test_web_tokens.py` : anneau de focus ≥ 3:1 sur chaque surface où un élément focalisable peut se trouver.

### A-07 — medium — Bordures `line` quasi invisibles comme limites de composants (1.4.11)
- Emplacement : DESIGN.md > `answer-slot` (bordure `line` en tirets), `reset-button`, `pane`, `scenario-card` indisponible ; champ SHA (aucune bordure spécifiée).
- Constat : `line` sur surface-raised 1,24:1 (clair), 1,48:1 (sombre) ; sur neutral-soft 1,08:1 et 1,35:1. La case de réponse vide, le champ SHA et le bouton « Recommencer » n'ont donc pas de limite visible à 3:1. Le texte d'aide les identifie en partie, mais un champ de saisie sans bord ne passe pas.
- Correctif : bordure de champ et de case (vide et pleine) en `muted` ou `ink-soft` (3:1 minimum : `muted` fait 3,38:1 en clair, 4,90:1 en sombre sur surface-raised) ; spécifier explicitement le champ SHA.

### A-08 — medium — Anneau « lié » = même teinte que le focus, sélection distinguée par la couleur seule (1.4.1, 2.4.7)
- Emplacement : DESIGN.md > `link-state` (anneau 2 px de couleur de discipline), `designable` ; Colors (`discipline-prompt` = `primary`).
- Constat : pour les éléments du dépôt local, l'anneau « lié » est violet `primary`, exactement la couleur de l'anneau de focus et du contour `designable`. Anneau lié, focus, contour désignable et sélection `ink` ne se distinguent que par teinte ou par pointillés (désignable). Un utilisateur qui ne distingue pas ces teintes ne sait pas où est son focus.
- Correctif : différencier par la forme : focus = anneau double plein décalé ; lié = fond teinté + coche ou marque « lié » ; sélection = contour épais ink + marque ● ; désignable = tirets. Ajouter un état texte (`aria-selected`, nom « lié à… »).

### A-09 — medium — Carte de la chaîne dépliée : gestion du focus non spécifiée (2.4.11, 4.1.2, 2.1.1)
- Emplacement : EXPERIENCE.md > Disposition A (« par-dessus les vues »), `chain-band` / `chain-map`.
- Constat : la carte se superpose aux vues, sans modale. Tab peut alors atteindre des éléments cachés sous la carte (focus entièrement masqué, 2.4.11). Aucun `aria-expanded` sur « Carte ▾ », aucune règle de focus à l'ouverture (premier nœud ? bouton ?) ni de retour du focus à la fermeture par Échap. La station courante (« Vous êtes ici ») n'a pas d'`aria-current`.
- Correctif : « Carte ▾ » = bouton `aria-expanded` + `aria-controls` ; à l'ouverture, focus sur le titre ou la station demandée ; vues dessous `inert` ; Échap ferme et rend le focus au bouton ; `aria-current="step"` sur la station courante ; zones de la carte en régions nommées, nœuds en liste.

### A-10 — medium — Terminal : flux de lecture et distinction stdout/stderr pour les lecteurs d'écran (1.3.1, 4.1.3, 3.1.2)
- Emplacement : EXPERIENCE.md > Accessibility Floor (« Terminal ») ; State Patterns (Commande refusée) ; Voice and Tone (langue de git).
- Constat : (a) stderr se distingue seulement par une teinte voisine (`on-ink-soft` contre `on-ink`) et un filet de 2 px ; « annoncés comme tels » n'est pas réalisé par une technique (préfixe masqué). (b) `role="log"` est poli : une sortie de `git log` de plusieurs centaines de lignes inonde le lecteur ; « refus » doit être immédiat (la règle générale dit « annoncés tout de suite ») mais il est écrit dans un log poli. (c) Une sortie de git en anglais (MinGit) dans une page `lang="fr"` est mal prononcée. (d) Le terminal « lecture seule pendant le quiz » n'est pas exposé (`aria-readonly`, raison reliée).
- Correctif : préfixe masqué visuellement « erreur standard : » devant chaque ligne stderr, « code de sortie 128, échec » sur la ligne finale ; garder le log poli mais résumer en fin de commande (voir A-03) avec `aria-atomic` sur le résumé, et `role="alert"` pour `terminal-refused` ; `lang="en"` sur les blocs de sortie anglais ; `aria-readonly="true"` + `aria-describedby` sur la saisie quand elle est restreinte.

### A-11 — medium — Onglets d'indice verrouillés et déblocage dépendant du temps (4.1.2, 4.1.3, 2.2.1)
- Emplacement : EXPERIENCE.md > Indices à paliers ; DESIGN.md > `hint-tabs`.
- Constat : l'onglet verrouillé est « grisé » : si implémenté avec `disabled`, il sort de l'ordre de tabulation et la condition (« Disponible après un essai ou un moment de lecture ») n'est pas atteinte par un lecteur d'écran. Le déblocage se produit sans événement annoncé. Pas de motif `role="tablist"` précisé (flèches, `aria-selected`). Voir « Temps » : pas de violation de 2.2.1, la durée interne ne coupe rien.
- Correctif : `role="tablist"`/`tab`/`tabpanel`, onglet verrouillé en `aria-disabled="true"` toujours focalisable, condition reliée par `aria-describedby`, déblocage annoncé en `role="status"` (« La solution est disponible. ») ; ne pas cacher le cadenas, l'icône a un nom (« verrouillé »).

### A-12 — medium — `quiz-banner` : position, annonce et retour (4.1.3, 2.4.3, 3.2.x)
- Emplacement : EXPERIENCE.md > Quiz à exécution réelle ; Component Patterns (`quiz-banner`).
- Constat : le bandeau est « au-dessus des vues », donc probablement avant le panneau dans l'ordre du DOM, alors que l'utilisateur est dans le panneau quand il l'a déclenché. L'apparition n'est pas annoncée ; le focus reste sur « Exécuter ma réponse ». Le bouton « J'ai compris, rétablir l'état » n'est pas dans l'ordre de lecture du flux d'action. La couleur d'avertissement est accompagnée de l'icône ⚠ et de texte : conforme à 1.4.1.
- Correctif : `role="status"` (ou `alert` : l'état est bloquant pour les commandes), contenu texte complet ; focus déplacé sur le bandeau ou lien « Aller au bandeau » dans le panneau ; ordre du DOM : bandeau juste avant le panneau ; après rétablissement, focus sur le panneau (« Rétabli »).

### A-13 — medium — Terminal : piège potentiel et sortie du focus (2.1.2, 2.4.3, 2.1.4)
- Emplacement : EXPERIENCE.md > Interaction Primitives (« Terminal »), Component Patterns (`terminal`, ↑/↓, Ctrl+C, Ctrl+L), Accessibility Floor.
- Constat : pas de piège aujourd'hui (Tab sort, F6 aussi), mais : (a) « Échap rend le focus au document » : cible non définie (où atterrit-il ?) ; et Échap est aussi dans la hiérarchie Échap (popover, carte, désignation...) : un Échap dans le terminal agit-il sur les deux ? (b) la complétion est exclue en v0.1 mais une v ultérieure qui capterait Tab créerait un piège ; (c) Ctrl+C/Ctrl+L s'ajoutent aux raccourcis du navigateur (Ctrl+L = barre d'adresse) : les raccourcis à caractère unique sont absents, ce qui est bien.
- Correctif : écrire que Tab quitte toujours le terminal ; Échap met le focus sur le titre de la vue 4 (et uniquement cela) ; hiérarchie Échap évaluée seulement hors terminal ; garder Tab libre si une complétion arrive (utiliser Ctrl+Espace). Ajouter dans la vue un lien d'évitement « Aller à la vue suivante ».

### A-14 — medium — Correspondances au focus : annonce bavarde et doublonnée (4.1.3)
- Emplacement : EXPERIENCE.md > Accessibility Floor (« Correspondances au clavier »).
- Constat : une région `aria-live="polite"` résume « 3 éléments liés : ... » à chaque focus. Avec un focus itinérant dans le graphe, chaque flèche déclenche l'annonce de l'élément (nom accessible) puis celle de la région : double lecture, et file d'attente.
- Correctif : lier le résumé par `aria-describedby` au nœud focalisé, ou n'annoncer qu'après une pause (≈ 500 ms) et sur sélection (Entrée) seulement ; garder la liste des correspondants consultable par une touche (« L » ou lien « Voir les éléments liés ») plutôt qu'à chaque déplacement.

### A-15 — medium — Masquage des vues et poignées : focus et alternative au glisser (2.4.3, 4.1.2, 2.5.7)
- Emplacement : EXPERIENCE.md > Masquage et agrandissement.
- Constat : « — » masque une vue (focus perdu sur un élément disparu) ; « ⛶ » mode focus (Échap) ; la poignée de gouttière n'est décrite qu'au clavier par pas de 16 px et double-clic. Rôle ARIA absent. Le glisser a une alternative clavier, mais pas d'alternative à pointeur unique non glissé (2.5.7) hormis le double-clic de réinitialisation.
- Correctif : après « — », focus sur la puce « + Nom » ; après « + », focus sur le titre de la vue ; poignée `role="separator"` avec `aria-valuenow/min/max` et flèches ; ajouter boutons « Élargir » / « Réduire » dans « Volets ▾ » comme alternative à pointeur unique.

### A-16 — medium — Réflexion et zoom 400 % (1.4.10, 1.4.4)
- Emplacement : EXPERIENCE.md > Responsive & Platform (« Très petite (< 1280 px) : mode focus seul » ; « à 125 % … repli »).
- Constat : à 200 % ou 400 % de zoom sur 1920 px, la fenêtre équivaut à 960 ou 480 px CSS : le mode focus doit alors suffire sans défilement horizontal pour le contenu non bidimensionnel (panneau, explications, catalogue, diagnostic). La spec écarte « mobile » mais le critère s'applique au zoom.
- Correctif : ajouter la règle « à 320 px CSS (400 %), le panneau Scénario et les pages annexes se lisent sur une colonne sans défilement horizontal ; seuls le graphe, le diff et le terminal peuvent défiler dans les deux sens » ; tester à 200 % et 400 %.

### A-17 — low — Règle « muted jamais en texte » (1.4.3)
- Emplacement : DESIGN.md > Colors, `state-unavailable`, `discipline-neutral`.
- Constat : `muted` `#8A8A9E` fait 3,38:1 sur surface-raised et 3,12:1 sur surface en clair (4,90 et 5,50 en sombre). Il sert de filet et de tirets (3:1 : OK) mais pas de texte. La spec utilise bien `ink-soft` pour les textes grisés ; la règle n'est pas écrite.
- Correctif : ajouter aux Don't : « `muted` et `discipline-neutral` ne servent jamais pour du texte ni pour l'icône seule en thème clair ».

### A-18 — low — Couleurs jaunes en clair sous 3:1 comme limite (1.4.11)
- Emplacement : DESIGN.md > `quiz-banner` (filet `warning`), Colors (`hosting-network`, `discipline-network`).
- Constat : `warning` sur blanc 1,52:1, `discipline-network` `#D9A400` sur blanc 2,27:1. Le filet du bandeau est décoratif (icône ⚠ et texte portent le sens : conforme). Le bouton « Exécuter le code (réseau possible) » marqué en jaune doit avoir une limite à 3:1 s'il est identifié par sa bordure.
- Correctif : bordure et icône du bouton réseau en `ink` ou `ink-soft`, la pastille jaune reste un complément ; vérifier qu'aucun filet jaune n'est seul porteur.

### A-19 — low — Segments de `step-progress` : relecture au survol seul (1.4.13, 2.1.1)
- Emplacement : EXPERIENCE.md > Component Patterns (`step-progress`, « Un segment terminé se survole »).
- Constat : information donnée au seul survol, ce que la spec bannit elle-même (Interaction Primitives). Pas de rôle clavier.
- Correctif : segments en boutons focalisables ouvrant la consigne dans une région déclarée (comme `explain-popover`) ; barre en `role="list"`, état « terminé / courante / à venir » dans le nom.

### A-20 — low — Mouvement et mise à jour automatique (2.2.2, 2.3.3)
- Emplacement : EXPERIENCE.md > Accessibility Floor (« Mouvement réduit »), State Patterns (chronomètres).
- Constat : `prefers-reduced-motion` est traité (point fixe, transitions coupées, défilement sans animation). Il reste : chronomètres qui s'incrémentent (« En cours… 3 s », « Modifié il y a 2 s ») pendant plus de 5 s ; le chronomètre ne doit pas être annoncé chaque seconde. Pas de bascule manuelle dans « Affichage ▾ ».
- Correctif : retirer le chronomètre de toute région live (annoncer « En cours » une fois, « Terminé » à la fin) ; ajouter dans « Affichage ▾ » un réglage « Réduire les animations » qui complète la préférence système ; le point « en cours » fixe reste accompagné du mot.

### A-21 — low — Branche locale, branche distante et tag : forme voisine (1.4.1)
- Emplacement : DESIGN.md > Shapes, `graph-branch`, `graph-remote-ref`.
- Constat : branche locale et ref distante sont deux pilules ; seuls le préfixe « origin/ » et la teinte (vert d'eau, bordure 2 px) les distinguent. Le préfixe texte suffit pour 1.4.1, mais la différence visuelle est faible en niveaux de gris. Commit de l'agent / collègue : badges texte, conforme. Commit perdu : tirets + libellé, conforme.
- Correctif : ajouter une icône (ordinateur / nuage) dans la pilule distante, et une forme distincte (pilule à bord plein pour local, pilule à double bord pour distant).

### A-22 — low — Champ SHA et bouton « Valider » inactif (3.3.1, 3.3.3, 4.1.2)
- Emplacement : EXPERIENCE.md > Désignation (point 4), Entretien RSSI.
- Constat : les messages (« Aucun commit ne correspond… », « Il manque la preuve… ») sont donnés mais pas leur technique : `role="alert"`/`aria-live`, `aria-invalid`, `aria-describedby`. Un `button disabled` quitte la tabulation, le motif n'est alors pas lu.
- Correctif : `aria-disabled="true"` + `aria-describedby` vers le texte du motif ; erreur de SHA en `role="alert"` avec `aria-invalid` ; l'aperçu du SHA résolu en `role="status"`.

### A-23 — low — `diagnostic-badge` et lignes de diagnostic (1.3.1, 1.4.1)
- Emplacement : DESIGN.md > `diagnostic-badge` ; EXPERIENCE.md > Diagnostic.
- Constat : la pastille rouge ne porte qu'un nombre. États ✓ / ⚠ / ✗ + mots : conforme. « ligne rouge » pour git absent est accompagné de la cause et de l'action : conforme.
- Correctif : nom accessible « Diagnostic, 2 outils absents ou trop anciens » ; tableau avec en-têtes `th` et `scope`, état dans une cellule texte.

### A-24 — low — Éléments purement décoratifs sous 3:1 (information de repli présente)
- Emplacement : DESIGN.md > `pr-check` en cours (point `state-active` `#04F06A` sur `primary-soft` 1,28:1 en clair), `scenario-card` indisponible (tirets `line` 1,08:1), `pane` (bordure `line` 1,15:1).
- Constat : sans conséquence tant que l'état est dit aussi par un mot (« En cours », « Indisponible », raison visible). À noter pour que personne ne s'appuie ensuite sur ces éléments comme seul signal.
- Correctif : consigner dans DESIGN.md que ces éléments sont décoratifs ; `aria-hidden="true"` sur le point.

## Temps (2.2.1) et cibles (2.5.8)
- Aucune limite de temps n'est imposée : le déblocage de la solution est « après un essai ou un moment de lecture », sans décompte affiché ; rien n'expire, ne coupe une saisie ou ne pénalise la lenteur (l'essai unique de FR-12 n'est pas chronométré). Conforme à 2.2.1. À corriger seulement l'annonce du déblocage (A-11) et les chronomètres (A-20).
- Cibles : `hit-target-min` de 32 px couvre boutons, ✕, poignées. Les exceptions réelles sont A-05 (lignes de diff 19,5 px, disques 14 px). Les termes de glossaire en ligne et les liens SHA dans le texte relèvent de l'exception « en ligne ».

## Tableau des ratios calculés

Formule WCAG 2.x, luminance relative sRGB. « Seuil » : 4,5 texte, 3 composant ou contour. Les échecs sont en gras.

| Combinaison | Seuil | Clair | Sombre |
|---|---|---|---|
| Texte courant `ink` / surface-raised | 4,5 | 19,69 | 14,02 |
| Texte courant `ink` / surface | 4,5 | 18,15 | 15,74 |
| Texte secondaire `ink-soft` / surface-raised | 4,5 | 8,63 | 8,06 |
| Texte secondaire `ink-soft` / surface | 4,5 | 7,96 | 9,05 |
| `muted` en texte / surface-raised | 4,5 | **3,38** | 4,90 |
| `muted` en texte / surface | 4,5 | **3,12** | 5,50 |
| Terminal : texte / fond (clair `#0A0A14`, sombre `#12121C`) | 4,5 | 19,69 | 15,74 |
| Terminal stderr `on-ink-soft` / fond | 4,5 | 12,66 | 11,96 |
| Terminal invite `primary-dark` `#9C86FF` / fond | 4,5 | 6,81 | 6,44 |
| Terminal ✗ / refus `danger-dark` `#FF6B7F` / fond | 4,5 | 7,18 | 6,79 |
| Terminal message de l'application `on-ink-soft` / fond (corps 13 px) | 4,5 | 12,66 | 11,96 |
| Filet stderr `muted` / fond du terminal | 3 | 5,82 | 5,50 |
| Filet message application `primary-dark` / fond | 3 | 6,81 | 6,44 |
| Filet refus `danger-dark` / fond | 3 | 7,18 | 6,79 |
| Succès : `ink` / `accent-soft` | 4,5 | 17,60 | 10,76 |
| Échec : `ink` / `danger-soft` | 4,5 | 16,80 | 13,35 |
| Avertissement : `ink` / `warning-soft` | 4,5 | 17,97 | 11,04 |
| En cours : `ink` / `primary-soft` | 4,5 | 16,37 | 12,21 |
| Pastille `on-vivid` / `accent` | 4,5 | 12,83 | 12,83 |
| Badge `on-vivid` / `danger` (jeton du thème : `#FF2A49` clair, `#FF6B7F` sombre) | 4,5 | 5,33 | 7,18 |
| Badge `on-vivid` / `danger` `#FF2A49` (si le jeton clair est utilisé en sombre) | 4,5 | 5,33 | 5,33 |
| Badge `on-vivid` / `warning` | 4,5 | 12,94 | 12,94 |
| Trait `danger` (choix faux, tirets 3 px) / surface-raised | 3 | 3,70 | 6,05 |
| Trait `danger` / surface | 3 | 3,41 | 6,79 |
| Trait `danger` `#FF2A49` utilisé en sombre / surface-raised | 3 | — | 4,48 |
| Contour « attendu » `ink` / surface-raised | 3 | 19,69 | 14,02 |
| Contour `designable` `primary` / surface-raised | 3 | 9,32 | 5,73 |
| Contour `designable` `primary` / surface | 3 | 8,59 | 6,44 |
| Survol `designable` : contour `primary` / `primary-soft` | 3 | 7,75 | 5,00 |
| Survol `designable` : texte `ink` / `primary-soft` | 4,5 | 16,37 | 12,21 |
| Puce de réponse et badge Agent : `primary-deep` / `primary-soft` | 4,5 | 12,85 | 8,39 |
| Bouton primaire `on-primary` / `primary` | 4,5 | 9,32 | 6,70 |
| Bouton secondaire `primary` / surface-raised | 4,5 | 9,32 | 5,73 |
| Sélection : contour `ink` / surface-raised | 3 | 19,69 | 14,02 |
| Pipeline surligné : filet `primary` / `primary-soft` | 3 | 7,75 | 5,00 |
| Onglet verrouillé `ink-soft` / `discipline-neutral-soft` | 4,5 | 7,53 | 7,36 |
| Carte indisponible `ink` / `discipline-neutral-soft` (sans opacité) | 4,5 | 17,18 | 12,80 |
| Carte indisponible `ink-soft` / neutral-soft (sans opacité) | 4,5 | 7,53 | 7,36 |
| Carte « grisée » avec opacité 0,5 (`ink`) | 4,5 | **3,61** | **4,32** |
| Carte « grisée » avec opacité 0,6 (`ink-soft`) | 4,5 | **2,89** | **3,60** |
| Bandeau carte : `ink` / `discipline-harness-soft` | 4,5 | 16,69 | 13,04 |
| Bandeau carte : `ink-soft` / surface-raised | 4,5 | 8,63 | 8,06 |
| Bandeau : trait `harness` / `harness-soft` | 3 | 4,72 | 4,93 |
| Bandeau : trait `harness` / surface-raised | 3 | 5,56 | 5,30 |
| Graphe : contour de commit `primary` / surface-raised | 3 | 9,32 | 5,73 |
| Graphe : arête `ink-soft` / surface-raised | 3 | 8,63 | 8,06 |
| Graphe : commit perdu `muted` tirets / surface | 3 | 3,12 | 5,50 |
| Graphe : commit perdu `muted` tirets / surface-raised | 3 | 3,38 | 4,90 |
| Graphe : libellé « perdu » `ink-soft` / surface | 4,5 | 7,96 | 9,05 |
| Ref distante : bordure `context` / `context-soft` | 3 | 4,50 | 5,73 |
| Ref distante : texte `ink` / `context-soft` | 4,5 | 17,16 | 11,98 |
| Étiquette tag/HEAD `on-ink` / `ink-fill` | 4,5 | 19,69 | 10,54 |
| Code `json-key` / surface-raised | 4,5 | 10,36 | 8,67 |
| Code `json-string` / surface-raised | 4,5 | 9,03 | 8,37 |
| Code `json-literal` / surface-raised | 4,5 | 7,34 | 9,55 |
| Sortie d'outil `ink` / `produced-soft` | 4,5 | 16,88 | 13,30 |
| Numéros de diff `ink-soft` / surface | 4,5 | 7,96 | 9,05 |
| Numéros de diff `ink-soft` / `accent-soft` | 4,5 | 7,71 | 6,19 |
| Numéros de diff `ink-soft` / `danger-soft` | 4,5 | 7,37 | 7,67 |
| `merge-blocked` `ink-soft` / neutral-soft | 4,5 | 7,53 | 7,36 |
| Anneau de focus `primary` / surface-raised | 3 | 9,32 | 5,73 |
| Anneau de focus `primary` / fond du terminal | 3 | **2,11** | 6,44 |
| Anneau de focus `primary` / bouton primaire (même fond) | 3 | **1,00** | **1,00** |
| Estompage 0,35 : `ink` / surface-raised | 4,5 | **2,34** | **2,90** |
| Estompage 0,35 : `ink-soft` / surface-raised | 4,5 | **1,81** | **2,16** |
| Point `accent` / surface-raised | 3 | **1,54** (décoratif) | 10,79 |
| Point `state-active` / `primary-soft` | 3 | **1,28** (décoratif) | 9,40 |
| Filet `warning` / surface-raised (décoratif) | 3 | **1,52** | 10,89 |
| Jaune réseau `#D9A400` / surface-raised | 3 | **2,27** | 8,72 |
| Bordure `line` / surface-raised (case de réponse, SHA) | 3 | **1,24** | **1,48** |
| Bordure `line` / surface (pane) | 3 | **1,15** | **1,66** |
| Tirets `line` / neutral-soft (carte indisponible) | 3 | **1,08** | **1,35** |

Opacité minimale pour 4,5:1 sur surface-raised : `ink` 0,56 (clair) / 0,51 (sombre) ; `ink-soft` 0,76 / 0,69.

Réponse au point ouvert n°11 : les couleurs sombres sur fond de terminal en thème clair sont conformes (invite 6,81:1, ✗ 7,18:1, stderr 12,66:1). Les estimations de DESIGN.md (6,8 et 7,2) sont confirmées pour le fond clair ; sur le fond sombre du terminal, 6,44 et 6,79:1.

## Résultat par point demandé
1. Contrastes : texte, terminal, états, correction, sélection, onglet verrouillé, lignes de catalogue et bandeau passent, hors A-02, A-06, A-07 et les cas décoratifs listés. Les lignes grisées du catalogue restent à 7,5:1 (`ink-soft`) ou 17:1 (`ink`) tant qu'aucune opacité n'est appliquée ; avec 0,5 ou 0,6 elles tombent sous 4,5:1 : écrire « grisé = fond neutral-soft, texte plein, sans `opacity` ».
2. Couleur seule : bien traité ; reste A-08 (anneaux) et A-21 (pilules).
3. Clavier : A-01, A-09, A-11, A-12, A-13, A-15.
4. Lecteurs d'écran : A-03, A-04, A-10, A-14.
5. Mouvement, temps, cibles : A-05, A-16, A-20 ; 2.2.1 conforme.
