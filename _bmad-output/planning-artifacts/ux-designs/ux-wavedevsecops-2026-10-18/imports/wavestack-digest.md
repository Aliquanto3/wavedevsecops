# Digest identité WaveStack, pour WaveDevSecOps

Sources : WaveStack `ux-agentic-harness-training-demo-2026-09-22/{DESIGN,EXPERIENCE}.md`, lot 6 (`ux-lot-6-atelier-llm-2026-10-04`, survol), `src/wavestack/web/static/{tokens,fonts}.css`.
Écart livré / spécifié : contrôle par script des 56 couleurs claires et des couleurs sombres de `tokens.css` contre le frontmatter du DESIGN.md : aucune différence. Typo, rounded, spacing et `@font-face` relus : identiques. Aucun écart à signaler.
Direction : « atelier de construction » (grands arrondis, relief de jouet par ombre pleine sans flou, fond à pois), charte Wavestone, deux thèmes (clair, sombre, « Système » par défaut). Éléments propres à WaveStack (à ne pas reprendre tels quels) : robot du modèle, local/réseau, jaune = « sort du poste », palette de segments de contexte.

## 1. Tokens (verbatim)

```yaml
# CLAIR (tokens.css :root, variables --color-<nom>)
colors-light:
  primary: '#451DC7'            # marque, boutons primaires, focus
  primary-deep: '#250F6B'
  primary-soft: '#EDE7FE'
  accent: '#04F06A'             # vert : "en action" et "OK", jamais en texte
  accent-soft: '#CAFEE0'
  ink: '#0A0A14'
  ink-soft: '#4A4A5E'
  muted: '#8A8A9E'
  line: '#E6E6EC'
  surface: '#F6F5FA'            # fond de page (+ pois)
  surface-raised: '#FFFFFF'     # volets, cartes
  warning: '#FFCA4A'
  danger: '#FF2A49'
  on-primary: '#FFFFFF'
  relief: '#D9D0F6'             # ombre pleine
  relief-active: '#C9BCF5'
  dot: '#D6CCF5'                # pois du fond
  hosting-network: '#FFCA4A'
  hosting-boundary: '#0A0A14'
  state-active: '#04F06A'
  state-ok: '#04F06A'
  state-blocked: '#FF2A49'
  state-error: '#FF2A49'
  state-unavailable: '#8A8A9E'
  segment-system-prompt: '#6B4EE6'
  segment-global-memory: '#27B060'
  segment-tool-descriptions: '#2A78D6'
  segment-history: '#B39CF7'
  segment-rag: '#0E8C7E'
  segment-tool-results: '#E0762B'
  segment-message: '#9C5BB5'
  segment-free: '#F6F5FA'
  discipline-prompt: '#451DC7'
  discipline-prompt-soft: '#EEE9FC'
  discipline-context: '#0F7B6C'
  discipline-context-soft: '#E2F3EF'
  discipline-harness: '#B8327A'
  discipline-harness-soft: '#FBE7F1'
  discipline-network: '#D9A400'
  discipline-network-soft: '#FFF5D1'
  discipline-neutral: '#8A8A9E'
  discipline-neutral-soft: '#EFEFF4'
  on-ink: '#FFFFFF'
  on-ink-soft: '#CFCDE4'
  produced-soft: '#E8EEF7'
  reasoning-soft: '#F3EFE3'
  json-key: '#1E3A8A'
  json-string: '#7A3410'
  json-literal: '#0B5E73'
  ink-fill: '#0A0A14'           # fond des éléments clés (barre, numéro de volet, bulle)
  ink-fill-edge: '#0A0A14'
  on-discipline: '#FFFFFF'      # texte sur prompt/context/harness
  on-vivid: '#0A0A14'           # texte sur jaune/vert/rouge/gris
  warning-soft: '#FFF4D6'
  danger-soft: '#FDE8EB'
  logo-tile: '#FFFFFF'
# SOMBRE (tokens.css :root[data-theme="dark"] ET @media (prefers-color-scheme: dark) :root:not([data-theme]) ; mêmes noms de variables)
colors-dark:
  primary: '#9C86FF'
  primary-deep: '#C9BDFF'
  primary-soft: '#2A2350'
  accent: '#04F06A'
  accent-soft: '#0F3A24'
  ink: '#ECEBF5'
  ink-soft: '#B4B3C7'
  muted: '#8A8A9E'
  line: '#3A394F'
  surface: '#12121C'
  surface-raised: '#1E1D2C'
  warning: '#FFCA4A'
  danger: '#FF6B7F'
  on-primary: '#0E0B1E'
  relief: '#2A2156'
  relief-active: '#3A2E78'
  dot: '#262538'
  hosting-network: '#FFCA4A'
  hosting-boundary: '#ECEBF5'
  state-active: '#04F06A'
  state-ok: '#04F06A'
  state-blocked: '#FF6B7F'
  state-error: '#FF6B7F'
  state-unavailable: '#8A8A9E'
  segment-system-prompt: '#8C74FF'
  segment-global-memory: '#3CC878'
  segment-tool-descriptions: '#4F95EA'
  segment-history: '#A48EF0'
  segment-rag: '#1FB3A2'
  segment-tool-results: '#F08A42'
  segment-message: '#C07FDA'
  segment-free: '#2A2938'
  discipline-prompt: '#9C86FF'
  discipline-prompt-soft: '#262047'
  discipline-context: '#2FB8A3'
  discipline-context-soft: '#12302B'
  discipline-harness: '#E8639F'
  discipline-harness-soft: '#3A1A2B'
  discipline-network: '#E8B516'
  discipline-network-soft: '#3A3010'
  discipline-neutral: '#8A8A9E'
  discipline-neutral-soft: '#26252F'
  on-ink: '#FFFFFF'
  on-ink-soft: '#CFCDE4'
  produced-soft: '#1A2335'
  reasoning-soft: '#2A2618'
  json-key: '#9DBBFF'
  json-string: '#F2A77E'
  json-literal: '#6FD3E3'
  ink-fill: '#33257A'           # violet profond (en sombre, ne jamais utiliser ink en fond)
  ink-fill-edge: '#7C6AD6'
  on-discipline: '#0E0B1E'
  on-vivid: '#0A0A14'
  warning-soft: '#3A3010'
  danger-soft: '#3A1820'
  logo-tile: '#FFFFFF'
typography:                      # tokens.css --typography-<nom>-font-{family,size,weight,line-height}
  pane-title:    {fontFamily: "Fredoka, system-ui, sans-serif", fontSize: 18px, fontWeight: '600', lineHeight: '1.15'}
  pane-subtitle: {fontFamily: "'Atkinson Hyperlegible', system-ui, sans-serif", fontSize: 13px, fontWeight: '400', lineHeight: '1.3'}
  heading:       {fontFamily: "Fredoka, system-ui, sans-serif", fontSize: 18px, fontWeight: '600', lineHeight: '1.3'}
  chat:          {fontFamily: "'Atkinson Hyperlegible', system-ui, sans-serif", fontSize: 16px, fontWeight: '400', lineHeight: '1.5'}
  body:          {fontFamily: "'Atkinson Hyperlegible', system-ui, sans-serif", fontSize: 14px, fontWeight: '400', lineHeight: '1.5'}
  body-sm:       {fontFamily: "'Atkinson Hyperlegible', system-ui, sans-serif", fontSize: 13px, fontWeight: '400', lineHeight: '1.4'}
  label:         {fontFamily: "Fredoka, system-ui, sans-serif", fontSize: 12px, fontWeight: '500', lineHeight: '1.2'}
  number:        {fontFamily: "Fredoka, system-ui, sans-serif", fontSize: 14px, fontWeight: '600', lineHeight: '1.2'}
  number-lg:     {fontFamily: "Fredoka, system-ui, sans-serif", fontSize: 20px, fontWeight: '600', lineHeight: '1.1'}
  code:          {fontFamily: "'JetBrains Mono', 'Cascadia Mono', Consolas, ui-monospace, monospace", fontSize: 13px, fontWeight: '400', lineHeight: '1.5'}
rounded: {sm: 12px, md: 18px, lg: 26px, full: 9999px}
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 24px
  '6': 32px
  gutter: 8px
  pane-padding: 12px
  top-bar-height: 56px
  brick-panel-width: 280px          # propre à WaveStack
  architecture-band-height: 250px   # propre à WaveStack (schéma)
  stroke-min: 2px
  stroke-path: 3px
  hit-target-min: 32px
  relief-offset: 4px
  relief-offset-pressed: 1px
  relief-offset-overlay: 6px
  dot-grid: 18px
```

Notes de typographie et de style
- Fredoka 500/600 (titres, étiquettes, nombres ; chiffres tabulaires `tabular-nums`), Atkinson Hyperlegible 400/700 (interface), JetBrains Mono 400 (code). Licence OFL.
- Polices embarquées hors ligne : `fonts.css` déclare 5 `@font-face` (`font-display: swap`, WOFF2 latin, fontsource) vers `fonts/fredoka-latin-500-normal.woff2`, `fredoka-latin-600-normal.woff2`, `atkinson-hyperlegible-latin-400-normal.woff2`, `atkinson-hyperlegible-latin-700-normal.woff2`, `jetbrains-mono-latin-400-normal.woff2`. Aucun CDN ; licences à côté des fichiers.
- Aucun texte sous 12 px ; pas de tailles « display ».
- Mode projection : rampe x 9/7, redéfinie dans `app.css` sous `:root.projection` (absente de tokens.css) : pane-title et heading 23 px, pane-subtitle/body-sm/code 17, chat 21, body/number 18, label 15, number-lg 26, top-bar-height 72.
- Thème : `color-scheme` suit ; `theme.js` pose `data-theme` ; aucune couleur en dur hors `tokens.css`, pas de `filter: invert`.
- Fond de page : `surface` + pois `dot` de 1,3 px sur grille `dot-grid` 18 px, uniquement derrière les volets.
- Relief : `box-shadow: 0 4px 0 <relief>` (pas de flou) ; bouton primaire sur `primary-deep` ; enfoncé 1 px ; menus et tiroirs 6 px.
- À remapper pour WaveDevSecOps : les couleurs de discipline (prompt/context/harness/network/neutral) vers vos domaines (git, distant/PR, CI, sécurité...), en gardant « une couleur = un sens ». Les `segment-*`, `produced-soft`, `reasoning-soft`, `json-*` sont propres au contexte LLM.

## 2. Composants visuels réutilisables (DESIGN.md > Components)

- En-tête commun `site-nav` : fond surface-raised, bordure line, rounded.lg, marque en `heading` encre, liens en `label` x1,2 ink-soft ; page courante en ink soulignée 3 px primary ; focus contour primary 2 px ; menu « Affichage ▾ » à droite (thème, langue, projection) : fond surface, bordure line, rounded.md, label.
- Barre basse `top-bar` : fond `ink-fill`, texte `on-ink`, hauteur 56 px, rounded.lg, relief `relief`, liseré `ink-fill-edge` 2 px, focus `on-ink` 2 px, commandes bordées `on-ink-soft`, jamais sur deux lignes ; toujours visible, ne défile pas.
- Volet `pane` : fond surface-raised, sans bordure, rounded.lg, relief `relief`, padding pane-padding ; bandeau d'en-tête `surface` séparé par un filet `line` ; numéro de lecture `pane-step` (disque `ink-fill`, 1,7 em, chiffre `number` en `on-ink`, caché aux lecteurs d'écran) ; titre `pane-title` ink ; sous-titre d'une ligne `pane-subtitle` ink-soft qui dit ce que le volet montre ; boutons ⛶ (focus) et « — » (`pane-hide-button` : ink-soft, bordure line, rounded.sm, 32 px). Volet en mode focus : bordure primary.
- Puce de volet masqué `pane-chip` : « + Nom », fond primary-soft, texte primary, bordure primary en tirets, rounded.full, label ; « + Nom · lié » avec point encre si un élément lié est caché.
- Poignée de gouttière `pane-resize-handle` : invisible au repos, pilule primary 4 x 32 px au survol ou focus, zone de saisie >= 32 px, flèches clavier par pas de 16 px, double-clic = proportions par défaut.
- Menu `pane-menu` (« Volets ▾ ») : surface-raised, bordure line, relief `relief`, rounded.md, une case par volet.
- Vue liée `link-state` (sélection et correspondance) : survol ou focus = éléments liés avec anneau 2 px de leur couleur de discipline (encre pour réseau et neutre ; `on-ink` sur fond encre), les autres à opacité 0,35 ; sélection = contour `ink` 2 px décalé de 2 px, sans estomper ; transition 150 ms, supprimée sous reduced-motion.
- Explication attachée, trois formes : (a) explication dépliable dans `brick-card` (2 à 3 phrases) ; (b) consigne `scenario-info` : « i » italique serif dans un disque 1,5 em cerclé primary (cible 32 px), plein primary au survol ou ouvert, popover surface-raised, ombre de relief, 420 px max, `body-sm` ink-soft, titre primary-deep gras ; (c) infobulles de jauge et de segments (nom accessible = infobulle). Lot 6 : clic, Entrée ou Espace sur un nom de réglage affiche son explication dans une région `aria-live="polite"`, Échap la ferme, le `title` double l'encart. Pas de composant « bulle » dédié autre que ces formes.
- Carte `brick-card` (modèle de carte à interrupteur) : active = fond doux de discipline, trait gauche 5 px, relief `relief-active` ; éteinte = fond discipline-neutral-soft, texte ink-soft ; indisponible = à plat, bordure en tirets, raison toujours visible en ink-soft ; interrupteur `brick-toggle` (on = couleur de discipline, off = line, parent éteint = muted) ; ligne d'état en `body-sm`.
- Badges et pastilles d'état `state-pill` : fond surface, bordure line, rounded.full, label, point 12 px ; actif ou OK = fond accent-soft + point `state-ok` ; erreur = fond danger-soft + point `state-error` ; indisponible = point en tirets, texte ink-soft. Jamais la couleur seule, jamais jaune pour un état. `category-chip` : fond et bordure de la discipline, texte ink. `trigger-badge-model` : primary-soft / primary-deep ; `trigger-badge-user` : contour ink. Étiquettes « Nouveau » et « Produit » : `ink-fill` / `on-ink`.
- Boutons : `button-primary` fond primary, texte on-primary, relief primary-deep, rounded.md, min 32 px, descend de 4 à 1 px au clic ; `button-secondary` fond surface-raised, texte et bordure primary, relief relief-active ; `reset-button` neutre, sans relief (bordure line) ; `button-danger` fond surface-raised, bordure danger 2 px, texte ink, sans relief (confirmé : fond danger, texte on-vivid) ; `projection-toggle` pressé = primary / on-primary ; `theme-picker` = `select` natif (« ◐ Système », « ☀ Clair », « ☾ Sombre »).
- Événement `harness-event` : carte surface-raised, bordure line, rounded.md, filet latéral épais + icône (rouge blocage ou échec, primary information) ; `overflow-card` : bordure `state-error` 2 px, icône d'alerte ; `outbound-payload` : bordure en tirets, en-tête jaune (propre au réseau).
- Page de diagnostic `diagnostic-row` / `model-card` / `checks-panel` : page fond `surface` sans pois, 960 px max (1440 pour la grille de cartes) ; ligne fond accent-soft (OK), warning-soft (avertissement) ou danger-soft (échec), rounded.md ; pastille « OK » ou « Échec » avec texte `on-vivid` ; action corrective dessous ; résultat avec filet gauche 4 px `state-ok` / `warning` / `state-error` ; cartes `model-card` (grille >= 250 px, relief `relief`, actif = bordure ink 3 px) ; contrôles dans un panneau repliable ; titres de section en `pane-title`.
- Terminal / console : composant dédié absent. Proches existants : `event-log` (journal replié, `label` + chevron, nom technique en `code` ink-soft, JSON en `code` sur `surface`, sans couleur d'état), `json-tree`, `produced-block` (fond produced-soft, filet gauche 4 px ink, étiquette ink-fill / on-ink, texte `code`), `context-section` (filet gauche 4 px + fond doux). Le diagnostic est aussi écrit dans le terminal (texte, hors UI).
- Schéma d'architecture (équivalent carte de la chaîne) : zones `arch-zone-local` (surface-raised, libellé primary, rounded.lg) et `arch-zone-network` (surface, libellé jaune) séparées par `arch-boundary` (trait hosting-boundary 2 px) ; nœuds `arch-node-*` rounded.sm, fond doux et trait continu de la discipline, réseau = fond network-soft + bordure en tirets + filet 6 px, indisponible = tirets gris, actif = halo `state-active` (`arch-node-active`) ; flux `arch-flow` ink-soft 2 px (actif vert, tirets animés à la frontière) ; bacs `arch-group` (surface-raised, bordure line 2 px, rounded.md, titre `label` posé sur la bordure) ; catégories distinguées par forme et icône, la couleur dit la discipline ; cadre `arch-harness` bordure primary 2 px, relief relief-active. Traits >= 2 px. Lot 6 (`llm-stage`) : cartes d'étape numérotées, étiquette « Réel » (ink-fill) ou « Illustratif » (tirets, fond neutre), arcs et cellules en primary / discipline-context.

## 3. Règles comportementales transposables (EXPERIENCE.md)

- Découpe en volets (Information Architecture > Découpe retenue) : barre commune en tête, barre d'actions en bas, panneau de réglage à gauche sans numéro, volets de lecture numérotés 1 à N, chacun avec un sous-titre ; la densité prime, tout tient dans 1280 x 650 (cas de référence).
- Masquage (Masquage des volets) : « — » dans l'en-tête masque ; le volet devient la puce « + Nom » ; le menu « Volets ▾ » bascule chaque volet ; les volets visibles se partagent l'espace libéré ; au moins un reste visible (dernier « — » et sa case désactivés, infobulle « Au moins un volet reste visible. ») ; configuration et tailles mémorisées par le navigateur, conservées au changement de scénario et à la réinitialisation ; tailles minimales 240 px de large, 160 px de haut ; réafficher rend la dernière taille ; pas d'animation décorative.
- Mode focus (State Patterns) : ⛶ agrandit un volet, les autres se réduisent à titre + signal d'état ; Échap ou ⛶ revient ; la barre basse reste entière.
- Sélection et correspondances (Interaction Primitives > Vue liée) : chaque élément liable porte des clés de liaison issues du journal de la session (AD-1) ; deux éléments sont liés s'ils partagent une clé ; survol ou focus clavier = éclairage des liés dans tous les volets, les autres estompés ; clic, Entrée ou Espace = sélection persistante unique (contour encre), re-clic l'efface ; Échap efface (ordre : tiroir, menu Volets, panneau Fenêtre, sélection, mode focus) ; puce de volet masqué « · lié », un clic la réaffiche avec l'élément en évidence ; l'estompage n'est jamais le seul signal ; aucune information réservée au survol (la salle ne voit pas le pointeur) ; un toucher n'éclaire que le temps du geste.
- Direct par défaut (Interaction Primitives) : les volets suivent l'action en cours ; toute sélection manuelle les fige ; « Suivre le direct » relance.
- Explications attachées (Voice and Tone, Component Patterns) : explication dépliable de 2 à 3 phrases par brique ; sous-titre de volet qui dit ce qu'il montre ; raison toujours visible pour un élément indisponible ; le « pourquoi » est la matière pédagogique.
- États (State Patterns) : chargement = « ce qui se passe + chronomètre », jamais un spinner muet (« Lecture du contexte (1 840 tokens)… 6 s ») ; streaming sans reconstruire le volet, défilement qui suit sauf si l'utilisateur a remonté ; volet vide = texte qui dit quoi faire (« Aucun tour pour l'instant. Envoyez un message : … ») ; erreur pédagogique = événement nommé, cause, réaction, qui décide (« Bloqué par le hook garde-fou. Décision du harnais (code), pas du modèle. ») ; l'application ne plante jamais, un échec est matériau pédagogique (NFR-8) ; outil ou brique manquant = indisponible avec raison (« Indisponible : … exige … ») et le reste continue de fonctionner ; échec bloquant du diagnostic = ligne rouge + cause + action, échec non bloquant = bouton « Continuer » ; pendant un échange en cours, les autres actions sont refusées avec la raison ; réinitialisation = retour à l'état nu avec message de confirmation.
- Accessibilité (Accessibility Floor) : jamais la couleur seule (icône + libellé) ; tout atteignable au clavier dans l'ordre de lecture (barre commune, réglages, volets 1 à N, barre basse), volets masqués sautés ; focus visible `primary` 2 px ; cibles >= 32 px ; traits >= 2 px ; volets en régions nommées ; streaming annoncé à la fin du tour (`aria-live` poli), blocages et échecs annoncés tout de suite ; puces « Réafficher le volet Nom » et « Masquer le volet Nom » ; contrastes AA dans les deux thèmes (4,5:1 texte, 3:1 traits porteurs de sens) ; `prefers-reduced-motion` : halos et flux deviennent surbrillance fixe, transitions de la vue liée coupées, information identique ; animation réservée au signal « en action » et au fondu de 150 ms.
- Interdits d'interaction (Interaction Primitives > Bannis) : modales bloquantes en démonstration, notifications qui masquent un volet, troncature automatique, information au seul survol, défilement automatique qui reprend la main, texte brut ou JSON déplié sans demande.
- Responsive (Responsive & Platform) : application desktop seule, pas de mobile ; fenêtre de référence 1280 x 650 CSS ; aucun masquage automatique sous 1280 px ; sous 1024 px le mode focus devient le seul mode ; mode projection pour la salle et la visio ; sous 1400 px les libellés se compactent (noms tronqués, entiers en infobulle) ; pages annexes 960 px max ; grille de cartes 4 à 5 colonnes à 1440, 3 à 1280, 2 en projection, 1 sous 640 px ; polices et ressources servies en local, fonctionnement sans réseau.
- Voix et ton (Voice and Tone) : français, vouvoiement, phrases courtes et complètes, pas de point d'exclamation, pas d'emoji, pas de jargon d'erreur brut ; un message d'état = ce qui se passe + pourquoi (une phrase) + action possible ; toujours nommer qui décide ; nombres précis (« 1 840 tokens », « 6 s ») ; termes anglais consacrés conservés ; titres en casse normale.
- Page de diagnostic (State Patterns, Responsive) : au premier démarrage, lignes de contrôle « En cours » puis OK ou Échec ; recherche en cours avec compteur « {n} sur {N} » et barre de progression, jamais « Aucun candidat » avant la fin ; états en un ou deux mots (« Actif », « Disponible », « Avertissement », « Incompatible », « Erreur », « Chargement… ») ; cartes dépliables (bouton nommé avec son état, `aria-expanded`, Échap replie) ; compteur de filtres annoncé en `aria-live` poli ; diagnostic consultable depuis la barre commune.

## 4. Do's and Don'ts de WaveStack (DESIGN.md, plus lot 6)

Do
- Une couleur = un sens (disciplines, jaune = ce qui sort du poste, vert = en action ou OK, rouge = bloqué ou échec).
- Icône + libellé + couleur pour tout état ; étiquettes de segment hors du segment, en encre, avec légende.
- Traits >= 2 px dans le schéma.
- Polices servies en local (WOFF2 + `@font-face`).
- Tokens de charte pour l'encre, les neutres et les violets.
- Relief jouet : ombre pleine sans flou, 4 px (1 px enfoncé, 6 px tiroirs et menus), couleurs de relief ; relief seulement sur les pièces posées sur la page.
- Grands arrondis 12 / 18 / 26 px et pilule.
- Pois uniquement sur le fond de page.
- Un sous-titre par volet qui dit ce qu'il montre.
- Distinguer les catégories du schéma par bac, forme et icône ; la couleur dit la discipline.
- Animations réservées au signal « en action » et au fondu 150 ms, coupées sous reduced-motion.
- Chaque couleur par un jeton de `tokens.css` avec son jumeau sombre.
- Fond d'encre = `ink-fill` ; texte sur fond vif = `on-vivid` explicite ; palette sombre dessinée jeton par jeton.
- Lot 6 : écrire « Illustratif » en plus des tirets ; écrire chaque poids et pourcentage ; n'afficher que des valeurs reçues de la session.

Don't
- Jaune comme avertissement générique ; coder un état ou un lieu par la seule couleur ; blanc sur les segments bleu ou vert d'eau.
- Traits fins ou gris clair ; police chargée depuis un CDN ; neutres teintés lilas de la maquette (`#1C1535`, `#EFEBFB`...).
- Ombre floue, `rgba`, dégradé ; relief sur messages, segments ou pièces indisponibles ; rayons hors échelle ou angles vifs.
- Pois ou motif derrière du texte, dans un volet ou une carte ; sous-titre décoratif ou répétant le titre.
- Une couleur par catégorie de composant ; robot décoratif ou animé au repos (propre à WaveStack).
- Curseur personnalisé, révélations au scroll, compteurs animés.
- Couleur écrite en dur hors `tokens.css` ; `ink` en fond (devient clair en sombre) ; texte hérité sur fond vif ; `filter: invert` ou palette calculée en JS.
- Logo chargé d'un CDN, recoloré ou inversé.
- Lot 6 : présenter l'illustratif comme lu dans le moteur ; introduire une couleur hors jetons ; carte d'étape plus haute que l'écran à 1366 x 768.
- Rejeté (EXPERIENCE > Inspiration & Anti-patterns) : cacher des étapes pour paraître rapide, tronquer le contexte par défaut, code couleur seul pour local/réseau.

## 5. Contrastes déjà vérifiés (WCAG, `tests/test_web_tokens.py`)

Clair
- on-ink sur ink 19,7 ; on-ink-soft sur ink 12,7 ; primary sur blanc 9,3 ; ink sur accent 12,8 ; ink sur hosting-network 12,9 ; ink sur discipline-network 8,7.
- on-ink sur discipline-prompt 9,3, context 5,2, harness 5,6 (seuil 4,5) ; ink-soft sur chaque fond doux >= 7,2.
- prompt, context, harness, neutral sur surface-raised >= 3,4 (seuil 3) ; muted 3,4 (non textuel seulement).
- Échecs documentés : accent sur blanc 1,5 ; hosting-network sur blanc 1,5 ; discipline-network sur blanc 2,3 ; danger sur blanc 3,7 (donc fond avec texte on-vivid 5,3, filet ou icône, jamais petit texte) ; violet sur encre 2,1 ; blanc sur segment-tool-descriptions 4,4 et segment-rag 4,1 ; encre sur segment-message 4,3.
- produced-soft : ink 16,9, ink-soft 7,4 ; reasoning-soft : ink 17,1, ink-soft 7,5 ; json-key >= 8,7, json-string >= 7,6, json-literal >= 6,2.

Sombre
- ink et ink-soft sur surface, surface-raised, primary-soft, accent-soft, warning-soft, danger-soft et fonds doux >= 6,2 ; primary sur surface-raised 5,7 ; primary-deep sur primary-soft 8,4 ; on-primary sur primary 6,7.
- on-ink / on-ink-soft sur ink-fill 12,5 / 8,0 ; on-discipline sur prompt / context / harness 6,7 / 7,8 / 6,2 ; on-vivid sur jaune, vert, rouge, gris >= 5,8.
- prompt, context, harness, neutral sur surface et surface-raised >= 4,9 (seuil 3) ; ink-fill-edge sur surface et surface-raised >= 3,9 ; ink et ink-soft sur produced et reasoning >= 7,4 ; json-* >= 6,6 ; danger en texte sur surface-raised 6,0.
- ink-fill sur la page ne fait que 1,3 à 1,5 (d'où le liseré `ink-fill-edge`).
- Absent : ratios de `line` sur surface et de `relief` / `dot` (décoratifs, aucun seuil donné).
