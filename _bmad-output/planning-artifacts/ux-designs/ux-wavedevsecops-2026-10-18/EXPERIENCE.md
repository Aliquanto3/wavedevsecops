---
title: WaveDevSecOps
status: final
created: 2026-10-18
updated: 2026-10-18
sources:
  - ../../prds/prd-wavedevsecops-2026-10-18/prd.md
  - ../../prds/prd-wavedevsecops-2026-10-18/addendum.md
  - imports/wavestack-digest.md
  - .memlog.md
---

# WaveDevSecOps — EXPERIENCE

> **DESIGN.md et EXPERIENCE.md priment sur toute maquette, wireframe ou import.** Les exigences sont citées par leur numéro (FR-n, UJ-n, NFR-n du PRD), sans être recopiées. Le vocabulaire est celui du glossaire du PRD (§3). Les maquettes de `mockups/` sont liées dans les sections qu'elles illustrent.

## Foundation

- WaveDevSecOps est une application web locale, servie sur `127.0.0.1` par un port libre et ouverte dans le navigateur ; la fenêtre pywebview sert de repli (NFR-12).
- Elle vise le desktop, à partir d'un écran 1920×1080 (détail : Responsive & Platform).
- Elle parle français (NFR-8) et vouvoie. Commandes, identifiants et sorties d'outils restent tels quels.
- Elle fonctionne hors ligne (NFR-1, NFR-9) : tout est servi en local. Seule l'exécution facultative du code LLM (FR-17) peut sortir du poste, par `network-run-button`.
- Son identité est décrite dans DESIGN.md, reprise de WaveStack. Elle a deux thèmes, Clair et Sombre, et une option Système (par défaut).
- Elle sert un apprenant par installation, sans compte (FR-20).
- Elle reprend le principe de WaveStack : des vues synchronisées sur le même état, une explication attachée à chaque élément (NFR-13), et des échecs qui servent de matériau pédagogique (NFR-7).

## Information Architecture

| Surface | Atteinte depuis | Rôle | Jalon |
|---|---|---|---|
| Diagnostic | Ouvert d'office au premier lancement ; puis « Diagnostic » dans l'en-tête | Outils, versions, marche à suivre, proxy (FR-19) | v0.1 |
| Catalogue (accueil) | Lancements suivants ; « Catalogue » dans l'en-tête | Parcours, scénarios en ordre conseillé, état A/B, « Reprendre », « Exporter mon rapport » (FR-9, FR-16) | v0.1 |
| Espace de travail scénario | Carte de scénario | Disposition principale : panneau Scénario et vues (FR-1 à FR-15) | v0.1 |
| Bilan de scénario | Fin de la dernière étape, dans le panneau Scénario | Score du premier coup, indices, suite (FR-20) | v0.1 |
| Rapport de progression | « Exporter mon rapport » (catalogue) | Aperçu puis export (FR-36) | v0.1 |
| Carte dépliée | « Carte ▾ » du bandeau | Stations, outils et barrières (FR-32) | v0.2 |
| Vocabulaire | « Vocabulaire » dans l'en-tête | Termes cibles et barrières (FR-33) | v0.2 |
| Entretien RSSI | Section « Savoir en parler » du catalogue | Scénario quiz avec preuve désignée (FR-34) | v0.3 à v1.0 |
| Fiche barrière → risque → preuve | Fin de l'entretien RSSI ; « Fiche » dans l'en-tête | Tableau et export HTML + CSV (FR-35) | v0.3 à v1.0 |

**En-tête (`site-nav`).** À gauche : la marque, Catalogue, Vocabulaire (v0.2), Fiche (v0.3 à v1.0) et Diagnostic avec son `diagnostic-badge`. À droite : `path-menu` « Parcours LLM ▾ », « Volets ▾ » (`pane-menu`, dans l'espace de travail ; le menu Volets liste les vues) et « Affichage ▾ » (thème, « Réduire les animations »). Un lien n'apparaît qu'avec le jalon qui livre sa surface `[ASSUMPTION]`.

**Parcours.** Le parcours en cours s'affiche sur tous les écrans dans `path-menu`, qui permet d'en changer partout. Chaque parcours garde sa progression (FR-16) : les cartes du catalogue montrent l'état du parcours choisi. Depuis un scénario, changer de parcours ramène au catalogue du nouveau parcours ; le scénario quitté reste à son étape dans l'ancien `[ASSUMPTION]`. Le `path-picker` du catalogue est le même choix, en plus grand. Au premier passage, aucun parcours n'est choisi (voir Catalogue).

Les pages annexes (Diagnostic, Rapport, Fiche) ont un fond `{colors.surface}` sans pois.

### Catalogue

Rendu : [mockups/catalogue.html](mockups/catalogue.html) (parcours LLM choisi, trois sections, un scénario en cours avec « Reprendre », trois cartes indisponibles faute de gitleaks ou de bandit).

- En haut, `path-picker` propose « Parcours LLM » et « Parcours sans IA ». Au premier passage, le catalogue n'affiche que cette question : « Choisissez votre parcours. Les deux suivent la même progression ; seul le code d'exercice change. », avec une phrase par option.
- Trois `catalogue-section` suivent : « Socle git » (8 scénarios dans l'ordre conseillé de FR-9), « Stations » (v0.2+, regroupées par station) et « Savoir en parler » (Vocabulaire, Entretien RSSI, Fiche). Une section d'un jalon non livré n'apparaît pas `[ASSUMPTION]`.
- Chaque `scenario-card` a une colonne Mode A et, si le scénario en a un, une colonne Mode B. Chacune affiche « À faire », « En cours » ou « Terminé », avec le score du premier coup (gabarit : « 3 sur 4 du premier coup · 0 indice / 1 indice / 2 indices »).
- Le bouton « Reprendre » se trouve sur le dernier scénario ouvert, dans la colonne du mode en cours, sous « Étape 3 sur 6 ». Il rouvre le scénario à cette étape, avec le bac à sable tel que l'apprenant l'a laissé `[ASSUMPTION, question ouverte 9]`. Si le bac à sable a disparu ou ne correspond plus à l'étape, un encart dit « Ce scénario ne peut pas reprendre là où vous l'aviez laissé. » et propose « Recommencer ».
- Une carte de station correspond à un scénario de barrière ; elle est rangée sous le sous-titre « Station n · Nom » et n'a qu'une ligne d'état.
- Une carte indisponible reste visible mais ne s'ouvre pas ; elle affiche « ⊘ Indisponible » et « Nécessite <outil> · Voir le diagnostic ».
- En pied, « Exporter mon rapport » est suivi de « Rien n'est envoyé : vous choisissez à qui transmettre le fichier. ».

### Disposition principale (espace de travail)

```
┌ En-tête (site-nav) ─────────────────────────────────────────────────────────────────────┐
├ Bandeau (v0.2) : Station 1 · Poste │ Station 2 · PR et CI │ Station 3 · Sécurité ┃CI|CD┃ Station 4 · Livraison [Carte ▾] ┤
├ Scénario ──────┬ ① Dépôt local (graphe + index) ─────┬ ② Distant + PR ──────────────────┤
│ titre, badge   │                                     │ refs origin, PR, checks, revue   │
│ étape n/N      ├ ③ Code (fichiers, diff, éditeur, trois écritures, SBOM) ───────────────┤
│ consigne       │                                                                        │
│ question       ├ ④ Terminal ────────────────────────────────────────────────────────────┤
│ explication    │ $ git …                                                                │
│ indices        │                                                                        │
│ Recommencer    │                                                                        │
└────────────────┴────────────────────────────────────────────────────────────────────────┘
```

Rendu : [mockups/espace-travail.html](mockups/espace-travail.html) (Flow 4, étape 3 : le check bandit a le focus et ses correspondants sont éclairés).

Proportions à 1920×1080, pour une fenêtre utile d'environ 1920×950 :

| Zone | Taille |
|---|---|
| Panneau Scénario | `{spacing.scenario-panel-width}` (≈ 23 %), toute la hauteur sous les bandeaux |
| Rangée haute | 40 % de la hauteur ; Dépôt local 55 %, Distant + PR 45 % |
| Code | 33 % de la hauteur |
| Terminal | 27 % de la hauteur (≈ 11 lignes) |

- Chaque vue défile en interne ; son en-tête reste fixe.
- Dans Distant + PR, le contenu s'ordonne ainsi : refs, PR courante, checks en échec, `merge-blocked`, checks réussis, journal de revue. Dans Code : fichier ou diff sélectionné, puis l'arbre en colonne repliable.
- Les vues portent un numéro de lecture (`pane-step`). Les stations s'écrivent toujours « Station n · Nom ».
- Sous-titres des vues : « Graphe des commits et index, comme `git log --all` et `git status` » ; « Refs de origin et PR du GitHub simulé » ; « Fichiers du bac à sable, diff et éditeur » ; « Vrai git, dans le bac à sable ».
- Le bandeau (v0.2) s'ajoute sous l'en-tête et réduit la hauteur des vues ; le reste de la disposition ne change pas (FR-32, NFR-10). Le menu Volets ne gère ni le bandeau ni la carte dépliée.
- La carte dépliée se pose par-dessus les vues, sans les déplacer. Accessibilité : voir Accessibility Floor > Carte dépliée.

### Masquage, agrandissement, élargissement

Ces règles viennent de WaveStack ([digest §3](imports/wavestack-digest.md)).

| Action | Effet |
|---|---|
| « — » dans l'en-tête d'une vue | La vue se masque et devient la puce « + Nom » |
| Puce « + Nom » ou case du menu Volets | La vue se réaffiche à sa dernière taille |
| ⛶ « Agrandir » | La vue occupe la zone des vues (vue agrandie) ; Échap ou ⛶ revient |
| Poignée de gouttière, glissée ou au clavier par pas de 16 px | La vue s'élargit ou se réduit ; double-clic = proportions par défaut |
| « Élargir » / « Réduire » dans le menu Volets | Même effet que la poignée, sans glisser |

- Au moins une vue reste visible. Une vue mesure au moins 240 × 160 px.
- Le navigateur mémorise les tailles et la configuration ; elles survivent au changement de scénario et à « Recommencer ».
- Le panneau Scénario ne se masque pas `[ASSUMPTION]`.
- Gestion du focus : voir Accessibility Floor > Masquage.

## Voice and Tone

Règles reprises de WaveStack : phrases courtes et complètes, pas de point d'exclamation, pas d'emoji, termes consacrés gardés (commit, push, PR, check), nombres précis, casse normale.

Un message d'état dit ce qui se passe, pourquoi (une phrase) et ce qu'on peut faire. Il nomme toujours **qui** décide : git, le hook, le pipeline simulé, le GitHub simulé ou WaveDevSecOps.

| Faire | Ne pas faire |
|---|---|
| « Le commit `a1b2c3d` n'est plus sur aucune branche. Il reste visible par `git reflog`. » | « Oups, vous avez perdu votre travail. » |
| « Refusé par le hook pre-commit : gitleaks a trouvé une clé dans `config.py`, ligne 4. » | « Erreur de commit. » |
| « Ce n'est pas l'élément attendu. Le commit en cause est entouré dans le graphe. » | « Mauvaise réponse ! » |
| « Merge impossible : le check bandit est en échec et 1 approbation sur 2 est donnée. » | « Vous ne pouvez pas merger. » |
| « Une piste pour avancer. Ouvrir un indice ne change pas votre score. » | « Besoin d'aide ? (−1 point) » |
| « Disponible après un essai ou un moment de lecture. » | « Solution disponible dans 30 s. » |
| « Refusée : `curl` n'est pas accepté ici. Ce terminal accepte git et ces commandes : `ls`, `cat`… » | « command not found » réécrit ou masqué |

- Un échec n'est jamais une faute de l'apprenant : on décrit l'état, pas la personne.
- L'aide est présentée comme normale.
- En mode B, l'agent est décrit par ses actes (« l'agent a committé `.env` »), sans morale.
- Les sorties de git et des outils ne sont jamais traduites ni réécrites (NFR-2). git est lancé en locale française : ses messages sont en français si ses traductions sont installées, en anglais sinon (par exemple avec MinGit). L'explication de l'application est toujours en français. La faisabilité relève de l'architecture.
- Le score suit un seul gabarit : « 3 sur 4 du premier coup · 1 indice », avec l'accord « 0 indice », « 1 indice », « 2 indices ».

## Component Patterns

Comportement. Les specs visuelles sont dans DESIGN.md > Components.

| Composant | Où | Règles de comportement |
|---|---|---|
| `site-nav` | Partout | Les liens suivent les jalons ; la page courante est soulignée. |
| `path-menu` | En-tête | Change le parcours depuis tout écran (règle : Information Architecture > Parcours). |
| `scenario-panel` | Espace de travail | Toujours visible. L'explication d'une étape n'apparaît qu'après la mise à jour des vues (FR-4). À la fin, le panneau affiche le bilan. |
| `mode-badge` | Panneau | Statique ; son « i » dit ce que signifie le mode A ou B. |
| `step-progress` | Panneau | Avance quand l'étape est validée sur l'état réel (FR-11). Chaque segment terminé est un bouton qui rouvre sa consigne dans un `explain-popover`. |
| `step-explanation` | Panneau | Apparaît après la mise à jour des vues (FR-4). La variante correction liste l'attendu et les équivalents, chacun avec « voir dans les vues ». La variante « Ce qui l'aurait bloqué » (FR-12, scénario `.env`) annonce les barrières, avec « Arrive en v0.2 » tant que la station n'est pas livrée. |
| `quiz-choice` | Panneau | Groupe radio : les flèches changent le choix, un seul choix à la fois. « Exécuter ma réponse » reste inactif tant que rien n'est coché et dit « Choisissez une commande. ». |
| `notice-card` | Panneau, pages annexes | Encart en ligne, jamais modal. Il porte une cause, une explication et une à trois actions, et reste jusqu'à ce que l'état change. |
| `score-summary` | Bilan | Propose « Scénario suivant », « Catalogue » et « Recommencer ». Recommencer conserve le score du premier coup (FR-10). |
| `terminal` | Terminal | Voir le tableau ci-dessous. |
| `terminal-prompt`, `terminal-stderr`, `terminal-exit-error` | Terminal | L'invite montre la branche courante. stderr reste à sa place dans le flux. Le code de sortie n'est ajouté que s'il est non nul. |
| `terminal-app-message`, `terminal-refused` | Terminal | Ce sont les seules façons pour l'application d'écrire dans le terminal ; elles ne se mêlent jamais à une ligne de git. |
| `graph-commit`, `graph-edge`, `graph-head`, `graph-branch`, `graph-remote-ref`, `graph-tag`, `graph-commit-colleague`, `graph-commit-agent` | Dépôt local | Survol ou focus : correspondances. Clic : sélection. « i » ou Entrée sur l'élément sélectionné : explication attachée (NFR-13). Un commit ne change pas de place sans raison git `[ASSUMPTION]`. |
| `graph-commit-lost` | Dépôt local | Le graphe suit `git log --all` et y ajoute, en tirets, les commits non référencés encore présents dans le reflog, avec « perdu · visible par reflog ». |
| `commit-list` | Dépôt local | Le bouton « Liste » / « Graphe » de l'en-tête de la vue bascule entre les deux. La sélection et les correspondances sont les mêmes. |
| `new-mark` | Vues | Posé par la dernière commande, retiré à la suivante ; « Rétabli » après un rétablissement de quiz. |
| `staging-index` | Dépôt local | Reflète `git status`. Un clic sélectionne ; il ne stage rien, on passe par le terminal `[ASSUMPTION]`. |
| `code-editor`, `external-change-notice` | Code | Ctrl+S ou le bouton enregistre ; « Ouvrir dans mon éditeur » ouvre l'éditeur externe (FR-3). Les marqueurs de conflit sont visibles et éditables. |
| `diff-view`, `diff-file-header` | Code | Le diff suit la sélection : commit, PR ou arbre de travail. Chaque ligne et chaque en-tête de fichier sont liables, focalisables et désignables. |
| `sbom-view` | Code | S'ouvre par « Voir le SBOM » sur le check pip-audit ou dans l'arbre. Lecture seule. Chaque ligne est liable (dépendance de `pyproject.toml`, check pip-audit) et désignable comme preuve. |
| `pr-card` | Distant + PR | « Ouvrir une PR » sur une branche poussée (FR-6). Merger n'est actif que si toutes les conditions sont remplies. |
| `pr-check` | Distant + PR | Un clic sélectionne ; « Voir la sortie » déplie `tool-output` ; « Voir dans le pipeline » ouvre `pipeline-tabs`. |
| `review-log` | Distant + PR | Le journal de revue liste demandes, commentaires et approbations dans l'ordre. Le collègue simulé répond selon le scénario. Chaque entrée est liable et désignable comme preuve. |
| `merge-blocked`, `promotion-gate` | Distant + PR | Les raisons restent visibles, une par ligne, chacune liée à l'élément en cause. |
| `tool-output` | Distant + PR, Terminal | Sortie réelle, sans réécriture ; les fichier:ligne deviennent des liens vers Code. Le bloc est focalisable et désignable. |
| `network-run-button` | Panneau | Aucune étape ne l'exige. Une confirmation en ligne demande : « Ce code peut appeler un service en ligne. Continuer ? ». |
| `explain-popover` | Partout | S'ouvre au clic, à Entrée ou à Espace sur « i » ; Échap le ferme et rend le focus au « i ». Il tient en deux ou trois phrases et n'apparaît jamais au seul survol. |
| `chain-band`, `chain-map` | Sous l'en-tête | La station courante suit le scénario. Un clic sur une station déplie la carte sur elle. Un nœud de barrière se lie aux checks, aux hooks et aux termes. |
| `pane`, `pane-step`, `pane-chip`, `pane-menu`, `pane-resize-handle`, `link-state`, `focus-ring`, `state-pill`, `theme-picker` | Partout | Comportement de WaveStack, avec les règles de focus de l'Accessibility Floor. |
| `button-primary`, `button-secondary`, `reset-button`, `button-danger` | Partout | Un bouton inactif dit pourquoi, dans un texte visible et relié. « Recommencer » est un `reset-button` avec confirmation en ligne ; `button-danger` sert au Rollback. |

**Terminal.**

| Touche ou situation | Effet |
|---|---|
| Entrée | Exécute la ligne saisie |
| ↑ / ↓ | Parcourt l'historique de la session |
| Ctrl+C | Interrompt la commande en cours |
| Ctrl+L | Efface l'affichage, pas l'historique |
| Sortie longue | Affichée au fil de l'eau, sans pager ; le défilement suit, sauf si l'apprenant a remonté |
| Plus de 5 000 lignes | Les plus anciennes sont masquées : « 1 240 lignes plus anciennes masquées » `[ASSUMPTION]` |
| Complétion | Absente en v0.1 ; si elle arrive, jamais sur Tab |

**Composants dont la règle est portée par une section.**

| Composant | Section |
|---|---|
| `designate-button`, `designate-list`, `answer-slot`, `sha-field`, `designable`, `verdict-mark` | Désignation |
| `hint-tabs` | Indices à paliers |
| `quiz-banner` | Quiz à exécution réelle |
| `pipeline-tabs` | Pipeline simulé et trois écritures |
| `build-artifact`, `env-card` | Livraison |
| `glossary-term` | Vocabulaire |
| `path-picker`, `catalogue-section`, `scenario-card` | Information Architecture > Catalogue |
| `diagnostic-row`, `diagnostic-badge` | Diagnostic |
| `report-preview`, `barrier-sheet` | Exports |

## State Patterns

Règle générale (NFR-7) : l'application ne plante jamais.

| État | Surface | Traitement |
|---|---|---|
| Aucune progression | Catalogue, Rapport | Les cartes affichent « À faire ». L'aperçu du rapport dit : « Aucun scénario terminé pour l'instant. Le rapport contiendra seulement les dates d'installation et de premier lancement. ». |
| Chargement d'un scénario | Espace de travail | « Préparation du bac à sable… 2 s » ; chaque vue montre un état vide titré, jamais un spinner muet. |
| Vue vide | Vues | Dépôt local : « Aucun commit pour l'instant. Créez un fichier puis tapez `git add` et `git commit`. » Distant + PR : « Aucune PR. Poussez une branche, puis ouvrez une PR. » Code : « Sélectionnez un fichier, un commit ou une PR pour voir son contenu. ». |
| Bac à sable indisponible | Panneau | `notice-card` d'erreur : « Le bac à sable n'a pas pu être créé dans `<dossier>` : <cause>. », avec « Réessayer » et « Voir le diagnostic ». |
| Commande en cours | Terminal | La saisie est inactive ; après 1 s, « En cours… 3 s » s'affiche ; Ctrl+C reste possible. |
| Synchro après commande (FR-4) | Toutes | L'ordre est fixe : sortie de git, puis vues mises à jour avec `new-mark`, puis validation de l'étape, puis explication. L'explication ne précède jamais les vues. |
| Modification externe (FR-3) | Dépôt local, Code | Les vues se mettent à jour seules et `external-change-notice` affiche « Modifié hors de l'application ». Si l'éditeur a des changements non enregistrés : « Le fichier a changé sur le disque. », avec « Garder ma version » et « Recharger ». |
| État inattendu (FR-11) | Panneau | `notice-card` d'information « État inattendu » : ce que l'étape attendait, ce qu'elle voit (liens vers les vues), une explication, puis « Continuer », « Ouvrir un indice » et « Recommencer ». Rien n'est bloqué. |
| Commande refusée (FR-2) | Terminal | `terminal-refused` : « Refusée : `<commande>` n'est pas accepté ici. Ce terminal accepte git et ces commandes : `<liste>`. Il reste confiné au bac à sable. » |
| Commande interactive | Terminal | « git attend un message de commit. Ajoutez `-m "…"`. » `[ASSUMPTION : mécanisme fixé en architecture]` |
| Erreur de git | Terminal | La sortie reste intacte, suivie de `terminal-exit-error` ; le panneau donne une explication si l'étape la prévoit. |
| Commit refusé par le hook (FR-21) | Terminal, panneau | La sortie réelle de gitleaks s'affiche (`tool-output`) et aucun commit n'apparaît dans le graphe. Le panneau dit : « Refusé par le hook pre-commit : gitleaks a trouvé un secret. Le commit n'a pas été créé. », avec un lien vers la ligne. |
| Lint ou test en échec (FR-21) | Terminal | La sortie réelle de ruff ou de pytest s'affiche ; les fichier:ligne sont liés à Code ; l'étape donne son explication. |
| Outil manquant | Catalogue, scénario | Le scénario dépendant est grisé avec sa raison. Si l'outil disparaît pendant un scénario, le terminal et le panneau le disent, avec un lien vers le diagnostic ; le reste continue `[ASSUMPTION]`. |
| Rétablissement en cours (FR-15) | Toutes | « Rétablissement de l'état… 1 s ». Les vues sont inactives (attribut HTML `inert`), leur texte reste lisible ; le terminal est inactif. |
| Rétablissement échoué (FR-15) | Panneau | `notice-card` d'erreur : « L'état n'a pas pu être rétabli. Pour ne pas vous laisser sur un état faux, recommencez le scénario. Votre score du premier coup est conservé. » La seule action est « Recommencer » (FR-10). L'annonce est immédiate. |
| Recommencer (FR-10) | Panneau | Confirmation en ligne : « Remettre le scénario à son état initial ? Votre score du premier coup est conservé. » Puis : « Scénario remis à zéro. ». |
| PR bloquée (FR-8, FR-22) | Distant + PR | `merge-blocked` liste le check obligatoire en échec, la revue obligatoire absente et « Approbations : 1 sur 2 ». |
| Push direct refusé (FR-22) | Terminal | La sortie réelle du refus s'affiche, suivie de : « Refusé par la protection de `main` : tout passe par une PR. ». |
| Check en cours | Distant + PR | `pr-check` « En cours » avec chronomètre ; c'est le seul élément animé. |
| Outil en erreur dans le pipeline | Distant + PR | `pr-check` « ⚠ Erreur de l'outil », distinct d'« Échec » : « bandit s'est arrêté sans résultat (code 2). Ce n'est pas un défaut de votre code. », avec « Relancer le check ». La PR reste bloquée. |
| Fin de scénario | Panneau | Le bilan s'affiche ; les vues restent consultables. |
| Export impossible | Rapport, Fiche | `notice-card` d'erreur : « Le fichier n'a pas pu être enregistré : <cause>. », avec « Réessayer ». |
| Application arrêtée | Page ouverte | Si le serveur local ne répond plus, un bandeau dit : « WaveDevSecOps ne répond plus. Relancez-le ; votre progression est enregistrée. » Les actions deviennent inactives. |
| Port occupé, page inaccessible | Console de lancement | Voir Flow 3. |

États traités dans leur section : premier passage sans parcours (Catalogue), état modifié par un quiz (Quiz à exécution réelle), désignation armée (Désignation), livraison (Livraison).

## Interaction Primitives

- **Survol ou focus** : montre les correspondances (`link-state`).
- **Clic, Entrée ou Espace** : pose une sélection persistante et unique ; un nouveau clic l'efface. Hors mode désignation, un clic ne sert qu'aux correspondances (FR-5).
- **Mode désignation** : seul `designate-button` l'arme (voir Désignation).
- **Échap**, hors terminal, ferme dans cet ordre : popover, carte dépliée, liste de désignation, menu Volets, mode désignation, sélection, vue agrandie. Dans le terminal, Échap rend seulement le focus au titre de la vue Terminal.
- **Clavier** : Tab suit l'ordre de lecture (en-tête, bandeau, `quiz-banner` s'il est présent, panneau Scénario, vues dans l'ordre de leur numéro) et saute les vues masquées. Chaque vue est un seul arrêt de tabulation ; à l'intérieur, les flèches passent d'un élément à l'autre (focus itinérant : un seul élément de la vue reçoit Tab, les flèches déplacent le focus entre les autres). F6 passe d'une zone à la suivante.
- **Terminal** : Tab en sort toujours. Aucun raccourci de l'application n'y capture de touche, sauf Échap.
- **Bannis** (repris de WaveStack) : modales bloquantes, notification qui masque une vue, information au seul survol, défilement automatique qui reprend la main, troncature sans accès au texte entier, exécution d'une commande par clic.

## Accessibility Floor

Repris de WaveStack ([digest §3](imports/wavestack-digest.md)) : jamais la couleur seule ; tout au clavier dans l'ordre de lecture ; cibles d'au moins `{spacing.hit-target-min}` (contiguës : `{spacing.hit-target-dense}`) ; traits d'au moins `{spacing.stroke-min}` ; vues en régions nommées ; niveau AA dans les deux thèmes.

**Focus et états visuels.** `focus-ring` est décalé de 2 px, en `{colors.primary}`, et en `{colors.focus-on-ink}` sur fond encre (terminal, HEAD, étiquettes). Focus, lié, sélectionné et désignable ont chacun leur forme (DESIGN.md > Focus, liaison, sélection). L'estompage et le grisé ne changent jamais l'opacité du texte.

**Annonces.**
- Une seule région `role="status"` reçoit les messages dans l'ordre de FR-4 : « Commande terminée. Vues mises à jour : 1 commit et 1 branche nouveaux. Étape 3 validée. » L'explication et le verdict s'annoncent ensuite, dans le panneau.
- `role="alert"` sert à : commande refusée, commit refusé par le hook, rétablissement échoué, « Application arrêtée ».
- Les chronomètres ne sont jamais dans une région live : « En cours » est annoncé une fois, « Terminé » à la fin.
- Correspondances : le résumé « 3 éléments liés : ref origin/main, PR n°2, fichier config.py » est relié par `aria-describedby` à l'élément qui a le focus. Il se lit sur demande, pas à chaque flèche. « Voir les éléments liés » ouvre la liste.

**Graphe.** Chaque nœud a un nom construit par gabarit : « Commit a1b2c3d, Add config, par l'agent, parent 9f8e7d6, pointé par la branche locale feature et HEAD, nouveau ». Les états (perdu, sélectionné, attendu, votre choix) entrent dans ce nom. Les refs ont un rôle et un nom (« référence distante origin/main », « tag v0.1.0 »). Les arêtes sont dites par « parent » dans le nom ; `commit-list` est l'alternative texte complète du graphe.

**Terminal.** La région a `role="log"`. Chaque ligne stderr porte un préfixe masqué « erreur standard : » ; la ligne finale dit « code de sortie 128, échec ». Une sortie en anglais porte `lang="en"`. Pendant le quiz, la saisie en lecture seule porte `aria-readonly="true"` et sa raison reliée.

**Indices.** Le bloc a `role="tablist"`. L'onglet verrouillé porte `aria-disabled="true"`, reste focalisable et relie sa condition par `aria-describedby`. Son déblocage est annoncé : « La solution est disponible. ».

**Quiz.** À l'apparition du `quiz-banner`, le focus va sur son titre ; le bandeau précède le panneau dans le DOM. Après le rétablissement, le focus revient au panneau.

**Carte dépliée.** « Carte ▾ » porte `aria-expanded` et `aria-controls`. À l'ouverture, le focus va sur la station demandée et les vues dessous deviennent `inert`. Échap ferme la carte et rend le focus au bouton. La station courante porte `aria-current="step"`.

**Masquage.** Après « — », le focus va sur la puce « + Nom » ; après réaffichage, sur le titre de la vue. Les poignées ont `role="separator"` et leurs valeurs ; « Élargir » et « Réduire », dans le menu Volets, évitent le glisser.

**Champs.** Un bouton inactif porte `aria-disabled` et sa raison reliée. Un SHA inconnu déclenche `role="alert"` et `aria-invalid` ; l'aperçu d'un SHA résolu est en `role="status"`. La pastille du diagnostic se lit « Diagnostic, 2 outils absents ou trop anciens ». Les tableaux ont des en-têtes `th`.

**Zoom et mouvement.** À 400 % (320 px CSS), le panneau Scénario, le catalogue et les pages annexes se lisent sur une colonne, sans défilement horizontal ; seuls le graphe, le diff et le terminal défilent dans les deux sens. Avec `prefers-reduced-motion` ou « Réduire les animations », le point « en cours » reste fixe avec son mot, les transitions sont coupées et le défilement n'est pas animé.

## Correspondances entre vues

Deux éléments sont liés s'ils partagent une clé : SHA, nom de ref, chemin, numéro de PR ou nom de check. `[ASSUMPTION : table proposée ; FR-5 laisse le détail à l'UX]`

| Élément | Dépôt local | Distant + PR | Code | Terminal | Carte (v0.2) |
|---|---|---|---|---|---|
| Commit | Nœud ; refs et HEAD qui le pointent | Refs `origin/…` ; PR qui le contiennent | Diff du commit | Lignes qui citent son SHA | — |
| Branche / ref | Étiquette et commit de tête | Ref distante homonyme ; PR dont c'est la tête ou la base | — | Lignes qui citent le nom | — |
| Fichier | Entrée de l'index | Fichier de la PR | Fichier dans l'arbre et l'éditeur | Lignes qui citent le chemin | — |
| Ligne de diff | Commit sélectionné qui l'introduit | Même ligne dans le diff de la PR | Ligne de l'éditeur | Sortie d'outil qui cite fichier:ligne | — |
| PR | Branches tête et base | Carte de PR | Diff de la PR | Lignes du push | Station 2 · PR et CI |
| Check | Commit testé | Ligne du check | Lignes signalées ; lignes de la tâche (`pipeline-tabs`) | Sortie de l'outil en local | Station et barrière |
| Sortie d'outil | — | Check correspondant | Fichier:ligne cités | Bloc de sortie | Barrière |
| Journal de revue | Commit relu | Entrée du `review-log` | — | — | Station 2 ou 3 |
| Ligne du SBOM | — | Check pip-audit | Ligne de `pyproject.toml` | Sortie de pip-audit | Barrière SCA |
| Tag (v0.3) | Étiquette et commit | Tag sur `origin` ; `build-artifact` | — | Ligne de `git tag` | Station 4 · Livraison |
| Barrière | Hook pre-commit (Station 1 · Poste local) | Check(s) et règle de protection | Fichier de config, lignes du pipeline | Dernière sortie de l'outil | Nœud de barrière |
| Terme du vocabulaire | Comme sa barrière | Comme sa barrière | Comme sa barrière | Comme sa barrière | Nœud de barrière |

- Dans le terminal, seuls les SHA, refs, chemins et blocs de sortie d'outil qui existent dans le bac à sable sont liables. Une ligne liée prend le fond et l'anneau `terminal-lit` ; les autres lignes passent en texte secondaire.
- Préséance des marques : verdict, puis sélection, puis désignable, puis lié.
- Si un correspondant est dans une vue masquée, la puce devient « + Nom · lié » ; un clic réaffiche la vue avec l'élément en évidence.
- Si un correspondant est hors de la zone visible, la vue défile jusqu'à lui sur clic, jamais au survol.

## Désignation (mode B et entretien RSSI)

Rendu : [mockups/designation-mode-b.html](mockups/designation-mode-b.html) : (a) mode armé, liste ouverte qui défile en interne, choix en attente ; (b) réponse fausse corrigée dans les vues et le panneau.

Au service de FR-12 et FR-34.

1. Le panneau pose la question (« Qu'a fait l'agent ? ») et propose `designate-button` « Désigner dans les vues ».
2. Une fois armé, le mode entoure de tirets les éléments désignables (`designable`) et change le curseur système (`crosshair`). Le bouton devient « Désignation active · Échap pour quitter » ; il porte `aria-pressed="true"` et le changement est annoncé.
3. Un clic, ou Entrée sur un élément qui a le focus, place l'élément dans `answer-slot`. Un autre choix le remplace ; ✕ vide la case. Le mode reste armé jusqu'à la validation ou Échap `[ASSUMPTION, question ouverte 4]`.
4. Échap désarme sans vider la case et rend le focus à `designate-button`.
5. Trois moyens équivalents permettent de choisir :
   - **dans les vues**, à la souris ou au clavier. Tab passe d'une vue à l'autre dans l'ordre normal ; les flèches parcourent les désignables de la vue ; Entrée choisit. Lignes de diff, en-têtes de fichier, blocs `tool-output`, lignes du terminal, entrées de `review-log` et lignes de `sbom-view` reçoivent le focus ;
   - **dans la liste** `designate-list` du panneau, où les désignables sont groupés par vue et filtrables au clavier. Elle couvre aussi les preuves qui ne sont pas des commits : sortie d'outil, check, journal de revue, SBOM, tag ;
   - **par SHA** (`sha-field`), raccourci pour un commit. Le champ accepte un SHA abrégé d'au moins 7 caractères `[ASSUMPTION]`, le résout dans le bac à sable et affiche un aperçu (« `a3f9d21` · Add config · Agent »). Pour un SHA inconnu, il dit « Aucun commit ne correspond à ce SHA dans le bac à sable. » ; l'essai n'est pas consommé.
6. Tab atteint toujours ✕, le champ SHA et « Valider ma réponse », même en mode armé.
7. Seul « Valider ma réponse » consomme l'unique essai (FR-12) ; le texte relié « 1 seul essai » figure sous le bouton.
8. Un élément choisi qui reste désignable montre le contour de sélection à la place du pointillé.
9. Hors désignation, un clic sert seulement aux correspondances.

Sont désignables tous les éléments des types acceptés par la question, pas seulement les bonnes réponses.

| Question | Types désignables |
|---|---|
| « Qu'a fait l'agent ? » (mode B) | Commit, branche ou ref, fichier, ligne de diff ; SHA |
| Preuve RSSI (FR-34) | Sortie d'outil (bloc ou ligne), check, entrée du journal de revue, ligne du SBOM, tag ; SHA si la preuve est un commit |

### Correction

1. Chaque question déclare un ensemble de bonnes réponses équivalentes, toutes acceptées : par exemple le commit `a3f9d21`, le fichier `.env` dans ce commit, la ligne `API_KEY=` de son diff et son SHA. L'ensemble a un élément principal.
2. Si le choix appartient à l'ensemble, il porte « ✓ Votre choix » ; sinon, il porte « ✗ Votre choix ».
3. Dans les deux cas, l'élément principal porte « ✓ Attendu » et les équivalents « ≡ Accepté aussi ».
4. L'explication du panneau apparaît, juste ou non, avec « voir dans les vues » vers chaque élément. Les marques restent jusqu'à l'étape suivante.
5. La case devient « Votre réponse · validée », sans ✕. Le panneau propose ensuite « Continuer » et « Recommencer ». Dans le scénario `.env`, l'encart « Ce qui l'aurait bloqué » suit la correction.

**Entretien RSSI.** Deux cases : « Réponse » (`quiz-choice`, choix parmi des propositions) et « Preuve » (désignation). Elles se remplissent dans l'ordre libre. « Valider ma réponse » s'active quand les deux sont remplies ; sinon il reste inactif et dit ce qui manque : « Il manque la preuve. Désignez-la dans les vues. » (FR-34). Une question n'est réussie que si la réponse est juste et la preuve dans l'ensemble déclaré `[ASSUMPTION]`.

## Indices à paliers

Au service de FR-13. Accessibilité : voir Accessibility Floor > Indices.

- Un seul `hint-tabs` occupe le panneau : Piste | Commande partielle | Solution. Un onglet ne s'ouvre qu'après le précédent.
- Un onglet verrouillé montre un cadenas et sa condition en clair. Pour la solution : « Disponible après un essai ou un moment de lecture. » Aucun décompte n'est affiché ; la durée reste un paramètre interne.
- « Un essai » est une commande tapée ou un choix validé pendant l'étape `[ASSUMPTION, question ouverte 5]`.
- Aucun compteur n'apparaît pendant l'étape. Le nombre d'indices n'apparaît qu'au bilan, à côté du score.
- Rouvrir un palier déjà ouvert ne compte pas une seconde fois `[ASSUMPTION]`.
- La commande partielle montre la commande avec des blancs (`git reset --____ HEAD@{1}`).
- La solution est un texte sélectionnable, sans bouton Copier ni Exécuter : l'apprenant la tape.
- Le suivi enregistre le palier, le temps avant la demande et le temps de lecture (FR-13), sans rien afficher pendant l'étape.

## Quiz à exécution réelle

Au service de FR-15. Accessibilité : voir Accessibility Floor > Quiz.

1. Le panneau propose des commandes (`quiz-choice`). « Exécuter ma réponse » lance le choix.
2. La commande s'exécute pour de vrai dans le terminal, juste ou non `[ASSUMPTION pour la bonne réponse]`.
3. Une bonne réponse n'affiche pas de bandeau : l'état produit reste et l'étape continue.
4. Après une mauvaise réponse, les vues restent sur l'état modifié (par exemple le commit perdu en `graph-commit-lost`). Le `quiz-banner` affiche « État modifié par le quiz — `git reset --hard HEAD~1` » et prend le focus. Le panneau affiche l'explication.
5. Pendant ce temps, le terminal est en lecture seule. Il accepte les commandes qui lisent l'état (`git status`, `git log`, `git reflog`, `ls`, `cat`…) et refuse les autres par `terminal-refused` : « Refusée pendant l'état modifié par le quiz. Les commandes de lecture restent possibles. Rétablissez l'état pour reprendre. »
6. « J'ai compris, rétablir l'état » déclenche le rétablissement. Les vues le montrent : « Rétabli » sur les éléments revenus.
7. L'apprenant rechoisit. Seul le premier essai compte pour le score du premier coup.
8. Si le rétablissement échoue, voir State Patterns > Rétablissement échoué.

## Diagnostic

Au service de FR-19 et UJ-2. Rendu : [mockups/diagnostic.html](mockups/diagnostic.html) (Camille derrière un proxy : gitleaks absent, bandit trop ancien, `NO_PROXY` à compléter).

- Le diagnostic s'ouvre d'office au premier lancement. Ensuite, on l'ouvre par « Diagnostic » dans l'en-tête, dont le `diagnostic-badge` compte les outils requis absents ou trop anciens.
- L'en-tête de page propose « Relancer le diagnostic ». Sous le titre, une phrase de synthèse (`role="status"`) résume : « Recherche terminée : 2 outils sur 7 demandent une action, et NO_PROXY demande un réglage. ».
- Pendant la recherche, chaque outil a une ligne « En cours », puis son état ; aucun outil n'est dit absent avant la fin.
- Le tableau est groupé par jalon (« Outils requis (v0.1) », « Outils de la chaîne (v0.2+) ») :

| Outil | Usage | Version trouvée | Version requise | État | Que faire ? | Scénarios indisponibles |
|---|---|---|---|---|---|---|
| git | Tous les scénarios | 2.47.0 | ≥ 2.x | ✓ OK | — | 0 |
| uv | Installation et lancement | 0.8.4 | ≥ 0.5 | ✓ OK | — | 0 |
| gitleaks | Hook pre-commit, Stations 1 et 3 | absent | fixée en architecture | ✗ Absent | Dépliable : installation sans droits administrateur | 3 |

- Les versions minimales sont illustratives ; l'architecture les fixe. La page le dit dans une note discrète.
- Chaque état s'écrit en mots avec une icône : ✓ OK, ⚠ Trop ancien, ✗ Absent.
- La colonne « Scénarios indisponibles » nomme les scénarios touchés sous le nombre.
- La section Proxy montre le proxy détecté (valeur en partie masquée `[ASSUMPTION]`), si `NO_PROXY` contient `127.0.0.1` et `localhost`, et l'état des certificats (`UV_SYSTEM_CERTS`). Chaque ligne a son « Que faire ? ».
- Sans git, rien ne fonctionne : un `notice-card` d'erreur donne la cause et l'action ; le catalogue reste visible, avec tous les scénarios grisés.
- Sans un outil de la chaîne, seuls ses scénarios sont grisés ; « Continuer vers le catalogue » reste proposé.
- Le diagnostic est aussi écrit dans la console de lancement (Flow 3).

## Pipeline simulé et trois écritures

Au service de FR-22 et FR-23 (v0.2).

- Chaque push sur une branche qui a une PR relance le pipeline simulé : un `pr-check` par outil (ruff, pytest, gitleaks, bandit, pip-audit, quality gate), dans l'ordre du pipeline.
- Chaque check requis par la protection de `main` porte l'étiquette « Obligatoire ».
- Un échec désigne fichier, ligne et règle (bandit), dépendance et vulnérabilité (pip-audit), couverture mesurée et seuil (quality gate) (FR-24 à FR-26).
- « Voir dans le pipeline » ouvre `pipeline-tabs` dans Code : GitHub Actions | Jenkins (`Jenkinsfile`) | GitLab CI (`.gitlab-ci.yml`), en lecture seule. Les lignes de la tâche sont surlignées et chaque onglet indique « lignes 12 à 18 » pour la même tâche.
- Changer d'onglet garde la tâche. Survoler un check éclaire ses lignes dans l'onglet ouvert.
- Rien ne s'exécute depuis ces fichiers (FR-23).

## Livraison (Station 4 · Livraison, v0.3)

Au service de FR-29 à FR-31. L'onglet « Livraison » s'ajoute à la vue Distant + PR `[ASSUMPTION]`.

- `git tag -a v1.2.0` crée un tag visible dans le graphe ; une fois poussé, il apparaît sur `origin`. Un tag non SemVer est refusé par `terminal-refused` : « Refusé : `v1.2` ne suit pas SemVer (MAJEUR.MINEUR.CORRECTIF). ».
- « Construire la version taguée » produit un `build-artifact` qui porte le numéro du tag.
- Deux `env-card`, Staging puis Prod simulée, montrent chacune leur version servie.
- Sans approbation, `promotion-gate` refuse la promotion et dit pourquoi ; l'approbation entre dans le `review-log` de la livraison.
- Le Rollback (`button-danger`) de la prod simulée demande une confirmation en ligne, puis annonce : « La prod simulée sert de nouveau v1.1.0. ».
- Le flow de la Station 4 · Livraison reste à écrire (question ouverte 1).

## Vocabulaire

Au service de FR-33 (v0.2).

- La page liste les termes cibles (secrets scanning, SAST, SCA, SBOM, quality gate, quatre yeux, protection de branche, traçabilité, DAST). Chaque terme a une définition en deux phrases, sa barrière et le lien « Voir la barrière ».
- Dans les explications, ces termes sont des `glossary-term`.
- « Voir la barrière » sélectionne la barrière si elle est dans l'état courant ; sinon, il déplie la carte sur son nœud, avec « La voir jouer : scénario <nom> » `[ASSUMPTION]`.
- DAST porte « Nommé seulement » et ne mène à aucune barrière.
- En v0.2, « traçabilité » mène aux PR et aux checks ; le tag et l'approbation de livraison s'ajoutent en v0.3.

## Exports

**Rapport de progression (FR-36, v0.1).** « Exporter mon rapport » ouvre `report-preview`, qui liste le contenu du rapport : scores, indices, remises à zéro et horodatages, par parcours. Il précise : « Rien n'est envoyé. Vous choisissez à qui transmettre ce fichier. » (NFR-9). L'export produit deux fichiers, comme la fiche : un HTML autonome lisible (imprimable en PDF) et un CSV en UTF-8 avec BOM. Les boutons sont « Exporter en HTML » et « Exporter en CSV ».

**Fiche barrière → risque → preuve (FR-35).** `barrier-sheet` a une ligne par barrière et ces colonnes : Barrière | Risque | Preuve | ISO 27001 | NIS2 | DORA | CRA. Chaque correspondance porte « explicite » ou « interprétation ». Les contrôles ISO sont cités par numéro et intitulé court. Une barrière dont la preuve n'a pas été vue affiche « Preuve pas encore vue : scénario <nom> » `[ASSUMPTION]`. La fiche s'exporte en HTML imprimable et en CSV pour le tableur ; le HTML reprend l'identité en version impression.

## Responsive & Platform

| Fenêtre | Comportement |
|---|---|
| 1920×1080 ou plus | Disposition principale complète. |
| Plus petite | Repli par masquage : des vues passent en puces. Ordre `[ASSUMPTION, question ouverte 3]` : d'abord les vues que l'étape n'utilise pas, puis Distant + PR, puis Code. Le panneau Scénario, le Dépôt local et le Terminal restent visibles. |
| Moins de 1280 px de large | Le panneau Scénario reste à gauche, avec une seule vue agrandie à droite ; les autres passent en puces `[ASSUMPTION]`. |
| 640 px ou moins (zoom fort) | Le panneau Scénario passe au-dessus et la vue agrandie dessous, sur une colonne (voir Accessibility Floor > Zoom et mouvement). |

- L'application tourne sous Windows 10/11, macOS et Linux, dans les navigateurs récents du poste `[ASSUMPTION : Chromium, Firefox, Safari]`. Les scénarios s'y comportent de la même façon (NFR-5).
- La fenêtre pywebview de repli a la même interface ; les exports y passent par la boîte d'enregistrement du système `[ASSUMPTION]`.
- Le zoom du navigateur est respecté : à 125 % sur 1920×1080, le repli par masquage s'applique.
- Le mobile et le tactile ne sont pas visés.

## Inspiration & Anti-patterns

- **Repris de Oh My Git!** : vrai git, mise en place déclarative par scénario, validation sur l'état réel du dépôt (FR-11, FR-14).
- **Repris de Learn Git Branching** : le graphe comme vue principale, mis à jour à chaque commande. **Rejeté** : le git simulé (NFR-2) et le compteur de coups, qui pousse à deviner.
- **Repris de Githug** : « indice » et « recommencer » à la demande. **Rejeté** : le terminal seul, sans vue de l'état.
- **Rejeté de Git-it et GitHub Skills** : la dépendance à un compte ou à un service en ligne (NFR-1).
- **Repris de WaveStack** : vues liées, explication attachée, volets masquables, diagnostic, identité.
- **Rejeté (pédagogie, addendum)** :
  - la pénalité d'indice et le compteur visible, qui entretiennent l'évitement de l'aide (*help avoidance* : l'apprenant n'ose plus demander) : aucun compteur pendant l'étape ;
  - le clic jusqu'au dernier palier sans lire (*bottom-out* : la solution complète obtenue en enchaînant les indices) : la solution se débloque après un essai ou un moment de lecture et ne se copie pas ;
  - le menu d'explications contourné par essais successifs : désignation dans les vues, un seul essai.
- **Rejeté** : la télémétrie, même facultative (NFR-9). Seul le rapport exporté par l'apprenant quitte la machine.

## Key Flows

### Flow 1 — UJ-1 : Anaël termine le socle git sans indice (v0.1)

1. Anaël lance l'application ; le navigateur s'ouvre sur le catalogue, avec le parcours LLM choisi.
2. Il ouvre « Branche », mode A. La consigne lui demande de créer une branche `feature` et de s'y placer.
3. Il tape `git switch -c feature`. Le terminal montre la sortie de git ; le graphe montre `feature` avec « Nouveau » et HEAD qui la suit ; puis l'explication s'affiche.
4. L'étape est validée sur l'état réel. Vient le premier des trois quiz du scénario : trois commandes pour défaire le dernier commit.
5. Pour tester, il choisit exprès `git reset --hard HEAD~1`. La commande s'exécute ; le graphe montre le commit perdu en tirets ; le `quiz-banner` apparaît ; l'explication dit comment `reflog` le retrouve.
6. Il tape `git reflog`, accepté en lecture seule, puis clique « J'ai compris, rétablir l'état ». Le commit revient avec « Rétabli ». Il rechoisit la bonne commande.
7. Il réussit les deux autres quiz du premier coup.
8. **Climax :** le bilan affiche « 2 sur 3 du premier coup · 0 indice ». L'erreur volontaire est comptée, comme prévu.
9. Il clique « Scénario suivant : PR / merge ».

Échec : si le rétablissement échoue, un `notice-card` d'erreur propose « Recommencer » ; son score du premier coup est conservé.

### Flow 2 — UJ-2 : Camille installe seule, puis comprend ce que l'agent a fait (v0.1)

1. Camille colle la commande unique d'installation dans PowerShell, sans droits administrateur.
2. L'application s'ouvre sur le Diagnostic : « git 2.47.0 ✓ OK ». Elle clique « Continuer vers le catalogue » et choisit un parcours.
3. Elle enchaîne branche, PR / merge (« Ouvrir une PR », revue du collègue simulé, Merger), conflit (résolu dans la vue Code, puis `git add` et `git commit`) et récupération par `reflog`.
4. Elle ouvre « add / commit », mode B. Le graphe montre deux commits avec le badge « Agent ».
5. Le panneau demande « Qu'a fait l'agent ? ». Elle survole les commits : le diff de l'un montre `.env`.
6. Elle clique « Désigner dans les vues », puis la ligne `API_KEY=…` du diff. La ligne se place dans la case.
7. Elle clique « Valider ma réponse ».
8. **Climax :** la ligne fait partie des bonnes réponses. Elle porte « ✓ Votre choix », le commit principal « ✓ Attendu » et `.env` « ≡ Accepté aussi ». L'explication s'affiche. Camille sait dire, graphe à l'appui, ce que l'agent a fait.
9. Elle retire le secret de l'historique, puis lit l'encart des barrières qui l'auraient bloqué (gitleaks en Station 1 · Poste local, secrets scanning), avec « Arrive en v0.2 » tant que la station n'est pas livrée `[ASSUMPTION]`.

Échec : si elle désigne un autre commit, il porte « ✗ Votre choix » et le bon « ✓ Attendu » ; l'explication est la même ; le score du premier coup enregistre l'échec.

### Flow 3 — Camille derrière le proxy (cas limite de UJ-2)

1. Le script d'installation échoue au téléchargement. Il écrit en français si un proxy est détecté, quelles variables régler (`HTTPS_PROXY`, `UV_SYSTEM_CERTS=true`) et comment passer par un clone ou un zip (FR-18).
2. Camille règle les variables et relance ; l'installation passe.
3. Au lancement, le navigateur passe par le proxy et n'atteint pas `127.0.0.1`. La console de lancement l'a prévu : si le port est occupé, elle en choisit un autre ; elle affiche l'adresse locale, rappelle d'ajouter `127.0.0.1` et `localhost` à `NO_PROXY`, et propose la fenêtre pywebview `[ASSUMPTION]`.
4. **Climax :** la page s'ouvre sur le Diagnostic. La section Proxy montre « Proxy détecté », « `NO_PROXY` ✓ » et « Certificats système ✓ ». Camille sait ce qui a été réglé et pourquoi.
5. Si gitleaks manque encore (v0.2+), sa ligne dit quoi faire ; ses scénarios sont grisés, le reste est ouvert.

Échec : si le navigateur n'atteint toujours pas `127.0.0.1`, elle lance la fenêtre pywebview proposée par la console ; l'interface est la même.

### Flow 4 — UJ-3 : Camille voit une PR bloquée en Station 3 (v0.2)

1. Pendant un atelier d'une heure, Camille ouvre dans le parcours LLM le scénario « outil trop puissant ». Le bandeau montre « Station 3 · Sécurité et qualité » avec « Vous êtes ici ».
2. Elle pousse sa branche et ouvre la PR. Les checks passent « En cours ».
3. bandit passe en « ✗ Échec · Obligatoire ». Elle clique le check : la vue Code surligne la ligne, la sortie de bandit nomme la règle, et la carte éclaire la barrière SAST.
4. `merge-blocked` liste « bandit en échec » et « Approbations : 0 sur 2 ».
5. Elle corrige le code, committe et pousse. bandit passe « ✓ Réussi ».
6. pip-audit échoue et nomme la dépendance et sa vulnérabilité. « Voir le SBOM » ouvre `sbom-view` ; elle met à jour la dépendance dans `pyproject.toml` et pousse.
7. La quality gate affiche « Couverture du nouveau code 86 % · seuil 80 % · ✓ ». Les deux approbations arrivent dans le `review-log` `[ASSUMPTION, question ouverte 6]`.
8. **Climax :** Merger devient actif. Sur chaque check vert, « Voir dans le pipeline » montre ses lignes dans GitHub Actions, Jenkins et GitLab CI.
9. Elle merge ; le graphe montre `main` à jour sur `origin`.

Échec : si elle tente `git push origin main`, la protection de `main` refuse le push pour de vrai, avec l'explication.

### Flow 5 — UJ-4 : Karim répond au RSSI et repart avec la fiche (au plus tard v1.0)

1. Karim ouvre « Entretien RSSI » dans « Savoir en parler ». Les vues montrent un dépôt où les barrières ont joué : checks, journal de revue, SBOM, tag `[ASSUMPTION]`.
2. Question : « Qu'est-ce qui empêche une clé d'API d'arriver sur `main` ? ». Il choisit « Le hook pre-commit gitleaks, puis le check gitleaks de la PR ».
3. « Valider ma réponse » reste inactif et dit : « Il manque la preuve. Désignez-la dans les vues. »
4. Il ouvre « Choisir dans la liste », filtre « gitleaks » et choisit le bloc de sortie de gitleaks, dans le groupe Terminal. La preuve se place ; le bouton s'active.
5. Il valide. La correction s'affiche dans les vues et dans le panneau.
6. Il enchaîne les questions : check en échec, journal de revue (deux approbations), ligne du SBOM.
7. **Climax :** le bilan affiche « 7 sur 8 du premier coup » (80 % ou plus, SM-7), puis « Ouvrir la fiche ».
8. La fiche liste chaque barrière, son risque, sa preuve et ses correspondances ISO 27001, NIS2, DORA et CRA. Il l'exporte en HTML et en CSV.
9. Il ouvre le CSV dans son tableur et imprime le HTML en PDF pour son rendez-vous.

Échec : s'il désigne le bon outil pour la mauvaise barrière, la question est échouée ; la preuve attendue porte « ✓ Attendu ».

## Questions ouvertes

**Bloquantes** : aucune. Anaël a tranché le 2026-10-18 (`.memlog.md`) les quatre questions bloquantes (commits perdus, langue de git, terminal pendant le quiz, format du rapport) et les deux constats de revue (règle de correction, désignation au clavier).

**Non bloquantes** (l'hypothèse en vigueur est marquée à l'endroit indiqué) :
1. Flow de la Station 4 · Livraison : le PRD le renvoie au découpage en stories ; l'UX sera mise à jour avant les stories v0.3 (Livraison).
2. Proportions de la disposition principale et largeur du panneau, validées sur maquette mais à confirmer en usage (Information Architecture).
3. Ordre de repli des vues sous 1920×1080 (Responsive & Platform).
4. Le mode désignation reste-t-il armé après un choix ? (Désignation, point 3)
5. Définition d'« un essai » pour débloquer la solution (Indices à paliers).
6. Approbations du GitHub simulé : automatiques quand les checks sont verts, ou demandées par l'apprenant ? (Flow 4)
7. Remises à zéro visibles au bilan, ou seulement dans le rapport ? (Exports)
8. Mode projection pour les ateliers avant le mode formateur (DESIGN.md > Typography).
9. « Reprendre » : rouvrir avec le bac à sable conservé, ou à l'étape sur un bac à sable reconstruit ? (Information Architecture > Catalogue)
