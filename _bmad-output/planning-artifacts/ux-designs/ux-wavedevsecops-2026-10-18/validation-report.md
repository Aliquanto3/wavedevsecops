# Validation Report — WaveDevSecOps

- **DESIGN.md:** `_bmad-output\planning-artifacts\ux-designs\ux-wavedevsecops-2026-10-18\DESIGN.md`
- **EXPERIENCE.md:** `_bmad-output\planning-artifacts\ux-designs\ux-wavedevsecops-2026-10-18\EXPERIENCE.md`
- **Run at:** 2026-10-18T14:28:31+02:00

## Overall verdict
La paire est solide et utilisable comme contrat : tous les jetons de couleur sont en hex avec leur jumeau sombre, les quatre UJ ont un flux avec protagoniste, étapes numérotées et climax, les 21 décisions du memlog sont reflétées sans contradiction, et aucun point du PRD n'est contredit sur le fond. Aucun constat critique. Trois constats high à corriger avant l'architecture : la règle de correction d'une désignation entre types différents (ligne de diff contre commit), le contraste du focus clavier sur le terminal en thème clair, et plusieurs composants utilisés dans EXPERIENCE sans spec visuelle ni comportement. Les maquettes HTML sont à venir et ne sont pas comptées comme critiques.

La relecture d'accessibilité (WCAG 2.2 AA) déplace l'image : elle ajoute un constat critical (parcours clavier du mode désignation incomplet, A-01) et cinq high (estompage à 0,35, annonces lecteur d'écran, nom accessible du graphe, cibles trop petites, anneau de focus). Ces constats sont à traiter avant l'architecture, avec les trois high du rubric.

Décisions d'Anaël du 2026-10-18 : ensemble de bonnes réponses équivalentes pour la désignation ; désignation au clavier par parcours des vues et par liste filtrable. Une passe de correction des constats critical, high et medium est en cours.

Comptes : rubric critical 0 · high 3 · medium 12 · low 24 ; accessibilité critical 1 · high 5 · medium 10 · low 8 ; total critical 1 · high 8 · medium 22 · low 32.

## Category verdicts
- Flow coverage — adequate
- Token completeness — adequate
- Component coverage — thin
- State coverage — adequate
- Visual reference coverage — thin
- Bloat & overspecification — adequate
- Inheritance discipline — adequate
- Shape fit — adequate

## Findings by severity

### Critical (1)
**[Accessibilité]** — A-01 — Mode désignation : parcours clavier incomplet (2.1.1, A) (§ EXPERIENCE.md > Accessibility Floor (« Désignation au clavier ») ; > Désignation, points 2 à 4 ; > Flow 5 étape 4.)
(a) « Tab ne parcourt alors que les éléments désignables » : pendant que le mode est armé, la case de réponse (✕ de retrait), le champ SHA, « Valider ma réponse » et le bouton « Désignation active » ne sont pas atteignables par Tab. Le seul moyen de sortie est Échap, qui désarme, et la spec ne dit pas si la sélection placée survit. Le parcours « armer, parcourir, choisir, retirer, valider » n'est donc pas faisable de bout en bout. (b) Les lignes de diff (« chaque ligne est un élément liable et désignable ») et les blocs de sortie du terminal ne sont pas déclarés focalisables ; parcourir des centaines de lignes une à une par Tab est de plus impraticable. (c) Le Flow 5 fait désigner la sortie de gitleaks « dans le terminal » : or le terminal est une région `role="log"` et capte le clavier ; aucune façon de désigner une ligne ou un bloc au clavier n'est décrite. (d) « Le champ SHA reste l'alternative complète » est faux pour la preuve RSSI : il ne couvre que les commits, pas une sortie d'outil, un check, un SBOM ou un tag.
Fix: ne pas restreindre Tab. Le mode armé ajoute seulement un état (`aria-pressed`, annonce) et garde l'ordre normal ; chaque vue expose un seul arrêt de tabulation (focus itinérant) avec flèches pour parcourir ses éléments désignables, Entrée pour placer. Ajouter une commande « Aller à la case de réponse » (raccourci F6 étendu ou lien d'évitement). Faire de chaque bloc de sortie d'outil et de chaque ligne de diff un élément focalisable dans le focus itinérant de sa vue. Prévoir pour les preuves non-commit une alternative saisie ou liste : sélecteur « Choisir une preuve dans la liste » (liste plate des éléments désignables du type attendu, avec nom accessible), équivalent complet du clic. Préciser que Échap désarme sans effacer la case, et que le focus revient sur le bouton « Désigner ».


### High (8)
**[Flow coverage]** — Flow 2, étapes 6 à 8  (§ EXPERIENCE > Désignation, Flow 2 ; PRD FR-12)
Flow 2, étapes 6 à 8 : Camille désigne une ligne de diff (`API_KEY=…`), mais la vue entoure « le commit attendu ». La règle de correction n'est écrite nulle part : une ligne du bon commit est-elle une réponse juste ? Une branche qui contient le commit ? Le tableau « Éléments désignables par type de question » dit seulement que tous les éléments des types listés sont désignables. FR-12 exige une correction automatique contre le dépôt réel, donc l'architecture a besoin de cette règle d'équivalence (EXPERIENCE > Désignation, Flow 2 ; PRD FR-12).
Fix: ajouter à Désignation une règle explicite : l'élément attendu est déclaré par le scénario avec ses éléments équivalents (ligne de diff → commit qui l'introduit, ref → commit pointé). Dire si une réponse équivalente est « ✓ Votre choix » ou « ✗ ». Compléter l'étape 8 du Flow 2 en conséquence.

**[Token completeness]** — Focus  (§ Tab ou F6)
Focus : l'Accessibility Floor impose partout « focus visible `{colors.primary}` 2 px ». Le terminal est sombre dans les deux thèmes ; en thème clair, `#451DC7` sur `#0A0A14` donne environ 2,1:1, sous les 3:1 des traits porteurs de sens. Même problème sur `graph-head`, `pane-step`, `new-mark`, `tool-output` (étiquette) et `terminal-*`. Le digest WaveStack prévoit `on-ink` 2 px sur fond encre. Le terminal est une zone à focus clavier central (Tab ou F6).
Fix: ajouter un jeton `focus-on-ink` (= `on-ink` / `ink-dark`) et le règle dans Accessibility Floor et dans `terminal`.

**[Component coverage]** — Éléments utilisés dans EXPERIENCE sans ligne DESIGN ni, le plus souvent, sans ligne Component Patterns 
Éléments utilisés dans EXPERIENCE sans ligne DESIGN ni, le plus souvent, sans ligne Component Patterns : liste de choix du quiz (boutons radio + « Exécuter ma réponse », FR-15) ; bouton « Désigner dans les vues » (états inactif, armé, « Désignation active ») ; encart « État inattendu » (FR-11) ; encart d'échec de restauration ; fil de revue et approbations dans `pr-card` (journal de revue, FR-6 et FR-22) ; vue SBOM (désignable en FR-34) ; badges mode A/B et parcours du `scenario-panel` ; marque « Rétabli » (variante de `new-mark`) ; mention « Modifié hors de l'application » et choix « Garder ma version / Recharger » ; bouton « Exécuter le code (réseau possible) » ; carte et question de l'entretien RSSI ; aperçu du rapport. Sans spec, chaque story les invente.
Fix: ajouter une ligne DESIGN (jetons) et une ligne Component Patterns (comportement) pour chacun, ou les rattacher explicitement à un composant existant (ex. encarts = `diagnostic-row` + `state-pill`).

**[Accessibilité]** — A-02 — Estompage à 0,35 : texte illisible pendant la mise en correspondance (1.4.3) (§ DESIGN.md > `link-state` (`dimmed-opacity: 0.35`) ; EXPERIENCE.md > Interaction Primitives, State Patterns (Restauration en cours).)
survol ou focus estompe tous les éléments non liés à 0,35. Ratios obtenus : texte `ink` sur surface-raised 2,34:1 (clair) et 2,90:1 (sombre) ; `ink-soft` 1,81:1 et 2,16:1. Le texte estompé reste du contenu actif (pas un composant inactif exempté), et le focus clavier peut y rester longtemps.
Fix: ne pas utiliser `opacity` sur le texte. Estomper les décors (remplissages, traits) et garder le texte à ≥ 4,5:1 : opacité minimale 0,56 (`ink`, clair) / 0,51 (sombre) ; 0,76 / 0,69 pour `ink-soft`. En pratique prendre 0,8 et ajouter un signal non coloré pour les éléments liés (déjà l'anneau). Même règle pour l'état « Restauration en cours » (composants inactifs : exemptés, mais lisibles à 0,6 minimum pour que le message reste lu).

**[Accessibilité]** — A-03 — Annonces lecteur d'écran absentes pour les changements d'état centraux (4.1.3, 1.3.1) (§ EXPERIENCE.md > State Patterns (Synchro après commande), Component Patterns (`verdict-mark`, `new-mark`, `scenario-panel`), Accessibility Floor.)
seule l'explication attachée (`explain-popover`) est dite `aria-live="polite"`. Rien n'annonce : la mise à jour des vues après une commande (« Nouveau » posé), la validation d'étape et l'apparition de l'explication dans le panneau, la correction (« Attendu » / « Votre choix » posés dans d'autres vues, alors que le focus reste sur « Valider »), le passage de `step-progress`, le refus « SHA inconnu », le bilan. Un utilisateur de lecteur d'écran ne sait pas que la commande a eu un effet visuel.
Fix: une région `role="status"` (polite) unique, alimentée dans l'ordre FR-4 : « Commande terminée, code 0. Vues mises à jour : 1 commit et 1 branche nouveaux. Étape 3 validée. » ; l'explication d'étape et le verdict en `role="status"` dans le panneau (l'explication reste après les vues). Les `verdict-mark` entrent dans le nom accessible de l'élément (« Commit a1b2c3d, attendu » ; « votre choix, incorrect »). Refus de commande et échec de restauration en `role="alert"`.

**[Accessibilité]** — A-04 — Graphe git : nom accessible incomplet et relations non exposées (1.3.1, 4.1.2) (§ EXPERIENCE.md > Accessibility Floor (« Noms accessibles ») ; Component Patterns (`graph-*`).)
l'exemple de nom (« Commit a1b2c3d, Add config, par l'agent, pointé par feature et HEAD ») ne couvre ni les parents/enfants (la topologie est ce qu'on apprend : divergence, fusion, commit perdu), ni les états « Nouveau », « perdu · visible par reflog », « origin/… » (distant), « détachée », « sélectionné », « lié », « désignable ». Les arêtes (`graph-edge`) n'ont aucun équivalent texte.
Fix: donner à chaque nœud un nom construit par gabarit (SHA, message, auteur, parents « parent : 9f8e7d6 », refs locales, refs distantes, tags, états) et exposer la relation parent par `aria-describedby`/liste. Fournir pour la vue 1 une alternative textuelle équivalente : tableau ou liste « Commits » (SHA, message, parents, refs, état) basculable ou toujours présent en rôle `table` caché visuellement, équivalent de `git log --all --graph`. Les refs (branches, tags, distantes) ont rôle et nom : « branche locale feature », « référence distante origin/main », « tag v0.1.0 ».

**[Accessibilité]** — A-05 — Cibles trop petites : lignes de diff et disques du graphe (2.5.8) (§ DESIGN.md > `graph-commit` (disque de 14 px), `diff-view` (13 px × 1,5 = 19,5 px de hauteur de ligne) ; EXPERIENCE.md > `diff-view`, Désignation.)
les lignes de diff sont cliquables et désignables, empilées sans espace : 19,5 px de haut, sous 24 px, sans exception d'espacement possible (cibles contiguës). Le disque de commit fait 14 px ; l'exception d'espacement ne tient que si aucun autre cible n'est dans un cercle de 24 px. Contredit `hit-target-min` de 32 px posé par la spec.
Fix: hauteur de ligne de diff interactive ≥ 24 px (idéalement 28 px) ; zone cliquable du nœud de graphe = disque + SHA + message, ≥ 24 × 24 px, avec espacement vertical ≥ 28 px entre commits ; l'indication visuelle reste de 14 px mais la zone de clic est étendue. Vérifier de même la pastille d'étape, les puces de référence, « i » (≥ 24 px).

**[Accessibilité]** — A-06 — Anneau de focus : contraste et distinction insuffisants (2.4.7, 1.4.11) (§ EXPERIENCE.md > Accessibility Floor (« focus visible `{colors.primary}` 2 px ») ; DESIGN.md > `terminal`, `button-primary`, `graph-head`.)
en thème clair, l'anneau `primary` `#451DC7` sur le fond du terminal `#0A0A14` ne fait que 2,11:1 (< 3:1). Sur `button-primary` (fond `primary`) ou sur `graph-head` / `new-mark` (fond encre), un anneau collé de même couleur que le fond est nul (1,00:1) ; aucun décalage n'est spécifié hors `designable`. En sombre, l'anneau `primary-dark` passe partout (≥ 5,0:1).
Fix: anneau double (2 px `ink` + 2 px `surface-raised`, ou décalage de 2 px) ; dans le terminal, anneau `on-ink` (blanc, 19,7:1) ou `primary-dark` en thème clair. Ajouter à `tests/test_web_tokens.py` : anneau de focus ≥ 3:1 sur chaque surface où un élément focalisable peut se trouver.


### Medium (22)
**[Flow coverage]** — Station 4 (FR-29 à FR-31, v0.3) 
Station 4 (FR-29 à FR-31, v0.3) : aucun flux, aucune surface dans l'IA, aucun composant (tag annoté avec refus non SemVer, artefact construit, staging et prod simulée, promotion avec approbation, rollback). Seuls « Tag (v0.3) » dans Correspondances et le bandeau « 4 Livraison » existent. Le PRD renvoie le parcours de la station 4 au découpage en stories, donc ce n'est pas une contradiction, mais l'UX est incomplète pour v0.3.
Fix: l'écrire comme question non bloquante et prévoir une mise à jour de l'UX avant les stories v0.3.

**[Flow coverage]** — Catalogue et parcours (FR-16, FR-9) 
Catalogue et parcours (FR-16, FR-9) : le memlog décide « sections Socle git / Stations / Savoir en parler » et « choix du parcours ». EXPERIENCE ne mentionne que « Savoir en parler ». Le choix initial du parcours (Flow 1 le suppose fait), le changement de parcours et la progression propre à chaque parcours n'ont ni composant ni règle. La mise en page du catalogue n'a pas de section dédiée, contrairement au Diagnostic.
Fix: section « Catalogue » : sections, sélecteur de parcours (composant, comportement, état au premier lancement), lecture de l'état A/B par parcours.

**[Token completeness]** — `{colors.warning}` et `{colors.hosting-network}` ont la même valeur `#FFCA4A` mais deux sens  (§ `state-pill`)
`{colors.warning}` et `{colors.hosting-network}` ont la même valeur `#FFCA4A` mais deux sens : « état provisoire » (bandeau du quiz, diagnostic) et « sort du poste » (FR-17). Le tableau Colors annonce « une couleur = un sens » ; le Do dit « Jaune réservé à l'état provisoire et à la sortie du poste » ; le digest WaveStack dit « jamais jaune pour un état » (`state-pill`).
Fix: soit un seul sens par teinte (réseau en `discipline-network` `#D9A400` + icône), soit assumer l'exception dans la table avec son motif.

**[Token completeness]** — Terminal 
Terminal : `terminal-prompt`, `terminal-exit-error`, `terminal-app-message` et `terminal-refused` utilisent `primary-dark`, `danger-dark`, `surface-dark` dans le thème clair. Cela rompt la règle « chaque couleur par un jeton, avec son jumeau sombre » et la lecture du suffixe `-dark` comme thème. Un développeur peut les basculer avec le thème.
Fix: jetons dédiés (`terminal-bg`, `terminal-fg`, `terminal-accent`, `terminal-danger`, valeurs identiques dans les deux thèmes).

**[Token completeness]** — Contrastes des ajouts non énoncés 
Contrastes des ajouts non énoncés : `on-vivid` sur `danger` (badge, environ 5,4:1), `ink-soft` sur `discipline-neutral-soft`, `primary-deep` sur `primary-soft` en sombre, `on-ink-soft` sur terminal. Seuls les contrastes du terminal sont estimés. La question 11 parle du « thème clair » alors que les estimations 6,8 et 7,2:1 sont déjà fournies pour le fond `ink-fill`.
Fix: tableau des combinaisons porteuses nouvelles avec ratio ; reformuler la question 11.

**[State coverage]** — Échecs d'infrastructure sans traitement 
Échecs d'infrastructure sans traitement : bac à sable impossible à créer (dossier non inscriptible, disque plein), serveur local arrêté pendant que l'onglet est ouvert (console fermée), port occupé au lancement. NFR-7 exige un message plutôt qu'un plantage.
Fix: ajouter deux lignes à State Patterns (« Bac à sable indisponible », « Application arrêtée »).

**[State coverage]** — « Reprendre » (catalogue) et redémarrage en cours de scénario 
« Reprendre » (catalogue) et redémarrage en cours de scénario : le bac à sable est-il conservé, ramené à l'étape, ou le scénario recommencé ? FR-20 ne garde que score et indices. Non spécifié, alors que « Reprendre » est un élément du memlog.
Fix: règle explicite (par exemple : reprise = scénario rouvert à son état initial, ou état restauré).

**[State coverage]** — Barrières en échec en v0.2  (§ affiché ou non ?)
Barrières en échec en v0.2 : refus du hook pre-commit gitleaks (FR-21), test cassé ou lint prévu, sont présents en exemple de ton mais n'ont ni état ni flux (où apparaît le refus ? lié au `graph-commit` absent ? explication ?). Quiz : une bonne réponse qui modifie l'état (ex. `reset --soft`) n'a pas de règle pour le bandeau (affiché ou non ?).

**[Visual reference coverage]** — DESIGN.md annonce « Maquettes HTML des écrans clés 
DESIGN.md annonce « Maquettes HTML des écrans clés : à venir dans `mockups/` » sans les nommer. Plusieurs hypothèses (proportions de la disposition A, `scenario-panel-width`, `chain-band-height`, ordre de repli) dépendent de ces maquettes.
Fix: lister les quatre maquettes prévues dans les deux spines, avec la section qu'elles illustrent, dès leur création ; garder la phrase « les spines priment » une seule fois.

**[Inheritance discipline]** — Numérotation en collision  (§ `pane-step` contre numéro de station)
Numérotation en collision : les vues sont numérotées 1 à 4 (`pane-step`) et les stations du bandeau aussi 1 à 4 (« 1 Poste local » … « 4 Livraison »), affichées ensemble à l'écran en v0.2. Les tableaux (Correspondances : « Dépôt local (1) » et « Station 2 ») et les flux mélangent les deux. Risque de confusion pour l'apprenant et pour le code (`pane-step` contre numéro de station).
Fix: nommer les stations par lettre ou par nom seulement, ou préfixer « Étape » / « Station » partout, et le dire dans DESIGN.

**[Shape fit]** — « Inspiration & Anti-patterns » est absent alors que les sources montrent des produits de référence et des… (§ aucun compteur d'indices, solution non copiable, désignation à un essai)
« Inspiration & Anti-patterns » est absent alors que les sources montrent des produits de référence et des rejets : Learn Git Branching, Oh My Git!, Git-it, Githug, GitHub Skills (addendum), help avoidance et menus contournés par essais (addendum, pédagogie). Une section courte donnerait aux stories le « pourquoi » des choix (aucun compteur d'indices, solution non copiable, désignation à un essai).

**[Shape fit]** — Capacité à 1920×1080 (hypothèse déjà marquée) 
Capacité à 1920×1080 (hypothèse déjà marquée) : rangée haute de 40 % (≈ 380 px) pour la vue 2 qui doit tenir refs, `pr-card`, six `pr-check`, approbations, `merge-blocked` et ses raisons ; vue Code de 33 % (≈ 310 px) pour l'éditeur de conflit et `pipeline-tabs`. Le contenu déborde probablement. Le mode focus ⛶ atténue, mais Flow 2 et Flow 4 s'y déroulent.
Fix: tester sur la maquette « espace de travail » ; sinon prévoir un défilement interne et un ordre de contenu prioritaire par vue.

**[Accessibilité]** — A-07 — Bordures `line` quasi invisibles comme limites de composants (1.4.11) (§ DESIGN.md > `answer-slot` (bordure `line` en tirets), `reset-button`, `pane`, `scenario-card` indisponible ; champ SHA (aucune bordure spécifiée).)
`line` sur surface-raised 1,24:1 (clair), 1,48:1 (sombre) ; sur neutral-soft 1,08:1 et 1,35:1. La case de réponse vide, le champ SHA et le bouton « Recommencer » n'ont donc pas de limite visible à 3:1. Le texte d'aide les identifie en partie, mais un champ de saisie sans bord ne passe pas.
Fix: bordure de champ et de case (vide et pleine) en `muted` ou `ink-soft` (3:1 minimum : `muted` fait 3,38:1 en clair, 4,90:1 en sombre sur surface-raised) ; spécifier explicitement le champ SHA.

**[Accessibilité]** — A-08 — Anneau « lié » = même teinte que le focus, sélection distinguée par la couleur seule (1.4.1, 2.4.7) (§ DESIGN.md > `link-state` (anneau 2 px de couleur de discipline), `designable` ; Colors (`discipline-prompt` = `primary`).)
pour les éléments du dépôt local, l'anneau « lié » est violet `primary`, exactement la couleur de l'anneau de focus et du contour `designable`. Anneau lié, focus, contour désignable et sélection `ink` ne se distinguent que par teinte ou par pointillés (désignable). Un utilisateur qui ne distingue pas ces teintes ne sait pas où est son focus.
Fix: différencier par la forme : focus = anneau double plein décalé ; lié = fond teinté + coche ou marque « lié » ; sélection = contour épais ink + marque ● ; désignable = tirets. Ajouter un état texte (`aria-selected`, nom « lié à… »).

**[Accessibilité]** — A-09 — Carte de la chaîne dépliée : gestion du focus non spécifiée (2.4.11, 4.1.2, 2.1.1) (§ EXPERIENCE.md > Disposition A (« par-dessus les vues »), `chain-band` / `chain-map`.)
la carte se superpose aux vues, sans modale. Tab peut alors atteindre des éléments cachés sous la carte (focus entièrement masqué, 2.4.11). Aucun `aria-expanded` sur « Carte ▾ », aucune règle de focus à l'ouverture (premier nœud ? bouton ?) ni de retour du focus à la fermeture par Échap. La station courante (« Vous êtes ici ») n'a pas d'`aria-current`.
Fix: « Carte ▾ » = bouton `aria-expanded` + `aria-controls` ; à l'ouverture, focus sur le titre ou la station demandée ; vues dessous `inert` ; Échap ferme et rend le focus au bouton ; `aria-current="step"` sur la station courante ; zones de la carte en régions nommées, nœuds en liste.

**[Accessibilité]** — A-10 — Terminal : flux de lecture et distinction stdout/stderr pour les lecteurs d'écran (1.3.1, 4.1.3, 3.1.2) (§ EXPERIENCE.md > Accessibility Floor (« Terminal ») ; State Patterns (Commande refusée) ; Voice and Tone (langue de git).)
(a) stderr se distingue seulement par une teinte voisine (`on-ink-soft` contre `on-ink`) et un filet de 2 px ; « annoncés comme tels » n'est pas réalisé par une technique (préfixe masqué). (b) `role="log"` est poli : une sortie de `git log` de plusieurs centaines de lignes inonde le lecteur ; « refus » doit être immédiat (la règle générale dit « annoncés tout de suite ») mais il est écrit dans un log poli. (c) Une sortie de git en anglais (MinGit) dans une page `lang="fr"` est mal prononcée. (d) Le terminal « lecture seule pendant le quiz » n'est pas exposé (`aria-readonly`, raison reliée).
Fix: préfixe masqué visuellement « erreur standard : » devant chaque ligne stderr, « code de sortie 128, échec » sur la ligne finale ; garder le log poli mais résumer en fin de commande (voir A-03) avec `aria-atomic` sur le résumé, et `role="alert"` pour `terminal-refused` ; `lang="en"` sur les blocs de sortie anglais ; `aria-readonly="true"` + `aria-describedby` sur la saisie quand elle est restreinte.

**[Accessibilité]** — A-11 — Onglets d'indice verrouillés et déblocage dépendant du temps (4.1.2, 4.1.3, 2.2.1) (§ EXPERIENCE.md > Indices à paliers ; DESIGN.md > `hint-tabs`.)
l'onglet verrouillé est « grisé » : si implémenté avec `disabled`, il sort de l'ordre de tabulation et la condition (« Disponible après un essai ou un moment de lecture ») n'est pas atteinte par un lecteur d'écran. Le déblocage se produit sans événement annoncé. Pas de motif `role="tablist"` précisé (flèches, `aria-selected`). Voir « Temps » : pas de violation de 2.2.1, la durée interne ne coupe rien.
Fix: `role="tablist"`/`tab`/`tabpanel`, onglet verrouillé en `aria-disabled="true"` toujours focalisable, condition reliée par `aria-describedby`, déblocage annoncé en `role="status"` (« La solution est disponible. ») ; ne pas cacher le cadenas, l'icône a un nom (« verrouillé »).

**[Accessibilité]** — A-12 — `quiz-banner` : position, annonce et retour (4.1.3, 2.4.3, 3.2.x) (§ EXPERIENCE.md > Quiz à exécution réelle ; Component Patterns (`quiz-banner`).)
le bandeau est « au-dessus des vues », donc probablement avant le panneau dans l'ordre du DOM, alors que l'utilisateur est dans le panneau quand il l'a déclenché. L'apparition n'est pas annoncée ; le focus reste sur « Exécuter ma réponse ». Le bouton « J'ai compris, rétablir l'état » n'est pas dans l'ordre de lecture du flux d'action. La couleur d'avertissement est accompagnée de l'icône ⚠ et de texte : conforme à 1.4.1.
Fix: `role="status"` (ou `alert` : l'état est bloquant pour les commandes), contenu texte complet ; focus déplacé sur le bandeau ou lien « Aller au bandeau » dans le panneau ; ordre du DOM : bandeau juste avant le panneau ; après rétablissement, focus sur le panneau (« Rétabli »).

**[Accessibilité]** — A-13 — Terminal : piège potentiel et sortie du focus (2.1.2, 2.4.3, 2.1.4) (§ EXPERIENCE.md > Interaction Primitives (« Terminal »), Component Patterns (`terminal`, ↑/↓, Ctrl+C, Ctrl+L), Accessibility Floor.)
pas de piège aujourd'hui (Tab sort, F6 aussi), mais : (a) « Échap rend le focus au document » : cible non définie (où atterrit-il ?) ; et Échap est aussi dans la hiérarchie Échap (popover, carte, désignation...) : un Échap dans le terminal agit-il sur les deux ? (b) la complétion est exclue en v0.1 mais une v ultérieure qui capterait Tab créerait un piège ; (c) Ctrl+C/Ctrl+L s'ajoutent aux raccourcis du navigateur (Ctrl+L = barre d'adresse) : les raccourcis à caractère unique sont absents, ce qui est bien.
Fix: écrire que Tab quitte toujours le terminal ; Échap met le focus sur le titre de la vue 4 (et uniquement cela) ; hiérarchie Échap évaluée seulement hors terminal ; garder Tab libre si une complétion arrive (utiliser Ctrl+Espace). Ajouter dans la vue un lien d'évitement « Aller à la vue suivante ».

**[Accessibilité]** — A-14 — Correspondances au focus : annonce bavarde et doublonnée (4.1.3) (§ EXPERIENCE.md > Accessibility Floor (« Correspondances au clavier »).)
une région `aria-live="polite"` résume « 3 éléments liés : ... » à chaque focus. Avec un focus itinérant dans le graphe, chaque flèche déclenche l'annonce de l'élément (nom accessible) puis celle de la région : double lecture, et file d'attente.
Fix: lier le résumé par `aria-describedby` au nœud focalisé, ou n'annoncer qu'après une pause (≈ 500 ms) et sur sélection (Entrée) seulement ; garder la liste des correspondants consultable par une touche (« L » ou lien « Voir les éléments liés ») plutôt qu'à chaque déplacement.

**[Accessibilité]** — A-15 — Masquage des vues et poignées : focus et alternative au glisser (2.4.3, 4.1.2, 2.5.7) (§ EXPERIENCE.md > Masquage et agrandissement.)
« — » masque une vue (focus perdu sur un élément disparu) ; « ⛶ » mode focus (Échap) ; la poignée de gouttière n'est décrite qu'au clavier par pas de 16 px et double-clic. Rôle ARIA absent. Le glisser a une alternative clavier, mais pas d'alternative à pointeur unique non glissé (2.5.7) hormis le double-clic de réinitialisation.
Fix: après « — », focus sur la puce « + Nom » ; après « + », focus sur le titre de la vue ; poignée `role="separator"` avec `aria-valuenow/min/max` et flèches ; ajouter boutons « Élargir » / « Réduire » dans « Volets ▾ » comme alternative à pointeur unique.

**[Accessibilité]** — A-16 — Réflexion et zoom 400 % (1.4.10, 1.4.4) (§ EXPERIENCE.md > Responsive & Platform (« Très petite (< 1280 px) : mode focus seul » ; « à 125 % … repli »).)
à 200 % ou 400 % de zoom sur 1920 px, la fenêtre équivaut à 960 ou 480 px CSS : le mode focus doit alors suffire sans défilement horizontal pour le contenu non bidimensionnel (panneau, explications, catalogue, diagnostic). La spec écarte « mobile » mais le critère s'applique au zoom.
Fix: ajouter la règle « à 320 px CSS (400 %), le panneau Scénario et les pages annexes se lisent sur une colonne sans défilement horizontal ; seuls le graphe, le diff et le terminal peuvent défiler dans les deux sens » ; tester à 200 % et 400 %.


### Low (32)
**[Flow coverage]** — Flow 3 n'a pas de chemin d'échec explicite (le flux est lui-même un échec ; étape 5 couvre l'outil manquant). (§ le flux est lui-même un échec ; étape 5 couvre l'outil manquant)
Flow 3 n'a pas de chemin d'échec explicite (le flux est lui-même un échec ; étape 5 couvre l'outil manquant).
Fix: ajouter une ligne « Échec : le navigateur n'atteint toujours pas 127.0.0.1 » avec repli pywebview.

**[Flow coverage]** — Flow 1, étape 7 
Flow 1, étape 7 : « 2 sur 3 du premier coup » alors que le flux ne montre qu'un quiz et que SM-1 vise ≥ 80 %. Un lecteur peut y voir un conflit.
Fix: préciser que le choix était volontaire et que le scénario compte trois quiz.

**[Token completeness]** — Valeurs brutes hors jetons 
Valeurs brutes hors jetons : `420px` (`explain-popover`), `2px discipline color` (`link-state`), disque de 14 px et pas de 16 px en prose.
Fix: jetons de spacing pour `popover-max-width` et `graph-node-size`.

**[Token completeness]** — `state-active` = `state-ok` = `accent` (`#04F06A`) 
`state-active` = `state-ok` = `accent` (`#04F06A`) : « en cours » et « réussi » partagent la même teinte, distingués par la forme et le texte. À noter dans les Do's.

**[Component coverage]** — Component Patterns n'a pas de ligne pour `designable` (décrit dans Désignation seulement) ni pour… (§ décrit dans l'IA)
Component Patterns n'a pas de ligne pour `designable` (décrit dans Désignation seulement) ni pour `site-nav` (décrit dans l'IA).

**[Component coverage]** — `explain-popover` 
`explain-popover` : le déclencheur « i » (disque cerclé du `scenario-info` WaveStack) n'est décrit que par renvoi au digest ; le memlog note qu'il n'existe pas de bulle dédiée chez WaveStack.
Fix: une ligne sur l'anatomie du déclencheur.

**[Component coverage]** — `terminal`  (§ NFR-7 : jamais de plantage)
`terminal` : « Pas de pager » et « sortie complète » sans plafond. Prévoir une borne de sortie ou de mémoire du log (NFR-7 : jamais de plantage).

**[State coverage]** — États vides absents pour le catalogue au premier lancement, pour la vue Code sans fichier sélectionné et…
États vides absents pour le catalogue au premier lancement, pour la vue Code sans fichier sélectionné et pour l'export du rapport sans progression. Échec d'écriture du fichier exporté non traité.

**[State coverage]** — Pipeline 
Pipeline : check qui échoue par expiration ou outil qui plante (distinct d'un défaut prévu) non distingué.

**[Visual reference coverage]** — `wavestack-digest.md` est cité en blockquote de DESIGN.md et en frontmatter de EXPERIENCE.md, mais pas lié…
`wavestack-digest.md` est cité en blockquote de DESIGN.md et en frontmatter de EXPERIENCE.md, mais pas lié dans les sections qui en dépendent (« digest §2 », « digest §3 » sans lien). Le digest est le seul accès aux spécifications WaveStack reprises : à lier à chaque renvoi.

**[Visual reference coverage]** — La règle « les spines priment » est écrite deux fois (une par fichier) ; acceptable, à n'écrire qu'une…
La règle « les spines priment » est écrite deux fois (une par fichier) ; acceptable, à n'écrire qu'une fois si une rubrique commune est ajoutée.

**[Bloat & overspecification]** — DESIGN.md Components décrit chaque composant deux fois (YAML puis prose) ; les deux concordent aujourd'hui…
DESIGN.md Components décrit chaque composant deux fois (YAML puis prose) ; les deux concordent aujourd'hui (aucune dérive trouvée), mais le risque de dérive est réel avec une cinquantaine de composants.
Fix: garder la prose pour les règles qui ne sont pas des jetons (formes, tirets, contenus).

**[Bloat & overspecification]** — EXPERIENCE cite des « Décisions d'Anaël (memlog) » dans le texte (Désignation, Indices, Quiz) 
EXPERIENCE cite des « Décisions d'Anaël (memlog) » dans le texte (Désignation, Indices, Quiz) : une provenance de processus qui ne sert pas au développeur, et le memlog n'est pas dans `sources`. À retirer ou à remplacer par un renvoi au FR.

**[Bloat & overspecification]** — Les 8 questions non bloquantes répètent des `[ASSUMPTION]` en ligne (proportions, ordre de repli,…
Les 8 questions non bloquantes répètent des `[ASSUMPTION]` en ligne (proportions, ordre de repli, désignation armée, approbations). À conserver, mais indiquer l'emplacement de l'hypothèse pour éviter une double mise à jour.

**[Bloat & overspecification]** — Foundation reformule NFR-1, NFR-8, NFR-9, NFR-12 ; acceptable car résumé de contexte, à garder à une ligne…
Foundation reformule NFR-1, NFR-8, NFR-9, NFR-12 ; acceptable car résumé de contexte, à garder à une ligne chacun.

**[Inheritance discipline]** — Terme « score du premier passage » (Recommencer, FR-10) contre « score du premier coup » (glossaire,…
Terme « score du premier passage » (Recommencer, FR-10) contre « score du premier coup » (glossaire, restauration échouée, bilan) dans le même fichier.
Fix: un seul terme, le glossaire du PRD.

**[Inheritance discipline]** — « Fil de revue (journal de revue) » dans `pr-card` 
« Fil de revue (journal de revue) » dans `pr-card` : deux noms pour un objet, le glossaire dit « journal de revue ».

**[Inheritance discipline]** — Fiche  (§ FR-35 : au plus tard v1.0, v0.3 au plus tôt)
Fiche : l'en-tête annonce « Fiche (v1.0) », l'IA « v0.3 à v1.0 » (FR-35 : au plus tard v1.0, v0.3 au plus tôt).

**[Inheritance discipline]** — DESIGN.md n'a pas de `sources` en frontmatter (EXPERIENCE.md en a). (§ EXPERIENCE.md en a)
DESIGN.md n'a pas de `sources` en frontmatter (EXPERIENCE.md en a).

**[Inheritance discipline]** — FR-36 dit « un fichier » ; l'UX et le memlog décident deux fichiers (HTML + CSV)
FR-36 dit « un fichier » ; l'UX et le memlog décident deux fichiers (HTML + CSV). Pas une contradiction (décision d'Anaël, hypothèse confirmée), à noter pour la traçabilité.

**[Inheritance discipline]** — Glossaire 
Glossaire : la carte de la chaîne est une « vue » ; l'UX en fait un bandeau et une carte dépliée hors des vues numérotées et du menu « Volets ». Décision du memlog (donc conforme), mais FR-32 « vue supplémentaire » s'en lit autrement.

**[Shape fit]** — Accessibility Floor suit les sections inventées au lieu d'être groupé avec Interaction Primitives ;…
Accessibility Floor suit les sections inventées au lieu d'être groupé avec Interaction Primitives ; l'ordre des sections par défaut n'est pas imposé, mais les défauts requis sont dispersés.

**[Shape fit]** — Responsive 
Responsive : « < 1280 px = mode focus seul » alors que le panneau Scénario ne se masque pas : indiquer comment panneau et vue focus se partagent l'écran.

**[Shape fit]** — Mode projection 
Mode projection : décision de ne pas le reprendre avant le mode formateur, alors que UJ-3 se déroule en atelier. Question 12 ouverte, cohérente avec le PRD.

**[Accessibilité]** — A-17 — Règle « muted jamais en texte » (1.4.3) (§ DESIGN.md > Colors, `state-unavailable`, `discipline-neutral`.)
`muted` `#8A8A9E` fait 3,38:1 sur surface-raised et 3,12:1 sur surface en clair (4,90 et 5,50 en sombre). Il sert de filet et de tirets (3:1 : OK) mais pas de texte. La spec utilise bien `ink-soft` pour les textes grisés ; la règle n'est pas écrite.
Fix: ajouter aux Don't : « `muted` et `discipline-neutral` ne servent jamais pour du texte ni pour l'icône seule en thème clair ».

**[Accessibilité]** — A-18 — Couleurs jaunes en clair sous 3:1 comme limite (1.4.11) (§ DESIGN.md > `quiz-banner` (filet `warning`), Colors (`hosting-network`, `discipline-network`).)
`warning` sur blanc 1,52:1, `discipline-network` `#D9A400` sur blanc 2,27:1. Le filet du bandeau est décoratif (icône ⚠ et texte portent le sens : conforme). Le bouton « Exécuter le code (réseau possible) » marqué en jaune doit avoir une limite à 3:1 s'il est identifié par sa bordure.
Fix: bordure et icône du bouton réseau en `ink` ou `ink-soft`, la pastille jaune reste un complément ; vérifier qu'aucun filet jaune n'est seul porteur.

**[Accessibilité]** — A-19 — Segments de `step-progress` : relecture au survol seul (1.4.13, 2.1.1) (§ EXPERIENCE.md > Component Patterns (`step-progress`, « Un segment terminé se survole »).)
information donnée au seul survol, ce que la spec bannit elle-même (Interaction Primitives). Pas de rôle clavier.
Fix: segments en boutons focalisables ouvrant la consigne dans une région déclarée (comme `explain-popover`) ; barre en `role="list"`, état « terminé / courante / à venir » dans le nom.

**[Accessibilité]** — A-20 — Mouvement et mise à jour automatique (2.2.2, 2.3.3) (§ EXPERIENCE.md > Accessibility Floor (« Mouvement réduit »), State Patterns (chronomètres).)
`prefers-reduced-motion` est traité (point fixe, transitions coupées, défilement sans animation). Il reste : chronomètres qui s'incrémentent (« En cours… 3 s », « Modifié il y a 2 s ») pendant plus de 5 s ; le chronomètre ne doit pas être annoncé chaque seconde. Pas de bascule manuelle dans « Affichage ▾ ».
Fix: retirer le chronomètre de toute région live (annoncer « En cours » une fois, « Terminé » à la fin) ; ajouter dans « Affichage ▾ » un réglage « Réduire les animations » qui complète la préférence système ; le point « en cours » fixe reste accompagné du mot.

**[Accessibilité]** — A-21 — Branche locale, branche distante et tag : forme voisine (1.4.1) (§ DESIGN.md > Shapes, `graph-branch`, `graph-remote-ref`.)
branche locale et ref distante sont deux pilules ; seuls le préfixe « origin/ » et la teinte (vert d'eau, bordure 2 px) les distinguent. Le préfixe texte suffit pour 1.4.1, mais la différence visuelle est faible en niveaux de gris. Commit de l'agent / collègue : badges texte, conforme. Commit perdu : tirets + libellé, conforme.
Fix: ajouter une icône (ordinateur / nuage) dans la pilule distante, et une forme distincte (pilule à bord plein pour local, pilule à double bord pour distant).

**[Accessibilité]** — A-22 — Champ SHA et bouton « Valider » inactif (3.3.1, 3.3.3, 4.1.2) (§ EXPERIENCE.md > Désignation (point 4), Entretien RSSI.)
les messages (« Aucun commit ne correspond… », « Il manque la preuve… ») sont donnés mais pas leur technique : `role="alert"`/`aria-live`, `aria-invalid`, `aria-describedby`. Un `button disabled` quitte la tabulation, le motif n'est alors pas lu.
Fix: `aria-disabled="true"` + `aria-describedby` vers le texte du motif ; erreur de SHA en `role="alert"` avec `aria-invalid` ; l'aperçu du SHA résolu en `role="status"`.

**[Accessibilité]** — A-23 — `diagnostic-badge` et lignes de diagnostic (1.3.1, 1.4.1) (§ DESIGN.md > `diagnostic-badge` ; EXPERIENCE.md > Diagnostic.)
la pastille rouge ne porte qu'un nombre. États ✓ / ⚠ / ✗ + mots : conforme. « ligne rouge » pour git absent est accompagné de la cause et de l'action : conforme.
Fix: nom accessible « Diagnostic, 2 outils absents ou trop anciens » ; tableau avec en-têtes `th` et `scope`, état dans une cellule texte.

**[Accessibilité]** — A-24 — Éléments purement décoratifs sous 3:1 (information de repli présente) (§ DESIGN.md > `pr-check` en cours (point `state-active` `#04F06A` sur `primary-soft` 1,28:1 en clair), `scenario-card` indisponible (tirets `line` 1,08:1), `pane` (bordure `line` 1,15:1).)
sans conséquence tant que l'état est dit aussi par un mot (« En cours », « Indisponible », raison visible). À noter pour que personne ne s'appuie ensuite sur ces éléments comme seul signal.
Fix: consigner dans DESIGN.md que ces éléments sont décoratifs ; `aria-hidden="true"` sur le point.

## Mechanical notes
- **Numérotation des questions non bloquantes (low)** : EXPERIENCE > Questions ouvertes commence à 5. Les questions bloquantes 1 à 4 ont été tranchées et ne sont plus listées, donc la numérotation commence à 5 sans explication. *Fix:* renuméroter à partir de 1 ou ajouter « (1 à 4 tranchées, voir memlog) ».
- Références croisées : toutes résolues (Information Architecture, Désignation, Indices à paliers, Quiz à exécution réelle, Diagnostic, Pipeline simulé, Vocabulaire, Exports, Responsive & Platform, State Patterns > Commande refusée).
- Chemin `sources` : résolu depuis `ux-designs/ux-wavedevsecops-2026-10-18/` vers `planning-artifacts/prds/prd-wavedevsecops-2026-10-18/` (prd.md, addendum.md) ; `imports/wavestack-digest.md` présent.
- Syntaxe : aucun diagramme Mermaid ; la disposition A est un schéma ASCII lisible. Cellule « Version requise » du Diagnostic avec « … » à compléter (gitleaks) ; versions minimales marquées `[ASSUMPTION]`.
- Colonne du tableau des proportions : 40 + 33 + 27 = 100 % ; 55 + 45 = 100 % ; cohérent.

## Reviewer files
- `review-rubric.md`
- `review-accessibilite.md`
