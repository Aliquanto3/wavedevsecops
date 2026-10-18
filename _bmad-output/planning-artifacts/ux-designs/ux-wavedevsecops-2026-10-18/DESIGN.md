---
name: WaveDevSecOps
description: Atelier local pour apprendre git, GitHub simulé et la chaîne DevSecOps sur un vrai bac à sable, vue par vue. Identité reprise de WaveStack ; ce fichier reprend ses jetons tels quels et n'ajoute que les composants propres à WaveDevSecOps.
status: final
created: 2026-10-18
updated: 2026-10-18
sources:
  - imports/wavestack-digest.md
  - EXPERIENCE.md
colors:
  # Thème clair. Valeurs reprises de WaveStack (tokens.css :root).
  # Non repris : segment-* et reasoning-soft (propres au contexte LLM de WaveStack).
  primary: '#451DC7'
  primary-deep: '#250F6B'
  primary-soft: '#EDE7FE'
  accent: '#04F06A'
  accent-soft: '#CAFEE0'
  ink: '#0A0A14'
  ink-soft: '#4A4A5E'
  muted: '#8A8A9E'
  line: '#E6E6EC'
  surface: '#F6F5FA'
  surface-raised: '#FFFFFF'
  warning: '#FFCA4A'
  danger: '#FF2A49'
  on-primary: '#FFFFFF'
  relief: '#D9D0F6'
  relief-active: '#C9BCF5'
  dot: '#D6CCF5'
  hosting-boundary: '#0A0A14'
  state-active: '#04F06A'
  state-ok: '#04F06A'
  state-blocked: '#FF2A49'
  state-error: '#FF2A49'
  state-unavailable: '#8A8A9E'
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
  json-key: '#1E3A8A'
  json-string: '#7A3410'
  json-literal: '#0B5E73'
  ink-fill: '#0A0A14'
  ink-fill-edge: '#0A0A14'
  on-discipline: '#FFFFFF'
  on-vivid: '#0A0A14'
  warning-soft: '#FFF4D6'
  danger-soft: '#FDE8EB'
  logo-tile: '#FFFFFF'
  # Thème sombre. Repris de WaveStack (:root[data-theme="dark"] et prefers-color-scheme: dark).
  primary-dark: '#9C86FF'
  primary-deep-dark: '#C9BDFF'
  primary-soft-dark: '#2A2350'
  accent-dark: '#04F06A'
  accent-soft-dark: '#0F3A24'
  ink-dark: '#ECEBF5'
  ink-soft-dark: '#B4B3C7'
  muted-dark: '#8A8A9E'
  line-dark: '#3A394F'
  surface-dark: '#12121C'
  surface-raised-dark: '#1E1D2C'
  warning-dark: '#FFCA4A'
  danger-dark: '#FF6B7F'
  on-primary-dark: '#0E0B1E'
  relief-dark: '#2A2156'
  relief-active-dark: '#3A2E78'
  dot-dark: '#262538'
  hosting-boundary-dark: '#ECEBF5'
  state-active-dark: '#04F06A'
  state-ok-dark: '#04F06A'
  state-blocked-dark: '#FF6B7F'
  state-error-dark: '#FF6B7F'
  state-unavailable-dark: '#8A8A9E'
  discipline-prompt-dark: '#9C86FF'
  discipline-prompt-soft-dark: '#262047'
  discipline-context-dark: '#2FB8A3'
  discipline-context-soft-dark: '#12302B'
  discipline-harness-dark: '#E8639F'
  discipline-harness-soft-dark: '#3A1A2B'
  discipline-network-dark: '#E8B516'
  discipline-network-soft-dark: '#3A3010'
  discipline-neutral-dark: '#8A8A9E'
  discipline-neutral-soft-dark: '#26252F'
  on-ink-dark: '#FFFFFF'
  on-ink-soft-dark: '#CFCDE4'
  produced-soft-dark: '#1A2335'
  json-key-dark: '#9DBBFF'
  json-string-dark: '#F2A77E'
  json-literal-dark: '#6FD3E3'
  ink-fill-dark: '#33257A'
  ink-fill-edge-dark: '#7C6AD6'
  on-discipline-dark: '#0E0B1E'
  on-vivid-dark: '#0A0A14'
  warning-soft-dark: '#3A3010'
  danger-soft-dark: '#3A1820'
  logo-tile-dark: '#FFFFFF'
  # Ajouts WaveDevSecOps [ASSUMPTION]. Valeurs copiées de jetons WaveStack existants, aucune teinte nouvelle.
  # Terminal : fond sombre dans les deux thèmes ; la paire claire/sombre ne change que le fond et le texte principal.
  terminal-bg: '#0A0A14'          # = ink-fill (clair)
  terminal-bg-dark: '#12121C'     # = surface-dark
  terminal-fg: '#FFFFFF'          # = on-ink
  terminal-fg-dark: '#ECEBF5'     # = ink-dark
  terminal-fg-soft: '#CFCDE4'     # = on-ink-soft ; stderr, messages de l'application
  terminal-fg-soft-dark: '#CFCDE4'
  terminal-accent: '#9C86FF'      # = primary-dark ; invite, filet des messages de l'application
  terminal-accent-dark: '#9C86FF'
  terminal-danger: '#FF6B7F'      # = danger-dark ; refus, code de sortie non nul
  terminal-danger-dark: '#FF6B7F'
  terminal-rule: '#8A8A9E'        # = muted ; filet stderr
  terminal-rule-dark: '#8A8A9E'
  terminal-lit-fill: '#3A1A2B'    # = discipline-harness-soft-dark ; ligne liée dans le terminal (link-state)
  terminal-lit-fill-dark: '#3A1A2B'
  terminal-lit-ring: '#E8639F'    # = discipline-harness-dark
  terminal-lit-ring-dark: '#E8639F'
  # Focus sur fond encre (terminal, ink-fill) : primary y tombe à 2,1:1.
  focus-on-ink: '#FFFFFF'         # = on-ink
  focus-on-ink-dark: '#FFFFFF'
typography:
  # Repris de WaveStack. Polices embarquées en WOFF2 (fonts.css), aucun CDN.
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
rounded:
  sm: 12px
  md: 18px
  lg: 26px
  full: 9999px
spacing:
  # Repris de WaveStack, sauf brick-panel-width et architecture-band-height (propres à WaveStack, non repris).
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 24px
  '6': 32px
  gutter: 8px
  pane-padding: 12px
  top-bar-height: 56px
  stroke-min: 2px
  stroke-path: 3px
  hit-target-min: 32px
  relief-offset: 4px
  relief-offset-pressed: 1px
  relief-offset-overlay: 6px
  dot-grid: 18px
  # Ajouts WaveDevSecOps [ASSUMPTION : valeurs à confirmer sur maquette 1920x1080]
  scenario-panel-width: 440px
  chain-band-height: 44px
  hit-target-dense: 24px        # cibles contiguës (lignes de diff, nœuds du graphe), WCAG 2.5.8
  graph-node-size: 14px         # disque visible ; la zone de clic couvre disque + SHA + message
  graph-row-height: 28px
  diff-line-height: 24px
  popover-max-width: 420px
  focus-ring-width: 2px
  focus-ring-offset: 2px
  pane-header-height: 44px
  progress-bar-height: 10px
  badge-height: 22px
  order-disc-size: 28px
  picker-height: 36px
  answer-slot-height: 40px
  list-max-height: 240px
  annex-max-width: 960px
  home-max-width: 1440px
components:
  # Repris de WaveStack ; modifiés : link-state, reset-button (bordure muted), diagnostic-row (pastilles pleines)
  site-nav: {background: '{colors.surface-raised}', border: '{colors.line}', radius: '{rounded.lg}', height: '{spacing.top-bar-height}', max-width: '{spacing.home-max-width}', current-underline: '{colors.primary}'}
  pane: {background: '{colors.surface-raised}', header-background: '{colors.surface}', header-height: '{spacing.pane-header-height}', radius: '{rounded.lg}', shadow: '{colors.relief}', padding: '{spacing.pane-padding}', title: '{typography.pane-title}', subtitle: '{typography.pane-subtitle}'}
  pane-step: {background: '{colors.ink-fill}', foreground: '{colors.on-ink}', type: '{typography.number}'}
  pane-chip: {background: '{colors.primary-soft}', foreground: '{colors.primary}', border: 'dashed {colors.primary}', radius: '{rounded.full}', type: '{typography.label}'}
  pane-resize-handle: {indicator: '{colors.primary}', hit-area: '{spacing.hit-target-min}'}
  pane-menu: {background: '{colors.surface-raised}', border: '{colors.line}', shadow: '{colors.relief}', radius: '{rounded.md}'}
  link-state: {linked-ring: '2px discipline color', linked-background: 'discipline-soft', dimmed-decor-opacity: '0.35', dimmed-text: '{colors.ink-soft}', selected-outline: '3px {colors.ink}', selected-mark: '●'}
  focus-ring: {color: '{colors.primary}', on-ink: '{colors.focus-on-ink}', width: '{spacing.focus-ring-width}', offset: '{spacing.focus-ring-offset}'}
  state-pill: {background: '{colors.surface}', border: '{colors.line}', radius: '{rounded.full}', ok-background: '{colors.accent-soft}', error-background: '{colors.danger-soft}'}
  button-primary: {background: '{colors.primary}', foreground: '{colors.on-primary}', shadow: '{colors.primary-deep}', radius: '{rounded.md}', min-height: '{spacing.hit-target-min}'}
  button-secondary: {background: '{colors.surface-raised}', foreground: '{colors.primary}', border: '{colors.primary}', shadow: '{colors.relief-active}', radius: '{rounded.md}'}
  reset-button: {background: '{colors.surface-raised}', foreground: '{colors.ink}', border: '{colors.muted}', radius: '{rounded.md}'}
  button-danger: {background: '{colors.surface-raised}', foreground: '{colors.ink}', border: '2px {colors.danger}', radius: '{rounded.md}'}
  theme-picker: {type: 'select natif', options: 'Système, Clair, Sombre'}
  explain-popover: {trigger-ring: '{colors.primary}', background: '{colors.surface-raised}', shadow: '{colors.relief}', max-width: '{spacing.popover-max-width}', type: '{typography.body-sm}', title: '{colors.primary-deep}'}
  diagnostic-row: {ok-background: '{colors.accent-soft}', warn-background: '{colors.warning-soft}', fail-background: '{colors.danger-soft}', radius: '{rounded.md}', pill-ok: '{colors.accent}', pill-warn: '{colors.warning}', pill-fail: '{colors.danger}', pill-foreground: '{colors.on-vivid}', group-rule: '2px {colors.ink-soft}'}
  tool-output: {background: '{colors.produced-soft}', rule: '4px {colors.ink}', tag-background: '{colors.ink-fill}', tag-foreground: '{colors.on-ink}', type: '{typography.code}'}
  # Ajouts WaveDevSecOps [ASSUMPTION : dérivés des jetons ci-dessus]
  # Panneau Scénario
  scenario-panel: {background: '{colors.surface-raised}', width: '{spacing.scenario-panel-width}', radius: '{rounded.lg}', shadow: '{colors.relief}', instruction: '{typography.chat}'}
  mode-badge: {background: '{colors.ink-fill}', foreground: '{colors.on-ink}', radius: '{rounded.sm}', type: '{typography.label}'}
  path-menu: {background: '{colors.surface-raised}', foreground: '{colors.ink}', border: '2px {colors.muted}', radius: '{rounded.md}', type: '{typography.label}', min-height: '{spacing.hit-target-min}'}
  step-explanation: {background: '{colors.surface-raised}', border: '2px {colors.muted}', rule: '4px {colors.primary}', barrier-rule: '4px {colors.discipline-harness}', radius: '{rounded.md}', title: '{typography.heading}'}
  step-progress: {done: '{colors.ink}', current: '{colors.primary}', upcoming: 'dashed 2px {colors.muted}', bar-height: '{spacing.progress-bar-height}', radius: '{rounded.full}', type: '{typography.number}', segment-target: '{spacing.hit-target-dense}'}
  quiz-choice: {background: '{colors.surface-raised}', border: '2px {colors.muted}', checked-border: '2px {colors.primary}', checked-background: '{colors.primary-soft}', radius: '{rounded.md}', command: '{typography.code}', min-height: '{spacing.hit-target-min}'}
  designate-button: {idle: '{components.button-secondary}', armed-background: '{colors.primary}', armed-foreground: '{colors.on-primary}', armed-text: 'Désignation active · Échap pour quitter'}
  designate-list: {background: '{colors.surface}', border: '2px {colors.muted}', group-title: '{typography.label}', item: '{typography.body-sm}', radius: '{rounded.md}', max-height: '{spacing.list-max-height}', overflow: 'défilement interne', item-height: '{spacing.graph-row-height}', chosen-background: '{colors.primary-soft}'}
  answer-slot: {empty-border: 'dashed {spacing.stroke-min} {colors.muted}', chip-background: '{colors.primary-soft}', chip-foreground: '{colors.primary-deep}', radius: '{rounded.md}', min-height: '{spacing.answer-slot-height}', remove-button: '{spacing.hit-target-min}'}
  sha-field: {background: '{colors.surface-raised}', border: '2px {colors.muted}', invalid-border: '2px {colors.danger}', type: '{typography.code}', radius: '{rounded.sm}', min-height: '{spacing.hit-target-min}'}
  hint-tabs: {active-underline: '3px {colors.primary}', locked-background: '{colors.discipline-neutral-soft}', locked-foreground: '{colors.ink-soft}', solution: '{typography.code}'}
  notice-card: {background: '{colors.surface-raised}', border: '2px {colors.muted}', rule: '4px', info-rule: '{colors.primary}', warn-rule: '{colors.warning}', error-rule: '{colors.danger}', radius: '{rounded.md}', title: '{typography.heading}'}
  quiz-banner: {background: '{colors.warning-soft}', rule: '4px {colors.warning}', foreground: '{colors.ink}', command: '{typography.code}'}
  score-summary: {score: '{typography.number-lg}', label: '{typography.label}', background: '{colors.surface}'}
  # Terminal
  terminal: {background: '{colors.terminal-bg}', foreground: '{colors.terminal-fg}', type: '{typography.code}', radius: '{rounded.md}', focus: '{colors.focus-on-ink}', linked-fill: '{colors.terminal-lit-fill}', linked-ring: '2px {colors.terminal-lit-ring}'}
  terminal-prompt: {foreground: '{colors.terminal-accent}', glyph: '$'}
  terminal-stderr: {foreground: '{colors.terminal-fg-soft}', rule: '2px {colors.terminal-rule}'}
  terminal-exit-error: {icon: '{colors.terminal-danger}', type: '{typography.label}'}
  terminal-app-message: {foreground: '{colors.terminal-fg-soft}', rule: '3px {colors.terminal-accent}', type: '{typography.body-sm}'}
  terminal-refused: {icon: '{colors.terminal-danger}', rule: '3px {colors.terminal-danger}', type: '{typography.body-sm}'}
  # Dépôt local
  graph-commit: {fill: '{colors.surface-raised}', stroke: '{spacing.stroke-path} {colors.discipline-prompt}', size: '{spacing.graph-node-size}', row: '{spacing.graph-row-height}', sha: '{typography.code}'}
  graph-edge: {stroke: '{spacing.stroke-min} {colors.ink-soft}'}
  graph-head: {background: '{colors.ink-fill}', foreground: '{colors.on-ink}', radius: '{rounded.sm}', type: '{typography.label}'}
  graph-branch: {background: '{colors.primary-soft}', foreground: '{colors.primary-deep}', border: '2px {colors.primary}', icon: 'poste', radius: '{rounded.full}', type: '{typography.label}'}
  graph-remote-ref: {background: '{colors.discipline-context-soft}', foreground: '{colors.ink}', border: 'double 4px {colors.discipline-context}', icon: 'serveur', radius: '{rounded.full}'}
  graph-tag: {background: '{colors.surface}', foreground: '{colors.ink}', border: '2px {colors.ink}', radius: '{rounded.sm}'}
  graph-commit-lost: {fill: '{colors.surface}', stroke: 'dashed {spacing.stroke-path} {colors.muted}', label: '{colors.ink-soft}'}
  graph-commit-colleague: {badge-border: '2px {colors.ink}', badge-foreground: '{colors.ink}', badge-text: 'Collègue'}
  graph-commit-agent: {badge-background: '{colors.primary-soft}', badge-foreground: '{colors.primary-deep}', badge-text: 'Agent'}
  commit-list: {type: '{typography.code}', header: '{typography.label}', row: '{spacing.graph-row-height}'}
  new-mark: {background: '{colors.ink-fill}', foreground: '{colors.on-ink}', text: 'Nouveau', restored-text: 'Rétabli'}
  staging-index: {staged-background: '{colors.accent-soft}', modified-border: '2px {colors.muted}', untracked-border: 'dashed 2px {colors.muted}', status-letter: '{typography.code}'}
  # Code
  code-editor: {background: '{colors.surface-raised}', syntax-key: '{colors.json-key}', syntax-string: '{colors.json-string}', syntax-literal: '{colors.json-literal}', type: '{typography.code}'}
  external-change-notice: {background: '{colors.primary-soft}', foreground: '{colors.ink}', type: '{typography.body-sm}'}
  diff-file-header: {type: '{typography.code}', meta: '{typography.body-sm}', meta-color: '{colors.ink-soft}', height: '{spacing.graph-row-height}', radius: '{rounded.sm}'}
  diff-view: {added-background: '{colors.accent-soft}', removed-background: '{colors.danger-soft}', hunk-background: '{colors.surface}', line-number: '{colors.ink-soft}', line-height: '{spacing.diff-line-height}', type: '{typography.code}'}
  pipeline-tabs: {readonly-tag: 'dashed 2px {colors.muted}', highlight-background: '{colors.primary-soft}', highlight-rule: '3px {colors.primary}'}
  sbom-view: {background: '{colors.surface-raised}', header: '{typography.label}', row: '{typography.code}', vulnerable-background: '{colors.danger-soft}', readonly-tag: 'dashed 2px {colors.muted}'}
  # Distant + PR
  pr-card: {background: '{colors.surface-raised}', border: '2px {colors.muted}', radius: '{rounded.md}', title: '{typography.heading}'}
  pr-check: {success: '{colors.accent-soft}', failure: '{colors.danger-soft}', pending: '{colors.primary-soft}', tool-error: '{colors.warning-soft}', pending-dot: '{colors.state-active}', pending-dot-border: '2px {colors.ink}', row-height: '{spacing.graph-row-height}', required-tag: '{colors.ink-fill}'}
  review-log: {rule: '2px {colors.ink-soft}', entry: '{typography.body-sm}', approved-mark: '{colors.accent-soft}', changes-mark: '{colors.danger-soft}', counter: '{typography.number}'}
  merge-blocked: {background: '{colors.discipline-neutral-soft}', foreground: '{colors.ink-soft}', reason: '{typography.body-sm}'}
  network-run-button: {background: '{colors.discipline-network-soft}', foreground: '{colors.ink}', border: '2px {colors.ink}', icon: 'réseau', radius: '{rounded.md}'}
  # Livraison, station 4 (v0.3)
  build-artifact: {background: '{colors.surface-raised}', border: '2px {colors.muted}', version: '{typography.code}', radius: '{rounded.md}'}
  env-card: {background: '{colors.surface-raised}', border: '2px {colors.discipline-harness}', title: '{typography.heading}', version: '{typography.code}', radius: '{rounded.md}'}
  promotion-gate: {blocked: '{components.merge-blocked}', approved-background: '{colors.accent-soft}'}
  # Chaîne et vocabulaire (v0.2+)
  chain-band: {background: '{colors.surface-raised}', height: '{spacing.chain-band-height}', current-background: '{colors.discipline-harness-soft}', current-rule: '3px {colors.discipline-harness}', here-pill: '2px {colors.discipline-harness}', boundary: '{spacing.stroke-min} {colors.hosting-boundary}'}
  chain-map: {background: '{colors.surface-raised}', shadow: '{colors.relief}', offset: '{spacing.relief-offset-overlay}', zone-radius: '{rounded.lg}', node-radius: '{rounded.sm}'}
  glossary-term: {underline: 'dotted {spacing.stroke-min} {colors.primary}', named-only-tag: 'dashed 2px {colors.muted}'}
  # Désignation et correction
  designable: {outline: 'dashed {spacing.stroke-min} {colors.primary}', outline-offset: 2px, hover-background: '{colors.primary-soft}'}
  verdict-mark: {expected-outline: '3px {colors.ink}', expected-badge: '{colors.accent}', chosen-outline: 'dashed 3px {colors.danger}', chosen-badge: '{colors.danger}', badge-foreground: '{colors.on-vivid}', equivalent-badge: 'dashed 2px {colors.ink}', badge-height: '{spacing.badge-height}', badge-radius: '{rounded.full}'}
  # Catalogue, diagnostic, exports
  path-picker: {background: '{colors.surface}', border: '2px {colors.muted}', selected-background: '{colors.primary}', selected-foreground: '{colors.on-primary}', radius: '{rounded.full}', type: '{typography.label}', height: '{spacing.picker-height}'}
  catalogue-section: {title: '{typography.pane-title}', subtitle: '{typography.pane-subtitle}', gap: '{spacing.5}', station-title: '{typography.number}', station-rule: '3px {colors.discipline-harness}', columns: 3}
  scenario-card: {background: '{colors.surface-raised}', radius: '{rounded.lg}', shadow: '{colors.relief}', unavailable-background: '{colors.discipline-neutral-soft}', unavailable-border: 'dashed 2px {colors.muted}', unavailable-text: '{colors.ink-soft}', order-disc: '{components.pane-step}', order-size: '{spacing.order-disc-size}', mode-divider: '2px {colors.line}'}
  diagnostic-badge: {background: '{colors.danger}', foreground: '{colors.on-vivid}', radius: '{rounded.full}', type: '{typography.number}', size: '{spacing.hit-target-dense}'}
  report-preview: {background: '{colors.surface-raised}', border: '2px {colors.muted}', radius: '{rounded.lg}', type: '{typography.body}', max-width: '{spacing.annex-max-width}'}
  barrier-sheet: {background: '{colors.surface-raised}', explicit-tag: '{colors.ink-fill}', interpretation-tag: 'dashed 2px {colors.ink}', print-background: '{colors.surface-raised}'}
---

# WaveDevSecOps — DESIGN

> **DESIGN.md et EXPERIENCE.md priment sur toute maquette ou import.** Source d'identité : [imports/wavestack-digest.md](imports/wavestack-digest.md) (jetons §1, composants §2, comportements §3, Do's and Don'ts §4, contrastes §5). Maquettes : [mockups/espace-travail.html](mockups/espace-travail.html), [mockups/designation-mode-b.html](mockups/designation-mode-b.html), [mockups/diagnostic.html](mockups/diagnostic.html), [mockups/catalogue.html](mockups/catalogue.html).
>
> FR et NFR : voir le PRD. Jalons v0.x : voir EXPERIENCE.md.

**Lexique.**
- *Pastille* : petit marqueur d'état ou de nombre (`state-pill`, `diagnostic-badge`).
- *Badge* : mot attaché à un élément pour le qualifier (« Mode A », « Agent », « ✓ Attendu »).
- *Étiquette* : mention fixe posée sur un élément (« HEAD », « Obligatoire », « Lecture seule », « Nouveau »).
- *Pilule* : forme seulement, arrondi `{rounded.full}`.
- *Carte* : objet posé sur la page, avec relief possible ; *encart* : bloc d'information dans un panneau, sans relief.

## Brand & Style

WaveDevSecOps est un atelier. On y casse un vrai dépôt git sans risque, on voit l'effet, on répare. L'identité reprend celle de WaveStack, l'« atelier de construction » de la même famille : grands arrondis, relief de jouet par ombre pleine sans flou, fond à pois, charte violette Wavestone. Elle a deux thèmes, Clair et Sombre, et une option Système (par défaut).

WaveDevSecOps réutilise les jetons de WaveStack ; il réaffecte le sens des couleurs de discipline et ajoute des composants : terminal, graphe git, index, diff, PR et checks, livraison, carte de la chaîne, désignation, indices. Les seuls jetons de couleur nouveaux (`terminal-*`, `focus-on-ink`) recopient des valeurs de WaveStack.

L'information prime. Les vues sont denses, la décoration minimale. Le vrai git parle en police mono ; l'application parle en Atkinson Hyperlegible. On ne doit jamais confondre une sortie de git et un message de WaveDevSecOps (NFR-2).

## Colors

Les valeurs sont reprises verbatim de WaveStack, en clair et en sombre (suffixe `-dark` = thème sombre, partout). Contrastes de WaveStack : [digest §5](imports/wavestack-digest.md).

**Une couleur = un sens.** Les couleurs de discipline gardent leurs valeurs et leurs noms ; leur sens change `[ASSUMPTION]` :

| Jeton | Sens dans WaveDevSecOps |
|---|---|
| `{colors.discipline-prompt}` (violet, = primary) | Dépôt local : commits, branches locales, HEAD, index |
| `{colors.discipline-context}` (vert d'eau) | Distant : refs de `origin`, PR du GitHub simulé |
| `{colors.discipline-harness}` (magenta) | Chaîne DevSecOps : stations, barrières, checks, pipeline simulé, livraison |
| `{colors.discipline-network}` (jaune foncé) | Ce qui sort du poste : seulement l'exécution facultative du code LLM (FR-17) |
| `{colors.discipline-neutral}` | Hors domaine, indisponible, « seulement nommé » |

**Deux jaunes, deux sens.** Le jaune clair `{colors.warning}` signale un état provisoire à surveiller : avertissement du diagnostic, bandeau « État modifié par le quiz ». Le jaune foncé `{colors.discipline-network}` signale ce qui sort du poste, sur un seul bouton (FR-17). Chacun vient toujours avec son icône (⚠ ou réseau), son texte, et une bordure ou une icône en `{colors.ink}`.

**États.**
- `{colors.state-ok}` / `{colors.accent}` : réussi, check vert. Ce vert a un contraste de 1,5:1 sur fond clair : on l'emploie en fond (`{colors.accent-soft}`) ou en point décoratif avec libellé, jamais en texte ni en trait.
- `{colors.state-active}` : « en cours ». Même teinte que `state-ok` : la forme (point animé) et le mot « En cours » les distinguent.
- `{colors.state-error}` / `{colors.danger}` : échec, blocage, refus. En fond doux, en filet de 3 px au moins, ou en badge avec `{colors.on-vivid}` (5,3:1) ; jamais en petit texte sur fond clair.
- `{colors.state-unavailable}` : outil manquant, scénario indisponible, onglet verrouillé. Le grisé utilise le fond `{colors.discipline-neutral-soft}` et le texte `{colors.ink-soft}`, sans opacité.

**Terminal.** Le terminal garde un fond sombre dans les deux thèmes et a ses propres jetons (`terminal-*`). Seuls le fond (`{colors.terminal-bg}`) et le texte principal (`{colors.terminal-fg}`) changent avec le thème ; les autres jetons `terminal-*` ont la même valeur dans les deux. Usage : Components > Terminal.

**Code.** La coloration syntaxique utilise `{colors.json-key}`, `{colors.json-string}` et `{colors.json-literal}`, sans autre teinte.

**Bordures porteuses.** Une bordure qui délimite un champ, une case ou un bouton est en `{colors.muted}` 2 px (3,4:1 en clair, 4,9:1 en sombre). `{colors.line}` (1,2:1) ne sert qu'aux filets décoratifs.

**Non repris :** `segment-*`, `reasoning-soft` et `hosting-network` (propres à WaveStack). `produced-soft` sert aux blocs de sortie d'outil.

### Contrastes des combinaisons ajoutées

Calculés selon la formule WCAG.

| Combinaison | Seuil | Clair | Sombre |
|---|---|---|---|
| `terminal-fg` / `terminal-bg` | 4,5 | 19,7 | 15,7 |
| `terminal-fg-soft` / `terminal-bg` | 4,5 | 12,7 | 12,0 |
| `terminal-accent` / `terminal-bg` | 4,5 | 6,8 | 6,4 |
| `terminal-danger` / `terminal-bg` | 4,5 | 7,2 | 6,8 |
| `terminal-rule` / `terminal-bg` | 3 | 5,8 | 5,5 |
| `focus-on-ink` / `terminal-bg` | 3 | 19,7 | 18,1 |
| `on-vivid` / `danger` (badges) | 4,5 | 5,3 | 7,2 |
| `primary-deep` / `primary-soft` (case de réponse, badge Agent) | 4,5 | 12,9 | 8,4 |
| `ink-soft` / `discipline-neutral-soft` (grisé, verrouillé) | 4,5 | 7,5 | 7,4 |
| `muted` / `surface-raised` (bordures porteuses) | 3 | 3,4 | 4,9 |
| `danger` tirets / `surface-raised` (choix faux) | 3 | 3,7 | 6,1 |
| `discipline-context` / `discipline-context-soft` (ref distante) | 3 | 4,5 | 5,7 |
| `primary` / `surface-raised` (focus, désignable) | 3 | 9,3 | 5,7 |

## Typography

La rampe vient de WaveStack. Fredoka sert aux titres, étiquettes et nombres (chiffres tabulaires) ; Atkinson Hyperlegible à l'interface ; JetBrains Mono à tout ce qui vient de git, des outils ou des fichiers.

| Rôle | Usage dans WaveDevSecOps |
|---|---|
| `{typography.pane-title}` | Titre de vue, de scénario, de section du catalogue |
| `{typography.pane-subtitle}` | Sous-titre d'une ligne qui dit ce que la vue montre |
| `{typography.heading}` | Titre de PR, d'encart, d'environnement |
| `{typography.chat}` | Consigne de l'étape, lue en premier |
| `{typography.body}` | Explication, texte courant |
| `{typography.body-sm}` | Messages de l'application dans le terminal, raisons, journal de revue |
| `{typography.label}` | Étiquettes, badges, onglets, pastilles |
| `{typography.number}` / `{typography.number-lg}` | Étape n/N, compteurs ; score du bilan |
| `{typography.code}` | Terminal, SHA, branches, chemins, diff, éditeur, sorties d'outils, solution d'indice, commandes du quiz |

Règles reprises : aucun texte sous 12 px ; pas de taille « display » ; polices servies en local (WOFF2), jamais par un CDN (NFR-1). Le mode projection de WaveStack arrivera avec le mode formateur `[ASSUMPTION]`.

## Layout & Spacing

L'échelle vient de WaveStack (`{spacing.1}` à `{spacing.6}`, gouttière `{spacing.gutter}`, padding de vue `{spacing.pane-padding}`). Le fond `{colors.surface}` porte des pois `{colors.dot}` sur une grille `{spacing.dot-grid}`, uniquement derrière les vues.

**Disposition principale**, écran de référence 1920×1080 (proportions : EXPERIENCE.md > Information Architecture). Rendu : [mockups/espace-travail.html](mockups/espace-travail.html).
- En-tête `site-nav` de `{spacing.top-bar-height}`.
- Bandeau de la carte de la chaîne de `{spacing.chain-band-height}`, à partir de v0.2.
- À gauche, panneau Scénario de largeur fixe `{spacing.scenario-panel-width}` `[ASSUMPTION]`.
- À droite, trois rangées : Dépôt local | Distant + PR ; Code ; Terminal.
- Quand une vue est masquée, une rangée de puces de `{spacing.hit-target-min}` s'ajoute en tête de la colonne droite (rendu : [mockups/designation-mode-b.html](mockups/designation-mode-b.html)).

Chaque vue défile en interne ; son en-tête (`{spacing.pane-header-height}`) reste fixe.

**Pages annexes.** Le `site-nav` y est centré, large de `{spacing.home-max-width}` au plus. Le catalogue occupe `{spacing.home-max-width}` ; le diagnostic, le rapport et la fiche `{spacing.annex-max-width}`. Fond `{colors.surface}` sans pois.

**Traits et cibles.** Les traits porteurs font `{spacing.stroke-min}` au moins ; les chemins du graphe `{spacing.stroke-path}`. Une cible isolée fait `{spacing.hit-target-min}` au moins ; une cible contiguë (ligne de diff, nœud du graphe, segment d'étape) `{spacing.hit-target-dense}` au moins. Une ligne de diff fait `{spacing.diff-line-height}`, une rangée du graphe `{spacing.graph-row-height}` ; la zone de clic d'un commit couvre le disque, le SHA et le message.

**Numérotation.** Les vues gardent leur numéro de lecture (`pane-step`). Une station s'écrit toujours « Station n · Nom », par exemple « Station 4 · Livraison ». Dans les textes, on nomme les vues par leur nom.

## Elevation & Depth

Le relief de jouet vient de WaveStack : ombre pleine sans flou `0 {spacing.relief-offset} 0 {colors.relief}` sur les pièces posées (vues, panneau Scénario, cartes du catalogue). Le bouton primaire pose sur `{colors.primary-deep}` ; enfoncé, il descend à `{spacing.relief-offset-pressed}`. La carte de la chaîne dépliée, les menus et les popovers prennent `{spacing.relief-offset-overlay}`.

Les lignes du terminal, les nœuds du graphe, les lignes de diff, les checks, les encarts, les cartes indisponibles et la fiche imprimée n'ont pas de relief. Le terminal est encastré.

## Shapes

Échelle de WaveStack :
- `{rounded.sm}` : tag, HEAD, nœuds de la carte, champ SHA, `mode-badge` ;
- `{rounded.md}` : boutons, PR, checks, encarts, case de réponse, choix du quiz, terminal ;
- `{rounded.lg}` : vues, panneau, cartes de scénario ;
- `{rounded.full}` : pilules (pastilles, refs, sélecteur de parcours, badges de verdict).

Formes du graphe `[ASSUMPTION]` : un commit est un disque ; un commit perdu, un disque en tirets ; une branche locale, une pilule à bord simple avec icône poste ; une ref distante, une pilule à double bord avec icône serveur ; un tag, un rectangle à encoche ; HEAD, un rectangle plein encre. La forme dit la catégorie, la couleur dit le domaine.

## Components

**Repris de WaveStack sans changement** ([digest §2](imports/wavestack-digest.md)) : `site-nav`, `pane`, `pane-step`, `pane-chip`, `pane-resize-handle`, `pane-menu`, `state-pill`, `button-primary`, `button-secondary`, `button-danger`, `theme-picker`. `explain-popover` reprend `scenario-info` : déclencheur « i » italique dans un disque de 1,5 em cerclé `{colors.primary}`, cible de `{spacing.hit-target-dense}` au moins, plein au survol ou ouvert. `tool-output` reprend `produced-block`.

**Modifiés :** `link-state` (estompage sans opacité sur le texte), `focus-ring` (décalage, version sur encre), `reset-button` (bordure `{colors.muted}`), `diagnostic-row` (pastilles pleines). Tous les ajouts sont `[ASSUMPTION]`. La prose ne donne que ce que les jetons ne disent pas.

### Focus, liaison, sélection

Quatre états, quatre formes :
- **Focus** (`focus-ring`) : anneau plein en `{colors.primary}`, décalé ; sur fond encre (terminal, `ink-fill`), en `{colors.focus-on-ink}`. Le décalage le garde visible sur un bouton primaire.
- **Lié** (`link-state`) : fond doux de la discipline et anneau de sa couleur.
- **Sélectionné** : contour `{colors.ink}` et marque ●.
- **Désignable** (`designable`) : contour en tirets `{colors.primary}`.

**Règles de combinaison.**
- Quand un élément est lié, les autres estompent leurs décors (remplissages, traits) et passent leur texte en `{colors.ink-soft}`, sans opacité.
- Préséance : verdict > sélection > désignable > lié. Un élément choisi qui reste désignable montre le contour de sélection à la place du pointillé.
- Dans le terminal, une ligne liée prend le fond `{colors.terminal-lit-fill}` et l'anneau `{colors.terminal-lit-ring}` ; les autres lignes passent en `{colors.terminal-fg-soft}`.

### Panneau Scénario
- **`scenario-panel`** : de haut en bas, le titre, `mode-badge` avec son « i », `step-progress`, la consigne, la zone de question, `step-explanation`, `hint-tabs`, puis « Recommencer » en pied. À la fin, le bilan. Le parcours se choisit dans l'en-tête (`path-menu`).
- **`path-menu`** : dans `site-nav`, à droite, avant « Volets ▾ » : « Parcours LLM ▾ », sur tous les écrans.
- **`step-progress`** : « Étape 3 sur 7 », puis des segments cliquables portant une barre en pilule (fait `{colors.ink}`, courant `{colors.primary}`, à venir en tirets `{colors.muted}`).
- **`step-explanation`** : encart de l'explication, filet gauche `{colors.primary}`, titre en `{typography.heading}`. La variante « Ce qui l'aurait bloqué » a un filet `{colors.discipline-harness}` et une ligne par barrière : nom, « Station n · Nom », une phrase, et l'étiquette en tirets « Arrive en v0.2 » tant que la station n'est pas livrée.
- **`quiz-choice`** : une carte par commande, case radio et commande en code ; cochée, elle prend la bordure `{colors.primary}` et le fond `{colors.primary-soft}`. Sous la liste, « Exécuter ma réponse » (`button-primary`).
- **`designate-button`** : « Désigner dans les vues » (`button-secondary`) ; armé, il prend le fond `{colors.primary}` et le texte « Désignation active · Échap pour quitter ».
- **`designate-list`** : le lien « Choisir dans la liste ▾ » (▴ ouvert) ouvre :
  - un champ de filtre « Filtrer par nom, SHA ou chemin » ;
  - une liste qui défile en interne, groupée par vue (titre en `{typography.label}`) ;
  - une ligne par élément, avec icône de type (commit = anneau, fichier, ligne, branche = poste) et SHA court à droite ;
  - l'élément choisi, sur fond `{colors.primary-soft}`, avec la mention « choisi ».
- **`answer-slot`** et **`sha-field`** :
  - libellé « Votre réponse » ; case vide en tirets `{colors.muted}`, avec un texte d'aide ;
  - case pleine : bande `{colors.primary-soft}` avec icône, libellé, SHA court et bouton ✕ rond ;
  - après validation : « Votre réponse · validée », sans ✕, avec son `verdict-mark` ;
  - champ « Ou saisir un SHA », aide « 7 caractères au moins, résolus dans le bac à sable. » ; invalide, bordure `{colors.danger}` et message ;
  - bouton pleine largeur « Valider ma réponse », avec sous lui le texte relié « 1 seul essai ».
- **`hint-tabs`** : Piste | Commande partielle | Solution. L'onglet actif est souligné en `{colors.primary}`. L'onglet verrouillé a un fond neutre, un texte `{colors.ink-soft}`, un cadenas et sa condition visible.
- **`notice-card`** : encart à filet gauche. Le filet est `{colors.primary}` pour une information (État inattendu), `{colors.warning}` pour un avertissement, `{colors.danger}` pour une erreur (rétablissement échoué, bac à sable indisponible). Il porte un titre, une icône, un texte et ses actions.
- **`quiz-banner`** : bandeau au-dessus des vues, fond `{colors.warning-soft}`, filet `{colors.warning}`, ⚠, « État modifié par le quiz — » suivi de la commande, et le bouton « J'ai compris, rétablir l'état ».
- **`score-summary`** : « 3 sur 4 du premier coup » en `{typography.number-lg}`, « 1 indice » en `{typography.number}`.

### Terminal
- **`terminal`** : fond `{colors.terminal-bg}`, texte `{colors.terminal-fg}`, `{typography.code}`.
- **`terminal-prompt`** : `$` en `{colors.terminal-accent}`, avec le dossier et la branche courante.
- **`terminal-stderr`** : texte `{colors.terminal-fg-soft}` et filet `{colors.terminal-rule}`, jamais rouge, car git écrit aussi sa progression sur stderr.
- **`terminal-exit-error`** : « ✗ code de sortie 128 », icône `{colors.terminal-danger}`.
- **`terminal-app-message`** : en `{typography.body-sm}`, précédé de « › », filet `{colors.terminal-accent}`.
- **`terminal-refused`** : comme le précédent, avec filet et ✗ en `{colors.terminal-danger}` et le mot « Refusée » en tête.

### Dépôt local
- **`graph-commit`** : disque de `{spacing.graph-node-size}` cerclé `{colors.discipline-prompt}`, SHA court et message à droite.
- **`graph-edge`** : trait `{colors.ink-soft}` ; vers un commit perdu, tirets `{colors.muted}`.
- **`graph-head`** : étiquette « HEAD » accolée à la branche courante ; détachée, « HEAD détachée » sur le commit.
- **`graph-branch`**, **`graph-remote-ref`**, **`graph-tag`** : formes de Shapes, noms en code, préfixe « origin/ » sur les refs distantes.
- **`graph-commit-lost`** : disque en tirets et libellé « perdu · visible par reflog ».
- **`graph-commit-colleague`** et **`graph-commit-agent`** : badges « Collègue » (contour encre) et « Agent » (`{colors.primary-soft}`), repris de `trigger-badge-user` et `trigger-badge-model`.
- **`commit-list`** : alternative texte du graphe, en tableau (SHA, message, auteur, parents, refs, état), dans l'ordre de `git log --all --graph`.
- **`new-mark`** : étiquette « Nouveau » sur tout élément créé ou déplacé par la dernière commande ; variante « Rétabli » après un quiz.
- **`staging-index`** : groupes « Indexé », « Modifié, non indexé », « Non suivi », avec la lettre d'état git en code. Indexé : fond `{colors.accent-soft}` ; modifié : bordure `{colors.muted}` ; non suivi : bordure en tirets.

### Code
- **`code-editor`** : arbre de fichiers et éditeur. Un fichier non enregistré porte un point plein et « non enregistré ». Bouton « Ouvrir dans mon éditeur ».
- **`external-change-notice`** : ligne `{colors.primary-soft}` en haut de l'éditeur, « Modifié hors de l'application » ; en cas de conflit, « Garder ma version » et « Recharger ».
- **`diff-file-header`** : ligne au-dessus du diff d'un fichier, avec le chemin en code puis « nouveau fichier · +3 −0 » ou « plié » en `{colors.ink-soft}`. Elle est désignable comme fichier.
- **`diff-view`** : une ligne ajoutée a le fond `{colors.accent-soft}` et « + » ; une ligne supprimée, le fond `{colors.danger-soft}` et « − ». Les numéros sont en `{colors.ink-soft}`, le texte en `{colors.ink}`.
- **`pipeline-tabs`** : GitHub Actions | Jenkins | GitLab CI, étiquette « Lecture seule » ; les lignes de la tâche ont le fond `{colors.primary-soft}` et un filet `{colors.primary}`.
- **`sbom-view`** : tableau du SBOM (composant, version, licence, vulnérabilités), étiquette « Lecture seule » ; une ligne vulnérable a le fond `{colors.danger-soft}`, ✗ et l'identifiant de la vulnérabilité.

### Distant + PR
- **`pr-card`** : titre, « feature → main » en code, checks, `review-log`, bouton Merger. Ordre : checks en échec, `merge-blocked`, checks réussis et en cours en ligne, `review-log`.
- **`pr-check`** : ligne arrondie `{rounded.md}` avec glyphe, outil en code, état en mots et durée à droite.
  - Réussi : ✓, fond `{colors.accent-soft}`.
  - Échec : ✗, fond `{colors.danger-soft}`. Une ligne de détail suit : fichier:ligne en lien, règle, « Voir la sortie », « Voir dans le pipeline ».
  - En cours : point animé cerclé `{colors.ink}` pour rester visible sur fond clair, fond `{colors.primary-soft}`.
  - Erreur de l'outil : ⚠, fond `{colors.warning-soft}`.
  - Obligatoire : étiquette encre.
- **`review-log`** : journal de revue. Un filet vertical `{colors.ink-soft}`, une entrée par événement (auteur, action, heure), un compteur à droite « Approbations : 1 sur 2 » suivi de « 2 approbations requises ». Approuvé : ✓ ; modifications demandées : ✗.
- **`merge-blocked`** : bouton inactif sur fond neutre, texte `{colors.ink-soft}`, raisons listées dessous.
- **`tool-output`** : bloc de sortie d'outil, étiquette encre au nom de l'outil.
- **`network-run-button`** : « Exécuter le code (réseau possible) », fond `{colors.discipline-network-soft}`, bordure et icône réseau en `{colors.ink}`.

### Livraison (Station 4 · Livraison, v0.3)
L'onglet « Livraison » s'ajoute à côté de « PR » dans la vue Distant + PR `[ASSUMPTION]`.
- **`build-artifact`** : artefact construit, nom et numéro du tag en code, commit source.
- **`env-card`** : une carte par environnement (« Staging », « Prod simulée ») avec la version servie en code, un historique court et, sur la prod simulée, le bouton « Rollback » (`button-danger`).
- **`promotion-gate`** : « Promouvoir vers la prod simulée ». Sans approbation, il prend la présentation de `merge-blocked` avec la raison ; approuvé, le fond `{colors.accent-soft}` et ✓.
- Un tag refusé (non SemVer) s'affiche par `terminal-refused` (EXPERIENCE.md > Livraison).

### Chaîne et vocabulaire (v0.2+)
- **`chain-band`** : quatre stations, de « Station 1 · Poste local » à « Station 4 · Livraison ». La station courante a le fond `{colors.discipline-harness-soft}`, un trait bas et la pilule « Vous êtes ici » (bordure `{colors.discipline-harness}`). Le libellé « CI | CD », encadré de deux traits `{colors.hosting-boundary}`, marque la frontière entre la Station 3 · Sécurité et qualité et la Station 4 · Livraison. Le bouton « Carte ▾ » est à droite.
- **`chain-map`** : carte dépliée sous le bandeau, une zone par station (style `arch-zone` de WaveStack), nœuds d'outil et de barrière en `{rounded.sm}`. Un outil indisponible est en tirets ; un jalon non livré porte « Bientôt » en tirets.
- **`glossary-term`** : terme souligné en pointillés `{colors.primary}`. Un terme « seulement nommé » (DAST) porte l'étiquette en tirets « Nommé seulement ».

### Désignation et correction
Rendu : [mockups/designation-mode-b.html](mockups/designation-mode-b.html), (a) mode armé avec choix en attente, (b) réponse fausse corrigée.
- **`designable`** : voir Focus, liaison, sélection.
- **`verdict-mark`** : badges en pilule de `{spacing.badge-height}`, posés à droite de la rangée du graphe, de l'en-tête de fichier ou de la ligne de diff.
  - Attendu (élément principal) : contour `{colors.ink}` et badge « ✓ Attendu ».
  - Choix faux : tirets `{colors.danger}` et badge « ✗ Votre choix ».
  - Choix juste : badge « ✓ Votre choix ».
  - Équivalent accepté : badge en tirets encre « ≡ Accepté aussi ».
  - Dans le panneau, la correction est un `step-explanation` qui liste l'attendu et les équivalents (badge, élément, lien « voir dans les vues »).

### Catalogue, diagnostic, exports
Rendu : [mockups/catalogue.html](mockups/catalogue.html), [mockups/diagnostic.html](mockups/diagnostic.html).
- **`path-picker`** : dans le catalogue, groupe radio de deux pilules, « Parcours LLM » | « Parcours sans IA » ; le choix actif a le fond `{colors.primary}` et le texte `{colors.on-primary}`. C'est le même choix que `path-menu`.
- **`catalogue-section`** : « Socle git », « Stations », « Savoir en parler », chacune avec titre, sous-titre d'une ligne et grille de trois colonnes. Dans « Stations », chaque station a un sous-titre « Station n · Nom » à filet gauche `{colors.discipline-harness}`.
- **`scenario-card`** : modèle `brick-card`, avec relief.
  - Titre précédé du numéro d'ordre dans un disque encre de `{spacing.order-disc-size}` (comme `pane-step`).
  - Colonnes « Mode A » et « Mode B » séparées d'un filet `{colors.line}` ; une seule colonne sans mode B. Une carte de station a une phrase de description et une seule ligne d'état.
  - Pastilles d'état : « ✓ Terminé » sur `{colors.accent-soft}` ; « En cours » sur `{colors.primary-soft}`, bordure `{colors.primary}`, avec un point ; « À faire » sur `{colors.surface}`.
  - Sous la pastille : « 3 sur 4 du premier coup · 1 indice », ou « Étape 3 sur 6 » et le bouton « Reprendre » (`button-primary`).
  - Indisponible : à plat, fond neutre, tirets `{colors.muted}`, texte `{colors.ink-soft}`, pastille « ⊘ Indisponible », raison en `{colors.ink}` « Nécessite gitleaks · Voir le diagnostic » (lien gras `{colors.primary-deep}`).
- **Pied du catalogue** : filet `{colors.line}`, « Exporter mon rapport » (`button-secondary`) et la phrase « Rien n'est envoyé : vous choisissez à qui transmettre le fichier. ».
- **`diagnostic-badge`** : pastille `{colors.danger}` / `{colors.on-vivid}` sur « Diagnostic », absente quand tout est OK.
- **`diagnostic-row`** (page Diagnostic) :
  - en-tête de page : titre, sous-titre, « Relancer le diagnostic » (`button-secondary`) ; puis une ligne de synthèse à filet gauche `{colors.primary}` ;
  - deux `pane`, « Outils » et « Proxy » ; dans le tableau, une ligne de groupe par jalon, soulignée `{colors.ink-soft}` ;
  - ligne d'outil au fond de son état, extrémités `{rounded.md}` ;
  - pastilles pleines, texte `{colors.on-vivid}` : « ✓ OK » `{colors.accent}`, « ⚠ Trop ancien » ou « ⚠ À compléter » `{colors.warning}`, « ✗ Absent » `{colors.danger}` ;
  - « Que faire ? » dépliable ; commandes en code bordé `{colors.muted}` ;
  - note discrète en `{typography.label}` : « Versions minimales illustratives, fixées en architecture. » ;
  - pied : « Continuer vers le catalogue » et une phrase sur les scénarios grisés.
- **`report-preview`** : carte d'aperçu du rapport : ce qu'il contient, la phrase de confidentialité, deux boutons d'export.
- **`barrier-sheet`** : tableau de la fiche ; « explicite » en étiquette pleine encre, « interprétation » en tirets. À l'impression : fond blanc, sans pois ni relief.

Chaque maquette a deux cases « Forcer clair » et « Forcer sombre » ; sans case cochée, elle suit le thème du système.

## Do's and Don'ts

Repris de WaveStack ([digest §4](imports/wavestack-digest.md)), plus :

**Do**
- Garder une couleur pour un sens (table Colors) : l'apprenant lit le domaine d'un coup d'œil.
- Joindre une icône et un libellé à tout état : la couleur seule ne passe pas en niveaux de gris.
- Écrire les sorties de git et des outils en mono, et les messages de l'application en Atkinson avec « › » : on ne les confond pas (NFR-2).
- Distinguer les catégories du graphe par la forme et l'icône : la couleur porte déjà le domaine.
- Border champs, cases et boutons en `{colors.muted}` 2 px : `{colors.line}` n'atteint pas 3:1.
- Décaler l'anneau de focus et le passer en `{colors.focus-on-ink}` sur fond encre : il reste visible partout.
- Griser par le fond neutre et le texte `{colors.ink-soft}` : le texte reste lisible.
- Écrire « Station n · Nom » : un chiffre nu se confond avec le numéro d'une vue.

**Don't**
- Appliquer une opacité à du texte : il tombe sous 4,5:1.
- Écrire du texte en `{colors.muted}` ou `{colors.discipline-neutral}` : 3,4:1 seulement en clair.
- Colorer stderr en rouge : git y écrit aussi sa progression.
- Réécrire une sortie de git : la vraie sortie est la matière pédagogique (NFR-2).
- Écrire en `{colors.accent}` ou tracer avec lui sur fond clair : 1,5:1.
- S'appuyer sur un point vert, un filet jaune ou des tirets `line` comme seul signal : ils sont décoratifs (`aria-hidden`).
- Colorer en rouge un commit d'agent : l'agent n'est pas en faute par défaut.
- Utiliser les jetons `terminal-*` hors du terminal : ils sont calculés pour son fond.
- Changer selon le thème les jetons `terminal-*` autres que le fond et le texte principal : leurs contrastes ne valent que pour ces valeurs.
- Dessiner un curseur sur mesure : le mode désignation utilise un curseur système.
- Mettre du relief sur une ligne du terminal ou du diff, un encart ou une carte indisponible : le relief signale une pièce posée et active.
- Utiliser une ombre floue, un dégradé ou `filter: invert` : hors de l'identité WaveStack.
- Charger une ressource depuis un CDN : l'application est hors ligne (NFR-1).
- Mettre des pois derrière du texte : ils gênent la lecture.
