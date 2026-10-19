# Run autonome — plan et état

Fichier d'état de l'orchestrateur, à relire en premier après chaque `/clear`.
Source des statuts : `sprint-status.yaml` (même dossier). Source des stories : `_bmad-output/planning-artifacts/epics.md`.
Établi le 2026-10-18 par `bmad-sprint-planning`. Gate de préparation : **PASS**.

## Périmètre

| Sprint | Contenu | Rôle dans le run |
|---|---|---|
| Sprint 1 (v0.1) | Epics 1 à 6, 44 stories | file principale |
| Sprint 2 (v0.2) | Epics 7 à 9, 17 stories | file de relais : à lancer dès que le Sprint 1 est fini **ou** bloqué sur une étape humaine |
| Hors run | Epics 10 à 12 | 10.2 à 10.5 en `backlog` (en attente de l'UX et du spine station 4) ; 12.5, 12.6 et 12.7 humaines ; reste après v0.2 |

## Règles fixes

1. **Type de story** (ligne `**Type :**` d'epics.md)
   - `dev` : `agent-cost-kit:dev-story` → `agent-cost-kit:second-avis` → `agent-cost-kit:reviewer` (avec la liste du second avis) → intégration.
   - `mixte` : l'agent fait la partie code et publication, puis la story reste en `review` avec la mention « attente humaine » dans le journal. Notifier Anaël et continuer sur ce qui n'en dépend pas.
   - `humaine` : jamais confiée à un agent. Pas de `dev-story`, pas de changement de statut.
2. **Ressource à activer par Anaël** (Ollama, GPU, compte externe, poste réel) : ne pas improviser. Notifier, noter dans le journal, passer à la story suivante éligible. Les tests du parcours LLM (2.11, 6.6, 8.5, 8.6) remplacent l'appel réseau ; une story qui exigerait un vrai modèle s'arrête là.
3. **Modèle** : `dev-story` sur Sonnet, sauf les stories pivots marquées ★, sur Opus. Reviewer sur Opus. Deux échecs Sonnet sur une story : la reprendre sur Opus. Un échec Opus : story `blocked` dans le journal, notification, on continue.
4. **Pas d'imbrication** : seul l'orchestrateur lance des agents. Tous les appels sont bloquants et attendus. Un agent lancé en arrière-plan sans être attendu fait reprendre la story.
5. **Tests** : tests ciblés pendant le dev, suite complète une fois avant chaque fusion dans `main`, CI verte sur les trois OS avant de passer la story en `done`.
6. **Sorties externes** : push sur `main` et CI autorisés pendant le run. Tag et release GitHub seulement dans les stories de release (6.7, 9.5), suite complète verte sur les trois OS.

## Parallélisme à risque minimal

- **Au plus 3 stories en développement à la fois**, chacune dans son worktree (`dev-story` travaille en worktree et ne fusionne pas).
- **Une vague = des stories qui ne touchent ni le même module, ni le même fichier pivot.** Fichiers pivots : catalogue des `kind` et enveloppes (`contracts/`, `events/`), registre des ops de setup (`content`, AD-7), registre des volets du front (`web/static`), liste blanche des commandes (AD-4), `tools.toml`, `content/pipeline.yaml`, `content/explanations.yaml`, `config.py` (`Settings`). Un ajout d'une ligne dans un registre est toléré ; une refonte ne l'est pas.
- **La dépendance commande** : une story ne part qu'une fois toutes ses dépendances en `done` (colonne « Après »).
- **Intégration en série**, dans l'ordre de la vague : rebase de la branche sur `main`, tests ciblés, suite complète, fusion, push, CI. Puis seulement la branche suivante. Conflit trivial (ajout dans un registre) : l'orchestrateur le résout. Conflit de fond : `dev-story` sur Opus refait le rebase, puis nouveau `second-avis`.
- **Chevauchement** : la revue d'une story peut tourner pendant que les autres de sa vague se développent. La vague suivante peut démarrer story par story, dès que les dépendances de chacune sont en `done`. Il n'y a pas besoin d'attendre la fin de la vague.
- Une story en échec ne bloque que ses dépendantes. Les autres continuent.

## Sprint 1 — v0.1 (Epics 1 à 6)

Ordre conseillé par vagues. ★ = story pivot, `dev-story` sur Opus.

| Vague | Stories en parallèle | Après |
|---|---|---|
| V0 | 1.1 ★ | — |
| V1 | 1.2 · 1.4 | 1.1 |
| V2 | 1.3 · 2.1 ★ · 1.6 | 1.3 ← 1.2 ; 2.1 ← 1.4 (`procs`) ; 1.6 ← 1.4 (`tools.toml`) |
| V3 | 1.5 · 2.2 ★ · 1.7 | 1.5 ← 1.3, 1.4 ; 2.2 ← 1.2, 2.1 ; 1.7 ← 1.6 |
| V4 | 2.3 · 2.6 ★ · 2.11 | 2.3 ← 1.3, 2.2 ; 2.6 ← 2.1, 2.2 ; 2.11 ← 2.1 |
| V5 | 2.4 · 2.7 · 3.1 ★ | 2.4 ← 2.2, 2.3 ; 2.7 ← 2.3, 2.6 ; 3.1 ← 2.1, 2.2 |
| V6 | 2.5 · 3.2 · 4.1 | 2.5 ← 2.4 ; 3.2 ← 3.1, 2.6 ; 4.1 ← 2.6 |
| V7 | 2.8 · 3.3 · 4.2 | 2.8 ← 2.5, 2.3 ; 3.3 ← 3.2, 2.3 ; 4.2 ← 1.2, 4.1 |
| V8 | 2.9 · 3.4 · 4.3 ★ | 2.9 ← 2.8 ; 3.4 ← 3.2 ; 4.3 ← 3.1, 2.2 |
| V9 | 2.10 · 3.5 · 4.4 | 2.10 ← 2.7, 2.8, 3.3 ; 3.5 ← 3.1 ; 4.4 ← 4.2, 4.3 |
| V10 | 4.5 · 5.1 | 4.5 ← 4.3, 2.4 ; 5.1 ← 3.4 (registre d'ops) |
| V11 | 4.6 · 5.2 | 4.6 ← 4.1, 4.2 ; 5.2 ← 4.1, 4.2, 2.6 |
| V12 | 4.7 · 5.3 | 4.7 ← 4.2 ; 5.3 ← 5.2, 2.7 |
| V13 | 5.4 · 6.1 | 5.4 ← 5.2 ; 6.1 ← 2.3, 1.5, 4.2 |
| V14 | 5.5 · 6.4 · 6.6 | 5.5 ← 5.3 ; 6.4 ← 6.1, 4.3 ; 6.6 ← 2.11, 2.2 |
| V15 | 5.6 · 6.2 · 6.5 | 5.6 ← 5.1, 5.5 ; 6.2 ← 6.1, 4.5, 4.6, 3.4 ; 6.5 ← 4.7 |
| V16 | 5.7 · 6.3 | 5.7 ← 5.6, 3.5 ; 6.3 ← 6.2 |
| V17 | 5.8 | 5.7 |
| V18 | 6.7 (mixte) | toutes les stories `dev` des Epics 1 à 6 |

Ligne de coupe v0.1 (epics.md) : en cas de retard ou d'échec, on coupe d'abord 6.6, puis 5.8, puis 6.4. Une story coupée reste en `backlog` et passe au jalon suivant. Couper demande l'accord d'Anaël : la proposer par notification, sans l'appliquer seul.

**6.7** : l'agent prépare la release v0.1.0 (version, notes, README), puis la publie : tag annoté et release GitHub. La story reste en `review` jusqu'au test de SM-1 à SM-4 par Anaël et deux collègues. Notifier Anaël, puis enchaîner sur le Sprint 2.

## Sprint 2 — v0.2 (Epics 7 à 9), file de relais

`content/pipeline.yaml` est le pivot de l'Epic 8 : les stories qui y ajoutent un job (8.1, 8.3, 8.4, 8.6) passent en série et se combinent en parallèle avec l'Epic 9.

| Vague | Stories en parallèle | Après |
|---|---|---|
| W1 | 7.1 ★ · 8.2 · 9.1 | 7.1 ← 1.4, 1.6 ; 8.2 ← 1.2 ; 9.1 ← 2.3 |
| W2 | 7.2 · 7.4 ★ · 9.4 | 7.2 ← 7.1 ; 7.4 ← 7.1, 3.1 ; 9.4 ← 2.10 |
| W3 | 7.3 · 7.5 · 9.2 | 7.3 ← 7.1, 3.5 ; 7.5 ← 7.4 ; 9.2 ← 9.1 |
| W4 | 7.6 · 8.1 · 9.3 | 7.6 ← 7.4 ; 8.1 ← 7.4 ; 9.3 ← 6.1 |
| W5 | 8.3 | 8.1, 8.2 |
| W6 | 8.4 · 8.5 | 8.4 ← 8.3 ; 8.5 ← 8.3 |
| W7 | 8.6 | 8.4 |
| W8 | 9.5 (mixte) | Epics 7 à 9 en `done` |

**9.5** : la mesure des 45 s et SM-9 reviennent à Anaël. L'agent prépare tout et publie la release v0.2.0 seulement si la mesure a été faite. Sinon, il s'arrête et notifie Anaël.

Après le Sprint 2, sans retour d'Anaël : arrêt du run et notification. Les Epics 10 et 11 demandent d'abord l'UX de la station 4.

## Journal

Une ligne par événement : date-heure · story · étape (dev, second-avis, review, fusion, CI, attente humaine, blocked) · résultat · commit.

- 2026-10-18 · — · sprint planning · `sprint-status.yaml` généré (80 stories en `backlog`), plan écrit · —
- 2026-10-18 · — · commit · artefacts BMAD et skills commités sur main · 9e60489
- 2026-10-18 · 1.1 · dev · lancé (dev-story Opus, worktree) · —
- 2026-10-18 · 1.1 · dev · fini, 61 tests verts sous Windows · 08f41f5
- 2026-10-18 · 1.1 · second-avis · 3 medium, 5 low · —
- 2026-10-18 · 1.1 · review · 4 medium corrigés (dont DNS du hook d'audit), point 8 reporté à 1.4 (`--group chain` en CI) · 413664e
- 2026-10-18 · 1.1 · fusion · ff sur main, suite complète 80 passed · 413664e
- 2026-10-18 · 1.1 · CI · verte sur les trois OS, story done · 0429d97
- 2026-10-18 · 1.2, 1.4 · dev · vague V1 lancée (dev-story Sonnet, worktrees) · —
- 2026-10-18 · 1.2 · dev · fini, 94 tests, CI verte sur la branche · c19fdc1
- 2026-10-18 · 1.4 · dev · fini, 126 tests (gitleaks absent du poste, signalé missing) · 6e81819
- 2026-10-18 · 1.2 · second-avis · 2 medium, 5 low · —
- 2026-10-18 · 1.2 · review · 6 corrigés (verrou atomique, OSError, second lancement sans écriture…), vivacité par pid reportée · 6d1c425
- 2026-10-18 · 1.2 · fusion · ff sur main, suite complète 100 passed · 6d1c425
- 2026-10-18 · 1.4 · second-avis · 1 high (terminate_tree n'arrête pas l'arbre si le chef est sorti), 2 medium, 5 low · —
- 2026-10-18 · 1.2 · CI · verte sur les trois OS, story done · 522f9a3
- 2026-10-18 · 1.3 · dev · lancé (dev-story Sonnet, worktree) · —
- 2026-10-18 · 1.4 · review · rebase sur main (config.py unifié sur resolved_data_dir), high corrigé (arrêt d'arbre borné, test enfant+petit-enfant), Job Object Windows reporté à procs.spawn · 78c397a
- 2026-10-18 · 1.4 · fusion · ff sur main, suite complète 150 passed, CI branche verte sur les trois OS · 78c397a
- 2026-10-18 · 1.3 · dev · fini, 120 tests (exclusion des licences OFL du contrôle AD-13 (2)) · 3dcd853
- 2026-10-18 · 2.1, 1.6 · dev · lancés (2.1 dev-story Opus ★, 1.6 Sonnet), 1.3 en revue · —
- 2026-10-18 · 1.3 · second-avis · 2 medium (fetch sans délai, désactivation des actions sans effet réel), 3 low · —
- 2026-10-18 · 1.3 · review · rebase propre, 3 medium corrigés (délai du point de vie, test JS sous Node, contraste du lien d'évitement en sombre + test WCAG) · b9dcac0
- 2026-10-18 · 1.3 · fusion · ff sur main, suite complète 175 passed, CI branche verte sur les trois OS, story done · b9dcac0
- 2026-10-18 · 1.5 · dev · lancé (dev-story Sonnet, worktree) · —
- 2026-10-18 · 1.6 · dev · fini, 165 tests dont 15 en simulation PowerShell 5.1 ; parcours réel (poste Windows non admin, proxy, 10 min) à vérifier par Anaël · 543ef4c
- 2026-10-18 · 1.6 · second-avis · 5 medium (barre de progression, proxy de l'amorçage et d'uv, voie iex cassée en simulation, GPO), 2 low · —
- 2026-10-18 · 1.5 · dev · fini, 194 tests (sans SSE, redirection / → /diagnostic au premier lancement) · 98efad4
- 2026-10-18 · 1.6 · review · rebase propre, 7 constats corrigés (proxy amorçage et uv, voie iex testée, GPO, dossier app protégé) · b5eb587
- 2026-10-18 · 1.6 · CI · rouge sous Windows seulement (sortie PowerShell en page OEM 437 dans 3 tests) ; renvoyé au reviewer · b5eb587
- 2026-10-18 · 1.5 · second-avis · 10 low, aucun high/medium · —
- 2026-10-18 · 2.1 · dev · fini, 192 tests, CI branche verte sur les trois OS (empreintes identiques) · a3274bb
- 2026-10-18 · 2.1 · second-avis · 2 medium prouvés (ignore global XDG non isolé → empreinte, confinement .git contournable sous Windows), 7 low · —
- 2026-10-18 · 1.6 · CI · tests PowerShell forcés en UTF-8, CI branche verte sur les trois OS · 95c0cf9
- 2026-10-18 · 1.6 · fusion · ff sur main, suite complète 195 passed, story done ; vérification sur vrai poste Windows non admin (8 points, section Revue de la spec) en attente d'Anaël · 95c0cf9
- 2026-10-18 · 1.5 · review · 5 low corrigés, aucun medium ; diagnostic_seen à ajouter à AD-5 · c72d1c4
- 2026-10-18 · 1.7 · dev · lancé (dev-story Sonnet, worktree) · —
- 2026-10-18 · 1.5 · fusion · rebase sur 5a51a2a par l'orchestrateur, suite complète 219 passed, CI branche verte sur les trois OS, ff sur main, story done · 0ec4010
- 2026-10-18 · 2.1 · review · 2 rebases (conflit trivial contracts), 3 medium corrigés (ignore/attributs globaux isolés, confinement .git normalisé, étape CI autocrlf qui prouvait à vide), 4 low corrigés ; liens de l'apprenant hors espace reportés à 2.2 · 836eb0d
- 2026-10-18 · 2.1 · fusion · ff sur main, suite complète 272 passed / 2 skipped, CI branche verte sur les trois OS, story done · 836eb0d
- 2026-10-18 · 2.2, 2.11 · dev · lancés (2.2 dev-story Opus ★, 2.11 Sonnet) ; 1.7 en dev · —
- 2026-10-18 · 1.7 · dev · fini, CI verte (installation réelle sur runners ubuntu et macos, shellcheck) · 7f4c23f
- 2026-10-18 · 2.11 · dev · fini, 289 tests, CI verte sur les trois OS, sans réseau ni modèle ; httpx 0.28.1 à ajouter à la table Stack · 23ea199
- 2026-10-18 · 1.7 · second-avis · aucun high, 1 medium/low (voie zip sans provisionnement git, idem install.ps1), 5 low · —
- 2026-10-18 · 2.11 · second-avis · 4 medium (allowed_endpoints contrôlé contre lui-même, AD-13 non imposé au gabarit, chemin httpx jamais testé, tests hors venv verrouillé), 4 low · —
- 2026-10-18 · 2.11 · review · 3 medium corrigés (test loopback par nom d'hôte, tests du gabarit en uv --offline --frozen sur cache préchargé en CI, chemin httpx exécuté), AD-13 des tests du gabarit via toolrun reporté à la station 1 · c2d4573
- 2026-10-18 · 2.11 · fusion · ff sur main, suite complète verte, CI branche verte sur les trois OS, story done · c2d4573
- 2026-10-18 · — · décision pour Anaël · ajouter httpx==0.28.1 à la table Stack du spine et au test de cohérence AD-16 ; diagnostic_seen à ajouter à AD-5 · —
- 2026-10-18 · 1.7 · review · rebase (conflit ci.yml trivial), medium XDG_DATA_HOME sous macOS corrigé, avertissement voie zip sans git (sh et ps1), échange sûr de l'app, délais réseau · ba13fd2
- 2026-10-18 · 2.2 · dev · fini, 316 tests, CI verte sur les trois OS · 9ba966f
- 2026-10-18 · 2.2 · second-avis · 1 high prouvé (close() laisse l'opération tourner → deux écrivains à la réouverture), 2 medium, 5 low · —
- 2026-10-18 · 1.7 · fusion · rebase sur 221000e par l'orchestrateur, suite complète 289 passed / 33 skipped, CI branche verte (5 jobs dont install.sh réel), ff sur main, story done ; Epic 1 done ; vérification poste réel macOS/Linux (9 points) en attente d'Anaël · 8df335e
- 2026-10-18 · — · décision Anaël · relais Sprint 2 autorisé pendant la revue de 2.2 (stories éligibles) · —
- 2026-10-18 · 7.1, 8.2 · dev · lancés (7.1 dev-story Opus ★, 8.2 Sonnet) ; 2.2 en revue · —
- 2026-10-18 · 2.2 · review · 2 rebases sans conflit, high corrigé (réouverture refusée en 409 tant que l'ancien fil tourne, veille LRU au repos d'abord), 2 medium et 5 low corrigés ; interruption de l'opération à la veille reportée à 2.4 · e5eb028
- 2026-10-18 · 2.2 · fusion · ff sur main, suite complète verte, CI branche verte sur les trois OS, story done · e5eb028
- 2026-10-18 · 2.3 · dev · lancé (dev-story Sonnet) ; 2.6 ★ et 3.1 ★ éligibles, en attente d'un créneau (7.1 et 8.2 en dev) · —
- 2026-10-18 · 8.2 · dev · fini, 38 tests dont pip-audit réel sur le serveur local, CI verte · f076b19
- 2026-10-18 · 2.6 · dev · lancé (dev-story Opus ★) · —
- 2026-10-18 · 8.2 · second-avis · 1 medium (corps lu en entier avant la limite de 64 Ko sur route publique), 4 low dont faux positif version locale · —
- 2026-10-18 · 2.3 · dev · fini, 354 tests, CI verte ; rendu réel à voir dans un navigateur · 35841d3
- 2026-10-18 · 3.1 · dev · lancé (dev-story Opus ★) · —
- 2026-10-18 · 2.3 · second-avis · 2 medium (gabarits listés au catalogue, critères DOM testés par grep), 4 low ; décision orchestrateur : scénarios gabarit-* internes, masqués du catalogue · —
- 2026-10-18 · 8.2 · review · rebase (conflit app.py trivial), medium corrigé (corps borné au flux, Origin étrangère refusée), 4 low corrigés (échec fermé, partie locale, extrait atomique) · 1db409a
- 2026-10-18 · 8.2 · fusion · ff sur main, suite complète 386 passed / 34 skipped, CI branche verte, story done · 1db409a
- 2026-10-18 · 7.1 · dev · fini, CI verte sur 6 jobs (install.ps1 réel ajouté), garde réseau .pth dans le venv du gabarit, branchement toolrun reporté à 7.2 · c0d474b
- 2026-10-18 · 7.1 · second-avis · 2 medium prouvés (garde réseau : nom 127.* non résolu autorisé, sendto UDP non audité), 7 low · —
- 2026-10-18 · 2.6 · dev · fini, 389 tests, CI verte ; placement par génération, indépendant des refs · 9dd49eb
- 2026-10-18 · 3.1 · dev · fini, 355 tests, CI verte, 4 empreintes de référence régénérées (github.json inclus) · 61f0532
- 2026-10-18 · 3.1 · second-avis · 1 medium (refresh seulement au setup), 8 low ; décision pour Anaël : une approbation survit-elle à un nouveau push ? (défaut actuel : oui, comme GitHub sans dismiss_stale_reviews) · —
- 2026-10-18 · 2.3 · review · rebase sur de2df2c, 2 medium corrigés (scénarios internes catalogue: false, tests DOM réels sur doublure minidom), 4 low · de83bb3
- 2026-10-18 · 2.6 · second-avis · 1 medium prouvé (placement par date : un commit antidaté déplace les existants), 6 low · —
- 2026-10-18 · 2.3 · fusion · ff sur main, suite complète 409 passed / 36 skipped, CI branche verte, story done ; rendu navigateur à vérifier par Anaël · de83bb3
- 2026-10-18 · 2.4, 9.1 · dev · lancés (Sonnet) · —
- 2026-10-18 19:58 · 9.1 · dev · fini, 412 tests, CI verte · 5bf1f3d
- 2026-10-18 19:58 · — · convention · à partir d'ici chaque ligne du journal porte l'heure (HH:MM) pour l'estimation de fin · —
- 2026-10-18 19:56 · 7.1 · review · 2 rebases sans conflit, 2 medium corrigés (garde réseau : IP loopback littérale seulement, sendto/DNS refusés), 3 low corrigés · 159685f
- 2026-10-18 19:56 · 7.1 · fusion · ff sur main, suite complète verte, CI branche verte sur 6 jobs, story done · 159685f
- 2026-10-18 19:56 · 7.2 · dev · lancé (dev-story Sonnet) · —
- 2026-10-18 19:56 · 7.2 · report · non lancé : même module que 2.4 (terminal, liste blanche AD-4), attend la fusion de 2.4 · —
- 2026-10-18 19:59 · 9.1 · second-avis · 2 medium (hauteurs CSS : min-height et bandeau sur deux lignes font défiler la page), 4 low · —
- 2026-10-18 20:07 · 6.6 · dev · lancé (dev-story Sonnet ; éligible depuis 2.2, repéré par l'outil d'avancement) · —
- 2026-10-18 20:09 · 2.6 · review · rebase sans conflit, medium corrigé (placement à mémoire : un commit antidaté ne déplace plus les autres), 5 low ; écart store.js (2.3) ↔ forme state_projected noté pour 2.7 · e5268ad
- 2026-10-18 20:09 · 2.6 · fusion · ff sur main, suite complète 498 passed / 36 skipped, CI branche verte, story done · e5268ad
- 2026-10-18 20:09 · 4.1 · dev · lancé (dev-story Sonnet, chemin critique) · —
- 2026-10-18 20:19 · 9.1 · review · 2 medium corrigés (bandeau en rangée de grille, plus de constante de hauteur), 3 low ; noms des stations en contenu reportés à 9.2 · 9d2249b
- 2026-10-18 20:19 · 9.1 · fusion · rebase sur b3b0794 par l'orchestrateur, suite complète verte, CI branche verte, ff sur main, story done · ce247ef
- 2026-10-18 20:19 · 6.6 · incident · worktree supprimé par erreur au nettoyage de l'orchestrateur avant tout code, story relancée · —
- 2026-10-18 20:22 · 2.4 · dev · fini, 579 tests, CI verte (Job Object, liste blanche, route interrupt) · 13dc1f3
- 2026-10-18 20:22 · 2.7 · dev · lancé (dev-story Sonnet) · —
- 2026-10-18 20:26 · 2.4 · second-avis · 1 high prouvé (aucune identité git pour l'apprenant : git commit échoue), 2 medium (remote show sur URL arbitraire, français non testé sous Windows), 5 low · —
- 2026-10-18 20:28 · 6.6 · dev · fini, 523 tests, CI verte, sans modèle ni réseau ; 4 vérifications avec un vrai Ollama à faire par Anaël ; instantanés créés en avance (pivot 4.3) · 6aecf4d
- 2026-10-18 20:28 · 9.2 · dev · lancé (dev-story Sonnet) · —
- 2026-10-18 20:29 · 3.1 · review · rebase, medium corrigé (refresh des PR au changement externe), 7 low ; dismiss_stale_reviews en option (défaut false, décision Anaël) · 4faea1b
- 2026-10-18 20:29 · 3.1 · fusion · conflit de fond avec 2.6 (engine/manager.py) résolu par dev-story Opus, rebase sur 8dd9069, suite complète verte, CI branche verte, ff sur main, story done · 290d078
- 2026-10-18 20:29 · — · file · éligibles en attente de créneau : 4.3 ★, 3.2, 3.5, 7.4 ★ · —
- 2026-10-18 20:35 · 6.6 · second-avis · 1 high (instantané 0 pris après les éditions, contraire à AD-6), 4 medium (instantané non vérifié par empreinte, 780 s sans interruption, orphelin à l'arrêt, environnement complet transmis au processus réseau), 4 low · —
- 2026-10-18 20:35 · 6.6 · décision orchestrateur · revue suspendue jusqu'à la fusion de 4.3 ★ (pivot des instantanés) ; la revue rebasera 6.6 sur l'API de 4.3 et retirera engine/snapshots.py de 6.6 · —
- 2026-10-18 20:35 · 4.1 · dev · fini, 524 tests, CI verte (registre des types d'étape, 4 issues de check) · 5c9f187
- 2026-10-18 20:35 · 4.3 · dev · lancé (dev-story Opus ★, chemin critique) · —
- 2026-10-18 20:40 · 4.1 · second-avis · 4 medium (lecture dans un état prévu republie failed, ahead_of non résolu passe à tort, pas intermédiaire licite marqué inattendu, types non-dépôt impossibles sans toucher au moteur), 5 low · —
- 2026-10-18 20:40 · — · outillage · agent-cost-kit v0.6.0 publié (commande /agent-cost-kit:avancement-run), plugin mis à jour au niveau utilisateur · f9bbf9a
- 2026-10-18 20:41 · — · décision Anaël · préparer un arrêt propre pour /clear : plus de nouveau lancement, on draine 2.4 et 4.1 (revues), 2.7, 9.2, 4.3 (dev) · —
- 2026-10-18 20:42 · 9.2 · dev · fini, 505 tests, CI verte (content/chain.yaml, CHAIN_STATIONS supprimé) · 10764e2
- 2026-10-18 20:42 · 2.7 · dev · fini, 513 tests, CI verte (écart store.js/2.6 résolu par projection par volet) · c260d5b
- 2026-10-18 20:44 · 9.2 · second-avis · liste à transmettre au reviewer (session suivante) : M1 catalogue.py:45-92,252 chain.yaml non validé (KeyError → espace qui ne s'ouvre plus ; valider par pydantic, erreurs en français, test de contenu malformé) ; M2 content/chain.yaml `available` figé au lieu du diagnostic réel ; L3 liens de barrière sans cible ; L4 chain.js:116,149 survol qui change aria-pressed et annonce aria-live ; L5 chain.js:61 aria-labelledby sur listitem ; L6 destroy() jamais appelé (workspace.js:580) ; L7 fichier absent → bandeau disparaît sans signal ; L8 lecture disque bloquante dans la boucle (to_thread) ; L9 test tautologique carte_depliee (focus comparé à lui-même) · 10764e2
- 2026-10-18 20:47 · 2.4 · review · rebase sans conflit, high corrigé (identité apprenant via learner.gitconfig en contexte apprenant), remote show borné, reflog write refusé, index.lock seulement si l'arbre est arrêté ; crochet AFTER_COMMAND_HOOKS → github_sim.refresh à brancher (3.1 fusionnée depuis) · 47d010a
- 2026-10-18 20:48 · 2.7 · second-avis · liste à transmettre au reviewer (session suivante) : M1 store.js:33-47 acceptViews retire la vue entière sur type inconnu ou TypeError, `problems` jamais lu → volet Dépôt vide sans diagnostic ; M2 repo.js:12-35,247,261-266 textes et noms accessibles composés côté front (LETTER_TEXT, ACTOR_TEXT, « Arbre de travail propre », aria-label de l'index) → passer côté serveur (AD-2, StagingItem.a11y_name_text) ; M3 repo.css:44-57 + repo.js:167-177 sujet long qui repousse refs et « Nouveau » hors champ ; L4 workspace.js:79,92-103 annonce identique non relue, deux régions role=status, libellé hors FR-4 ; L5 repo.js:212 parent absent affiché en element_id brut ; L6 prompt/announce_text non contrôlés tant que 2.4 ne déclare pas sa projection ; L7 repo.js:105-115 routage des arêtes sur les index et non les rangs · c260d5b
- 2026-10-18 20:57 · 2.4 · fusion · rebase sur 87f5124 par l'orchestrateur, suite complète verte, CI branche verte, ff sur main, story done ; 7.2 et 2.5 deviennent éligibles · 00463d8
- 2026-10-18 21:01 · 4.3 · dev · fini, 540 tests, CI verte ; API des instantanés dans la spec (take_snapshot, restore_snapshot, WorkspaceManager.restore, resume_restore) · 6087374
- 2026-10-18 21:04 · 4.1 · review · rebase (conflits d'ajout), 3 medium corrigés (pending avant foreseen, référence introuvable = échec, StepContext extensible aux types non-dépôt), règle « inattendu » gardée + lint d'avertissement, 4 low · 972570d
- 2026-10-18 21:04 · 4.1 · fusion · reportée : rebase sur ff80137 (2.4) en conflit dans engine/manager.py, engine/operations.py, web/static/js/store.js → dev-story Opus pour finir le rebase, puis suite, CI et fusion (revue déjà faite) · 972570d
- 2026-10-18 21:05 · 4.3 · second-avis · liste à transmettre au reviewer (session suivante) : H1 snapshots.py:210-215,256-283,332-346 _run_restore ne capte que RestoreFailed (GitError ou écriture run.json → pas de restore_failed, restoring reste écrit) ; H2 operations.py:323-325,505 + events/catalog.py:56 après restore_failed l'espace repasse en idle et accepte des écritures sur un état mélangé (« seule action : Recommencer » non appliqué, pas de garde sur restoring) ; M3 snapshots.py:218-231 retour arrière en un seul essai, restoring=None même s'il échoue → plus de reprise ; M4 snapshots.py:314-321 resume_restore supprime repo/origin.git/hooks sans réessai ; L5 tests/test_snapshots.py:306 test quiz_altered limité à Windows, test_restore_failed_dans_la_file n'assert pas l'état moteur ; L6 .staging-N et .restore/trash-* laissés jusqu'à la prochaine restauration ; L7 seuls index.lock/HEAD.lock exclus de la copie ; L8 « Dépôt chargé » annoncé après restauration · 6087374
- 2026-10-18 21:05 · — · arrêt propre · fin de session d'orchestration (contexte chargé) ; reprise par une nouvelle session, cf. section « Reprise » · —
- 2026-10-18 21:25 · — · reprise · nouvelle session d'orchestration · —
- 2026-10-18 21:25 · 4.1 · dev · dev-story Opus lancé pour finir le rebase (worktree existant) · —
- 2026-10-18 21:25 · 4.3, 2.7, 9.2 · review · reviewers Opus lancés avec la liste du second avis (worktrees existants) · —
- 2026-10-18 21:25 · 3.2, 2.5 · dev · lancés (dev-story Sonnet, nouveaux worktrees) ; 3.5, 7.4 ★, 7.2 en attente d'un créneau (3.5 et 7.4 touchent github_sim comme 3.2, 7.2 le terminal comme 2.5) · —
- 2026-10-18 21:40 · 4.1 · dev · rebase fini par dev-story Opus (conflits d'ajout seulement : git_path + panel, OpContext, store.js), 731 passed / 37 skipped, CI branche verte sur 6 jobs · 09a7afd
- 2026-10-18 21:40 · 4.1 · fusion · ff sur main, story done ; 4.2 devient éligible (test d'ordre terminal_output → step_verdict non écrit, noté) · 09a7afd
- 2026-10-18 21:40 · 4.2 · dev · lancé (dev-story Sonnet, chemin critique) · —
- 2026-10-18 21:45 · 4.3 · review · rebase (config.py trivial), H1 corrigé (toute erreur → restore_failed), M3 (retour arrière 3 essais, restoring gardé), M4 (reprise au démarrage suivant), H2 ramené à medium et reporté à 4.4 (spec), L5 assert moteur, L6-L8 écartés/reportés ; 714 passed, CI branche verte · 60db8da
- 2026-10-18 21:45 · 4.3 · fusion · rebase sur eb6cfbc par l'orchestrateur (imports engine/__init__ et manager, trivial), suite complète en cours · —
- 2026-10-18 21:45 · 3.2 · dev · fini, 703 passed / 37 skipped, CI verte ; crochet AFTER_COMMAND_HOOKS → refresh branché ; schéma de pr_updated laissé ouvert pour 3.3 · 3572cd7
- 2026-10-18 21:45 · 3.2 · second-avis · lancé · —
- 2026-10-18 21:45 · 9.2 · review · rebase sans conflit, M1 corrigé (chain.yaml validé par pydantic, 6 cas invalides testés), M2 corrigé (available calculé par toolrun.resolve, ~150 ms), L8 to_thread, L9 vrai test ; L3-L7 écartés (motifs en spec) ; 706 passed, CI branche verte · f3097a1
- 2026-10-18 21:45 · — · décision pour Anaël · 9.2 : disponibilité des outils de la carte issue de la sonde réelle (gitleaks absent → tirets) au lieu du contenu figé ; défaut gardé, à confirmer · —
- 2026-10-18 21:45 · 4.3 · fusion · ruff : ordre d'imports après résolution, corrigé ; suite relancée · —
- 2026-10-18 21:51 · 3.2 · second-avis · aucun high, 1 medium (état github.json non écrit après update-ref réussi → second merge possible), 6 low (pas de pr_updated sur refus, préflight hors file, _update_ref trompeur, merge vide, câblage app non testé, lecture sans retry) ; reviewer Opus lancé · —
- 2026-10-18 21:52 · 2.7 · review · rebase (3 conflits d'ajout), medium trouvé en revue corrigé (arête traversant un commit de même rang, tracé par bandes + test géométrique), M2 (a11y_name_text côté serveur), M3 (sujet tronqué 48ch), M1→low console.warn, L5, fuite externalOps ; L4 reporté (NVDA/VoiceOver), L6 écarté ; 709 passed, CI branche verte · e8361a7
- 2026-10-18 21:55 · 4.3 · fusion · suite complète 748 passed / 37 skipped après rebase, CI branche en cours · 8c6effa
- 2026-10-18 21:55 · 2.5 · dev · fini, 86 tests de confinement, CI verte sur les trois OS (liens symboliques testés en CI) ; test de performance de projections en échec local non relancé · b0350c5
- 2026-10-18 21:55 · 2.5 · second-avis · lancé · —
- 2026-10-18 22:00 · 4.3 · fusion · CI branche verte sur 6 jobs, ff sur main, story done ; 4.5 éligible, revue 6.6 débloquée · 8c6effa
- 2026-10-18 22:00 · 2.5 · second-avis · 1 high prouvé (cp -r copie le contenu d'une jonction Windows hors espace), 3 medium (cp -r recopie un lien sortant sous POSIX, lecture/écriture intégrale sans limite, rm -rf * accepté sans décision), 5 low (noms réservés CONIN$/caractères interdits, parents créés par >, CRLF/BOM recopiés, .git imbriqué copié, OSError de ls) ; échec de perf local dû à la charge · —
- 2026-10-18 22:01 · 2.5, 6.6 · review · reviewers Opus lancés (6.6 rebase sur l'API d'instantanés de 4.3, branchement procs.spawn) · —
- 2026-10-18 22:01 · 4.5 · dev · lancé (dev-story Sonnet) · —
- 2026-10-18 22:01 · 4.2 · dev · fini, 746 passed, CI verte (ProgressStore, faits dédupliqués sur ce qu'ils constatent, rejeu au démarrage) · 58f34b7
- 2026-10-18 22:01 · 4.2 · second-avis · lancé · —
- 2026-10-18 22:05 · 4.2 · second-avis · aucun high, 1 medium (test du Recommencer qui ne prouve que le rejeu), 7 low (atomicité non testée, verrou intra-processus, ordre du rejeu, progress.json corrompu bloquant, clé d'idempotence non vérifiée, champ manquant → fait perdu, émetteurs quiz/indice reportés) ; reviewer Opus lancé · —
- 2026-10-18 22:15 · 9.2 · fusion · suite complète 757 passed / 37 skipped, CI branche verte sur 6 jobs, ff sur main, story done · fa3df43
- 2026-10-18 22:15 · — · suivi · sprint-status aligné (2.5, 3.2, 4.2, 2.7, 6.6 en review ; 4.5 in-progress) · —
- 2026-10-18 22:16 · 2.7 · fusion · rebase sur 0a06348 en conflit de fond (région role=status partagée : statut d'étape 4.1 / annonce de commande 2.7) → dev-story Opus pour finir le rebase · —
- 2026-10-18 22:23 · 2.5 · review · rebase (wsfs trivial), high corrigé et élargi (jonction Windows traitée comme un lien : cp refuse, cp -r refuse un dossier qui en contient), cat borné à 256 Kio, echo >> sans relecture, noms non portables, parents absents, .git imbriqué, OSError ; lien sortant copié comme lien gardé (comme cp -R) ; 845 passed, CI branche verte · 407b90a
- 2026-10-18 22:23 · — · décision pour Anaël · 2.5 : rm -rf * à la racine accepté comme dans un shell (Recommencer répare) ; ajouter une garde (confirmation ou refus) ? · —
- 2026-10-18 22:23 · 2.5 · fusion · rebase sur 0a06348 sans conflit, suite complète et CI en cours · 049527b
- 2026-10-18 22:23 · — · outillage · agent-cost-kit PR #11 (avancement-run : sans détail par story quand il y a des epics, barres █░), v0.6.4 non publiée · 98e0c68
- 2026-10-18 22:25 · — · outillage · agent-cost-kit v0.6.4 publié (PR #11 fusionnée, tag et release), plugin mis à jour au niveau utilisateur, actif après redémarrage · 5d741ee
- 2026-10-18 22:26 · — · décision Anaël · préparer un arrêt propre pour /clear : plus de nouveau lancement, on draine 2.5 (fusion), 2.7 (rebase), 3.2, 4.2, 6.6 (revues), 4.5 (dev) · —
- 2026-10-18 22:27 · 6.6 · review · rebase sur 6860667 (snapshots de 4.3 gardés, instantané exercise vérifié par empreinte avant lancement), toolrun.spawn_module → procs.spawn (interruption, Job Object, codes 124/130), environnement réduit, HIGH et 4 MEDIUM corrigés ; uv sync non interruptible reporté à 7.2 ; 774 passed, CI branche verte ; vérifications Ollama réel pour Anaël · aa6aa74
- 2026-10-18 22:30 · 3.2 · review · rebase sur 0a06348 sans conflit, medium corrigé (merge écrit dans origin reconnu, pas de second commit), 5 low corrigés (pr_updated sur refus, GitError distincte de la course, rien à merger, faux 409 sur lecture illisible, 5 tests dont câblage create_app), préflight hors file gardé (critère 409 synchrone) ; CI branche verte · 0c30c2f
- 2026-10-18 22:32 · 4.2 · review · rebase sur 0a06348 sans conflit, medium trouvé en revue corrigé (rejeu par liste validated dans run.json, plus par position), medium du second avis corrigé (vrai rétablissement + seconde validation), test d'arrêt brutal, all_progress() ; low 3-7 écartés (motifs en spec) ; 775 passed, CI branche verte · 5349972
- 2026-10-18 22:36 · 2.5 · fusion · suite complète 854 passed / 41 skipped, CI branche verte sur 6 jobs, ff sur main, story done ; 7.2 éligible · 049527b
- 2026-10-18 22:37 · 2.7 · fusion · rebase par dev-story Opus (une région role=status : annonce de commande puis statut d'étape, test DOM combiné), 770 passed, CI verte · 42c695f
- 2026-10-18 22:37 · 3.2, 4.2, 6.6, 2.7 · fusion · empilées dans cet ordre sur 8bb7571 (6.6 : conflits d'ajout app.py et workspace.js résolus par l'orchestrateur), 4 branches poussées pour CI, suite complète locale sur le sommet de pile en cours · 2.7 fbcb3ef
- 2026-10-18 22:44 · 4.5 · dev · fini, 763 passed, CI verte (type d'étape quiz, restore_state, écritures refusées en quiz_altered et après restore_failed = H2 de 4.3) ; premier essai dans run.json.quiz_first à brancher sur ProgressStore (4.2) ; intention restart à créer par 4.4 · 9c3119a
- 2026-10-18 22:44 · 4.5 · second-avis · lancé · —
- 2026-10-18 22:45 · 3.2, 4.2, 6.6, 2.7 · fusion · suite complète sur le sommet de pile 922 passed / 41 skipped · fbcb3ef
- 2026-10-18 22:45 · 3.2 · fusion · CI branche verte, ff sur main, story done ; 3.3, 3.5, 7.4 ★ éligibles · 8c4040d
- 2026-10-18 22:45 · 4.2 · fusion · CI branche verte, ff sur main, story done ; 4.4 éligible (4.2 et 4.3 done) · d73cbef
- 2026-10-18 22:46 · 6.6 · fusion · CI branche verte sur 6 jobs, fusion sur main (commit de fusion avec 2.7), story done ; 4 vérifications Ollama réel en attente d'Anaël · 430c980
- 2026-10-18 22:46 · 2.7 · fusion · CI branche verte sur 6 jobs, fusion sur main, story done ; 2.10 attend encore 2.8 et 3.3 · fbcb3ef
- 2026-10-18 22:01 · 9.2 · fusion · rebase sur 6860667 sans conflit, suite complète en cours · —
- 2026-10-18 22:47 · 4.5 · second-avis · liste à transmettre au reviewer (session suivante) : H1 operations.py:410-418 + snapshots.py:_run_restore Recommencer refusée après restore_failed (garde quiz_altered toujours active, _rest pas remis à idle ; test test_quiz.py:277-288 ne pose pas _rest) ; H2 operations.py:410-418,556 + terminal/quiz.py:392-413 deux quiz_choice soumis avant la fin du premier passent la garde (contrôle seulement à submit), le second écrase run.json.quiz → empreinte ≠ après restore_state (prouvé par sonde) ; M3 terminal/quiz.py:405-416 save_run(quiz) avant _run_git et set_rest_state après → run.json.quiz posé mais _rest idle si git lève ; M4 quiz.js:558-559 + terminal/quiz.py:322-324 « score du premier coup conservé » mais seul run.json.quiz_first est écrit → brancher sur ProgressStore de 4.2 (fusionnée) ; M5 tests : cas réel de restore_failed et soumissions concurrentes non testés ; L6 restore_state encore admis après restore_failed ; L7 exemption setup saine ; L8 un op d'écriture déclaré writes=False contournerait la garde · 9c3119a
- 2026-10-18 22:47 · — · arrêt propre · fin de session d'orchestration avant /clear ; reprise par une nouvelle session, cf. section « Reprise » · 63d065e
- 2026-10-18 23:00 · — · reprise · nouvelle session d'orchestration · —
- 2026-10-18 23:00 · 4.5 · review · reviewer Opus lancé avec la liste du second avis (worktree existant ; rebase sur main et premier essai branché sur ProgressStore) · —
- 2026-10-18 23:00 · 3.4, 2.8, 5.2 · dev · lancés (dev-story Sonnet, nouveaux worktrees) ; 5.2 ajouté aux éligibles (4.1, 4.2, 2.6 done), chemin critique de l'Epic 5 ; 3.3, 3.5, 7.4 ★ attendent 3.4 (github_sim), 7.2 attend 2.8 (terminal), 4.4, 4.6, 4.7 attendent la revue de 4.5, 6.1 en attente d'un créneau · —
- 2026-10-18 23:28 · 4.5 · review · rebase (store.js, workspace.js : conflits d'ajout), H1 (restart passe les deux refus), H2 (garde revérifiée à l'exécution + precheck du choix), M3, M4 (fait quiz_first_attempt dans ProgressStore), M5 (6 tests), L6 corrigés ; L7, L8 écartés ; 941 passed / 41 skipped, 1 échec instable test_toolrun (passe seul) ; CI branche verte sur 6 jobs ; pour 4.4 : restart doit remettre le repos à idle · c4898b2
- 2026-10-18 23:31 · 4.5 · fusion · rebase sur le suivi (sans code), tests ciblés 52 passed, ff sur main, story done ; 4.4, 4.6, 4.7 éligibles (créneaux pleins : 3.4, 2.8, 5.2) · 47ed73f
- 2026-10-18 23:33 · 3.4 · dev · fini, 932 passed / 41 skipped, CI verte sur 6 jobs (SHA du commit collègue identique sur les trois OS) ; ops colleague_commit et colleague_reaction (trigger pr_opened | checks_green), registre pour 5.1 (commit_on_origin, add_reaction, set_check_state) ; vue review-log reportée à 3.3 · 2be1fb2
- 2026-10-18 23:33 · 3.4 · second-avis · lancé · —
- 2026-10-18 23:33 · 6.1 · dev · lancé (dev-story Sonnet ; ouvre 6.2, 6.4, 9.3 ; hors moteur d'étapes pris par 5.2) · —
- 2026-10-18 23:36 · 3.4 · second-avis · aucun high, 1 medium (commit_on_origin force parent = old et ignore start : pas de commit non fast-forward pour 5.1), 3 low (add_reaction/set_check_state hors file, SHA verrouillé, empreinte pré-3.4 non épinglée) ; reviewer Opus lancé · —
- 2026-10-18 23:37 · 5.2 · dev · fini, 936 passed / 41 skipped, CI verte sur 6 jobs ; type d'étape designate, answer_submit (409 au second essai), answer_corrected, route resolve_sha ; premier essai via quiz_first_attempt ; pour 4.4 : Recommencer vide run.json.answers · 5351412
- 2026-10-18 23:37 · 5.2 · second-avis · lancé · —
- 2026-10-18 23:37 · 4.6 · dev · lancé (dev-story Sonnet ; nécessaire à 6.2) · —
- 2026-10-18 23:39 · 2.8 · dev · fini, 955 passed / 41 skipped, CI verte sur 6 jobs ; save_file (base_hash, 409 revérifié dans la file), open_external via procs, GET code/tree, file, diff ; éditeur textarea natif (consigné en Deferred du spine) ; contrôles navigateur pour Anaël (gouttière, 24 px, lecteur d'écran, ouverture système, conflit) · 4423cef
- 2026-10-18 23:39 · 2.8 · second-avis · lancé · —
- 2026-10-18 23:39 · 4.7 · dev · lancé (dev-story Sonnet ; ouvre 6.5) ; 7.2 garde son tour (toolrun touché par 2.8) · —
- 2026-10-18 23:44 · 2.8 · second-avis · aucun high, 6 medium (CRLF perdus à la sauvegarde, open_external exécute .bat/.exe via os.startfile, bit x perdu sous POSIX, restore_failed non gardé avant 4.5, fichiers créés absents du diff, aria-label sur div sans role), 4 low ; reviewer Opus lancé · —
- 2026-10-18 23:45 · 5.2 · second-avis · aucun high, 3 medium (answer_submit sans step_id vise la désignation suivante, writes=False contourne la garde quiz_altered, branche partie avant 4.5 : rebase de fond sur steps.py et operations.py), 3 low (test de rejeu instable, assertions, annonce relancée) ; reviewer Opus lancé avec rebase soigné · —
- 2026-10-19 00:00 · 6.1 · dev · fini, 952 passed / 41 skipped, CI verte sur 6 jobs ; GET /api/catalogue?track=, états depuis ProgressStore, mode indisponible (409 sur /api/open), path-menu ; parcours en localStorage ; SOCLE_ORDER impose les scenario_id de 6.2 et 6.3 ; contrôles navigateur pour Anaël · fc7aafe
- 2026-10-19 00:00 · 6.1 · second-avis · lancé · —
- 2026-10-19 00:00 · 7.2 · dev · lancé (dev-story Sonnet ; reprend uv sync non interruptible reporté par 6.6) · —
- 2026-10-19 00:01 · 3.4 · review · rebase sans conflit, aucun medium réel : M1 ramené à low (spec et docstring corrigées, 5.1 ajoutera parent explicite et update-ref de réécriture), L2 écarté (appelant dans la file ; report pour 7.4), L3 confirmé (CI trois OS), L4 corrigé (empreinte d'avant 3.4 épinglée) ; 954 passed / 41 skipped, CI branche verte sur 6 jobs · cf4cb79
- 2026-10-19 00:03 · 3.4 · fusion · rebase sur le suivi (sans code), tests ciblés 32 passed, ff sur main, story done ; 3.3, 3.5, 7.4 ★ et 5.1 éligibles (créneaux pleins : 4.6, 4.7, 7.2) · ffb753f
- 2026-10-19 00:04 · 6.1 · second-avis · aucun high, 2 medium (progress.json corrompu → 500 sur /api/catalogue, boucle silencieuse du picker côté front), 5 low (track vide, radiogroup sans flèches, SOCLE_ORDER non testé, 409 nomme tool_id, skip sans Node) ; reviewer Opus lancé · —
- 2026-10-19 00:07 · 4.7 · dev · fini, 955 passed / 41 skipped, CI verte ; bilan calculé à la lecture par build_summary (rien d'écrit), Scénario suivant / Catalogue / Recommencer ; restart attend 4.4, émetteur hint_opened attend 4.6, désignations à brancher dans derive · cccbc8c
- 2026-10-19 00:07 · 4.7 · second-avis · lancé · —
- 2026-10-19 00:07 · 5.1 · dev · lancé (dev-story Sonnet ; chemin critique de l'Epic 5, réutilise le registre de 3.4) ; 3.3 au prochain créneau · —
- 2026-10-19 00:07 · 4.6 · dev · fini, 964 passed / 41 skipped, CI verte ; hint_open en 3 paliers ordonnés (solution après un essai ou 20 s), fait hint_opened à la clôture de lecture, rejeu au réveil, tablist avec cadenas ; aucun scénario ne déclare encore hints · bffc618
- 2026-10-19 00:07 · 4.6 · second-avis · lancé · —
- 2026-10-19 00:07 · 3.3 · dev · lancé (dev-story Sonnet ; ouvre 2.10 ; vue review-log reportée par 3.4) · —
- 2026-10-19 00:10 · 4.7 · second-avis · aucun high, 2 medium (_next_scenario en ordre lexical au lieu de l'ordre FR-9 de 6.1, progress.json absent → « Aucune question »), 6 low ; reviewer Opus lancé (ordre à porter hors de web, à aligner avec 6.1) · —
- 2026-10-19 00:11 · 4.6 · second-avis · aucun high, 1 medium (hint_pending non clos par Recommencer, restauration ni snapshot → fait hint_opened perdu), 4 low (read_ms sans plafond, hint_open admis en restore_failed, onglets verrouillés hors Tab, commande refusée non comptée comme essai) ; reviewer Opus lancé · —
- 2026-10-19 00:15 · 5.2 · review · rebase sur main (un conflit de fond dans engine/steps.py validate et panel : tout 4.5 gardé, marques designable ajoutées), M1 corrigé (step_id obligatoire, 422 sinon), L4 (test de rejeu stabilisé), L6 (annonce non relancée sur même op_id) ; M2 écarté (quiz_altered laisse le quiz courant, désignation refusée), L5 sans objet ; 960 passed / 41 skipped, CI branche verte sur 6 jobs · cf75e4f
- 2026-10-19 00:15 · — · décision pour Anaël · 5.2 : ajouter step_id (obligatoire) à answer_submit dans AD-17 du spine · —
- 2026-10-19 00:19 · 5.2 · fusion · rebase sur le suivi (sans code), tests ciblés 58 passed, ff sur main, story done ; 5.3, 5.4 et 4.4 éligibles (créneaux pleins : 7.2, 5.1, 3.3 ; 4.4 attendra aussi 4.6 pour la clôture des indices) · 884560f
- 2026-10-19 00:20 · 6.1 · review · rebase sans conflit, M1 (progress.json illisible → motif français), M2 (pas de boucle de repli, LOAD_FAILED), L5 (test de dérive SOCLE_ORDER), L6 (libellé d'outil au 409) corrigés ; L3, L4, L7 écartés ; 967 passed, CI branche verte · 9d68f20
- 2026-10-19 00:20 · — · décision pour Anaël · 6.1 : valider les identifiants du socle (add-commit, push-pull, branche, pr-merge, conflit, stash, rebase, recuperation) avant 6.2 · —
- 2026-10-19 00:25 · 2.8 · review · rebase sans conflit, M2 relevé en high et corrigé (ouverture comme texte : verbe edit / Bloc-notes, open -t, xdg-open hors .desktop), M5 (non suivis dans le diff), M6 (rôles heading/group), M3 (droits conservés), L8, L9 partiel corrigés ; M1 (LF, règle wsfs), M4 (déjà refusé, test ajouté), L7, L10 écartés ; 983 passed, CI branche verte · 3ceae98
- 2026-10-19 00:25 · — · décision pour Anaël · 2.8 : sous Windows, un fichier sans verbe edit s'ouvre dans le Bloc-notes (sécurité) ; à vérifier sur poste · —
- 2026-10-19 00:28 · 4.7 · review · rebase sans conflit, M1 (ordre FR-9 dans scenarios/order.py hors web), M2 (total des questions tiré du scénario), L4, L8 corrigés ; L3, L7 écartés ; L5, L6 reportés à 4.4 ; 971 passed, CI branche verte · a0c3ac4
- 2026-10-19 00:30 · 4.6 · review · rebase sans conflit, M1 corrigé (hints.settle appelé par setup replace et restore ; 4.4 devra l'appeler), L2 (read_ms plafonné à 15 min), L5 (commande refusée = essai) corrigés ; L3, L4 écartés ; 979 passed, CI branche verte · 57a5f6d
- 2026-10-19 00:30 · — · décision pour Anaël · 4.6 : plafond de lecture 15 min ; une commande refusée débloque la solution comme un essai · —
- 2026-10-19 00:30 · 6.1, 2.8, 4.7, 4.6 · fusion · empilées dans cet ordre : 6.1 sur main (suite complète 985 passed / 41 skipped), 2.8 sur 6.1 (conflit d'ajout app.py résolu par l'orchestrateur, suite complète du sommet 1026 passed / 42 skipped), 4.7 sur 2.8 (conflit d'ordre d'initialisation manager.py résolu, catalogue de 6.1 aligné sur scenarios.order) ; 4.6 sur 4.7 en conflit de fond (steps.py, app.py, store.js, scenario.js, workspace.css) → dev-story Opus pour le rebase · 0959686
- 2026-10-19 00:42 · 6.1 · fusion · CI branche verte sur 6 jobs, ff sur main, story done · 4720ff4
- 2026-10-19 00:42 · 3.3 · dev · fini, 975 passed / 41 skipped, CI verte ; projection views.remote (branches distantes, pr-card, checks, raisons liées, review-log), element_id pr:, check:, review: documentés pour 2.10 · 3a2c25a
- 2026-10-19 00:42 · 3.3 · second-avis · lancé · —
- 2026-10-19 00:42 · 5.3 · dev · lancé (dev-story Sonnet ; chemin critique de l'Epic 5) · —
- 2026-10-19 00:42 · 4.6 · fusion · dev-story Opus lancé pour le rebase de fond sur la pile 4.7 (worktree existant, sans push) · —
- 2026-10-19 00:43 · 4.7 · fusion · branche empilée (6.1 + 2.8 + 4.7 + alignement) poussée, CI branche en cours ; 2.8 CI branche en cours · 0959686
- 2026-10-19 00:43 · 7.2 · dev · fini, 992 passed / 45 skipped, CI verte ; ruff et pytest dans la section tools de la liste blanche (déclarés par scénario), sortie tool-output, liens fichier:ligne par relance machine, fait evidence_seen, scénarios defaut-de-lint.A et test-casse.A, uv sync interruptible ; étapes à valider sur le résultat d'outil plus tard · d4a2799
- 2026-10-19 00:43 · 7.2 · second-avis · lancé · —
- 2026-10-19 00:44 · 5.1 · dev · fini, 966 passed / 41 skipped, CI verte (SHA épinglés identiques sur trois OS) ; ops agent_commit, agent_push_force, stash, agent_rebase_conflict ; commit_on_origin reçoit parent et force en ajout · 1c4c899
- 2026-10-19 00:44 · 5.1 · second-avis · lancé · —
- 2026-10-19 00:44 · 3.5 · dev · lancé (dev-story Sonnet ; ouvre 5.7 et 7.3) ; 5.4 attend 5.3 (même front), 4.4 attend 4.6 · —
- 2026-10-19 00:44 · — · notification · 4 décisions non bloquantes envoyées à Anaël (ids du socle avant 6.2, step_id AD-17, Bloc-notes 2.8, plafond indices 4.6) · —
- 2026-10-19 00:45 · 2.8 · fusion · CI branche verte sur 6 jobs (pile 6.1 + 2.8), commit de fusion sur main (code identique à la branche testée), story done · d60cd1d
- 2026-10-19 00:48 · 5.1 · second-avis · aucun high, 1 medium (agent_rebase_conflict réussit en silence si un rebase est déjà en cours, reproduit), 5 low (date sans effet, commit sans pathspec, stash include_untracked, pas de reflog sur origin nu, SHA vérifiés en local sous Windows seulement) ; reviewer Opus lancé · —
- 2026-10-19 00:52 · 7.2 · second-avis · aucun high, 3 medium (pytest -- -p charge un greffon malgré l'invariant « ni -p », prouvé ; Ctrl+C sans effet pendant la relance machine ; uv sync échoué jamais retenté), 4 low ; reviewer Opus lancé · —
- 2026-10-19 00:58 · 3.3 · second-avis · aucun high, 1 medium (conflits textuels prévisibles avec 2.8 dans views.js et index.html), 7 low (focus après Merger, Ouvrir une PR masqué si contenue, Literal sans test d'égalité, « sur m » absent sans protection…) ; reviewer Opus lancé · —
- 2026-10-19 01:09 · 4.7 · fusion · CI branche verte sur 6 jobs, suite complète du sommet de pile 1043 passed / 42 skipped, commit de fusion sur main, story done ; 6.5 éligible · 48fd456
- 2026-10-19 01:10 · 4.6 · fusion · rebase de fond sur la pile 4.7 fini par dev-story Opus (steps.py, app.py, workspace.css, store.js, scenario.js : deux côtés gardés), test d'intégration bilan + indice ajouté ; tests ciblés 133 passed, suite complète en lots 936 + 133 passed, aucun échec ; branche poussée, CI en cours · 316f3dc
- 2026-10-19 01:11 · 6.5 · dev · lancé (dev-story Sonnet ; contrat du bilan de 4.7) ; 4.4 attend la fusion de 4.6 (hints.settle) · —
- 2026-10-19 01:12 · 5.3 · dev · fini, 993 passed / 41 skipped, CI verte ; front seul : designation.js (mode armé, answer-slot, champ SHA via resolve_sha, step_id toujours joint), data-designable dans repo.js ; correction affichée reportée à 5.5, liste filtrable à 5.4 ; contrôles navigateur pour Anaël · 4ad6a6d
- 2026-10-19 01:12 · 5.3 · second-avis · lancé · —
- 2026-10-19 01:12 · 2.9 · dev · lancé (dev-story Sonnet ; 2.8 done ; ouvre 2.10 avec 3.3) ; 5.4 attend 5.3 (même front), 7.4 ★ attend que github_sim se libère (3.3, 3.5) · —
- 2026-10-19 01:15 · 5.3 · second-avis · aucun high, 2 medium (pas de garde synchrone sur Valider : double POST ; conflits prévisibles scenario.js et workspace.css avec 4.7 et 4.6), 4 low (resolve_sha sans contrôle de type ni doublon, refs non désignables au clavier, écouteurs cumulés, Échap avec la chaîne ouverte) ; reviewer Opus lancé (rebase sur 4.6) · —
- 2026-10-19 01:17 · 3.5 · dev · fini, 994 passed / 41 skipped, CI verte sur trois OS (sh de PortableGit) ; paquet hooks, op install_hooks, core.hooksPath=../hooks dans origin.git (GIT_CONFIG_COUNT retiré par receive-pack), message terminal protected_branch ; empreinte de hooks/ dépendante du poste · 0745cb7
- 2026-10-19 01:17 · 3.5 · second-avis · lancé · —
- 2026-10-19 01:20 · 5.1 · review · rebase sans conflit, M1 corrigé (rebase déjà en cours refusé, code 1 exigé, test), L3 corrigé (commit -- fichiers), L2 écarté (date des commits rejoués), L4, L5 notés au contrat pour 5.6 à 5.8, L6 confirmé par la CI ; 1039 passed / 42 skipped, CI branche verte sur 6 jobs · 71265a3
- 2026-10-19 01:24 · 4.6 · fusion · CI branche verte sur 6 jobs, commit de fusion sur main, story done ; 4.4 et 6.2 (si 3.4, 4.5, 4.6, 6.1 done : oui) éligibles · a0f8127
- 2026-10-19 01:24 · 4.4 · dev · lancé (dev-story Sonnet ; intention restart attendue par 4.5, 4.6, 4.7, 5.2) · —
- 2026-10-19 01:24 · 5.1 · fusion · rebase sur main sans conflit, branche poussée, suite complète et CI en cours · —
- 2026-10-19 01:30 · 3.5 · second-avis · aucun high, aucun contournement trouvé ; 3 medium (message de protection affiché aussi pour un non fast-forward, interpréteur figé : venv déplacé → tous les pushes refusés sans explication, exception non GithubSimError → tout refusé), 6 low ; reviewer Opus lancé · —
- 2026-10-19 01:45 · 7.2 · review · rebase sans conflit, M1 (`--` et valeurs commençant par `-` refusés : pytest -k -p chargeait aussi un greffon), M2 (relance machine interruptible, code 130), M3 (uv sync retenté), medium trouvé en revue (section: stations, sinon rangés dans le socle), test Ctrl+C stabilisé ; L4-L6 écartés, L7 reporté (poste réel) ; CI branche verte sur 6 jobs · f5d1c1d
- 2026-10-19 01:45 · — · décision pour Anaël · 7.2 : scénarios de station 1 absents du catalogue jusqu'à 9.3 (ou les ajouter au socle en attendant) ; evidence_seen limité aux codes 0 et 1 ? · —
- 2026-10-19 01:52 · 5.1 · fusion · suite complète 1082 passed / 42 skipped, CI branche verte sur 6 jobs, commit de fusion sur main, story done ; 5.6 attend 5.5 · 0fde9cc
- 2026-10-19 01:53 · 7.2 · fusion · rebase sur main (conflits d'ajout operations.py submit_facts/output, workspace.py hints/_prepare_tool_environment, résolus par l'orchestrateur), ruff vert, branche poussée, suite complète et CI en cours · —
- 2026-10-19 02:06 · 5.3 · review · rebase sur 4.6 (scenario.js, workspace.css ; bloc désignation sous la consigne), M1 (garde d'envoi de Valider), L3 partiel (SHA hors type ou hors étape ignoré) corrigés, 2 tests ; L5 écarté, L4 (5.4), L6 reportés ; 1079 passed, CI branche verte · 123706c
- 2026-10-19 02:06 · — · décision pour Anaël · 5.3 : priorité d'Échap entre chaîne ouverte et mode Désigner · —
- 2026-10-19 02:06 · 3.3 · review · rebase (views.js, index.html : deux côtés gardés), medium trouvé en revue corrigé (designable dans la vue distante selon le contrat 5.2), L2, L4, L6, L8 corrigés ; L3, L5, L7 écartés ; 1050 passed, CI branche verte · d134366
- 2026-10-19 02:06 · — · décision pour Anaël · 3.3 : Ouvrir une PR masqué pour une branche déjà contenue, « sur m » omis sans protection (écarts à la lettre des critères) · —
- 2026-10-19 02:06 · 7.2, 5.3, 3.3 · fusion · CI 7.2 verte sur 6 jobs (287b1c9) ; 5.3 puis 3.3 empilées sans conflit, branches poussées ; suite de 7.2 seule arrêtée au profit d'une suite complète unique sur le sommet de pile (en cours) ; CI 5.3 et 3.3 en cours · —
- 2026-10-19 02:06 · — · proposition · la suite complète locale dure ~26 min (7 min en début de soirée) : pytest-xdist la diviserait par 3 ou 4 ; dépendance de dev à ajouter à la table Stack, accord d'Anaël requis · —
- 2026-10-19 02:08 · 6.5 · dev · fini, 1057 passed / 42 skipped, CI verte ; progress/report.py (rapport calculé à la lecture, HTML autonome Jinja2 et CSV ; BOM, ;, cellules neutralisées), GET /api/report et /api/report/export, enregistrement côté navigateur ; scenario_reset attendu de 4.4 · b04150a
- 2026-10-19 02:08 · 6.5 · second-avis · lancé · —
- 2026-10-19 02:08 · 6.2 · dev · lancé (dev-story Sonnet ; identifiants du socle de scenarios/order.py gardés en attendant la décision d'Anaël) · —
- 2026-10-19 02:08 · — · note · les heures de 00:10 à 01:45 consignées par lots dans cette session sont des heures de réception estimées (± 5 min) ; les heures des fusions et des commits cités sont exactes · —
- 2026-10-19 02:16 · 6.5 · second-avis · aucun high, 3 medium (neutralisation CSV partielle prouvée, scenario_reset seul rend « En cours » et nom non partagé avec 4.4, ALLOW_DOWNLOADS pywebview non vérifié), 5 low ; reviewer Opus lancé ; 4.4 prévenue du nom scenario_reset · —
- 2026-10-19 02:16 · 3.5 · review · rebase sans conflit, high trouvé en revue (empreinte de hooks/ dépendante du chemin Python → canonical_script), M1 (message seulement si le hook a été atteint, d'après les refs), M2 (hooks.refresh avant chaque push), M3, L4, L5, L7 corrigés ; L6 écarté (AD-9), L8 reporté ; 1085 passed, CI branche verte · 7d8d19c
- 2026-10-19 02:16 · — · décision pour Anaël · 3.5 : erreur imprévue du hook = push refusé, github.json illisible = push accepté (asymétrie voulue) · —
- 2026-10-19 02:16 · 2.9 · dev · fini, 1051 passed, CI verte ; lot retenu pendant le silence post-commande, notice « Modifié hors de l'application », conflit dès que le disque change ; watch_quiet_ms 300 · 1e17ef0
- 2026-10-19 02:16 · 2.9 · second-avis · lancé · —
- 2026-10-19 02:16 · 7.4 ★ · dev · lancé (dev-story Opus ; pivot Sprint 2, ouvre 7.5, 7.6, 8.1) · —
- 2026-10-19 02:17 · 7.2 · fusion · suite complète du sommet de pile (7.2 + 5.3 + 3.3) 1173 passed / 46 skipped, CI branche verte sur 6 jobs, commit de fusion sur main, story done ; 7.3 attend 3.5 · 43c095b
- 2026-10-19 02:20 · 2.9 · second-avis · aucun high, 2 medium (changement pendant la suspension écarté et jamais rejoué, prouvé ; test de latence qui ne contrôle que le dernier essai), 6 low ; reviewer Opus lancé · —
- 2026-10-19 02:20 · 5.3 · fusion · CI branche verte sur 6 jobs, suite du sommet de pile 1173 passed, commit de fusion sur main, story done ; 5.4 et 5.5 éligibles · 9df9dbe
- 2026-10-19 02:21 · 3.3 · fusion · CI branche verte sur 6 jobs, suite du sommet de pile 1173 passed, commit de fusion sur main, story done ; 2.10 éligible (2.7, 2.8, 3.3 done) · 7f11ee9
- 2026-10-19 02:21 · 3.5 · fusion · rebase sur main sans conflit, branche poussée, suite complète et CI en cours · —
- 2026-10-19 02:31 · 4.4 · dev · fini, 1094 passed / 42 skipped, CI verte sur 6 jobs ; intention restart (engine/restart.py) : hints.settle, initial_run, instantané 0 vérifié ou reconstruction par setup, repos idle ; fait scenario_reset ignoré par derive ; confirmation en ligne, encart content_changed · 1ed0226
- 2026-10-19 02:31 · — · décision pour Anaël · 4.4 : ajouter scenario_reset à AD-14 du spine · —
- 2026-10-19 02:31 · 4.4 · second-avis · lancé · —
- 2026-10-19 02:31 · 5.5 · dev · lancé (dev-story Sonnet ; chemin critique de l'Epic 5) ; 5.4 attend 5.5 (même front), 2.10 au prochain créneau · —
- 2026-10-19 02:35 · 4.4 · second-avis · aucun high, 2 medium (derive ne borne pas au premier passage : score modifié par le 2e passage, prouvé ; double POST restart), 3 low (restoring posé après la réécriture de run.json, epoch 0 transitoire, faux positif content_changed) ; reviewer Opus lancé (coordination de derive avec 6.5) · —
- 2026-10-19 02:35 · — · vérification · uv run dans un worktree importe bien le src du worktree (pas celui de main) : suites complètes des piles valides · —
- 2026-10-19 02:37 · 3.5 · fusion · suite complète 1189 passed / 46 skipped, CI branche verte sur 6 jobs, commit de fusion sur main, story done ; 7.3 éligible (7.1, 3.5 done) ; 5.7 attend 5.6 · 3f00039
- 2026-10-19 02:45 · 6.5 · review · rebase sans conflit, M1 (toutes les cellules CSV neutralisées, tests par colonne), M2 (RESTART_KIND partagé, remise exclue de l'état), M3 (ALLOW_DOWNLOADS vérifié dans pywebview 6.2.1 et protégé), L6, L7 corrigés ; L4, L5 écartés, L8 reporté ; 1158 passed, CI branche verte · 53812e8
- 2026-10-19 02:45 · 6.5 · fusion · kind de remise réaligné par l'orchestrateur sur scenario_reset (4.4 l'émet ; le reviewer avait lu un état antérieur de 4.4), tests ciblés 102 passed, rebase sur main sans conflit, suite complète et CI en cours ; reviewer de 4.4 prévenu (RESTART_KIND unique, derive fusionné) · 8af0c93
- 2026-10-19 02:56 · 6.2 · dev · fini, 1108 passed / 42 skipped, CI verte ; scénarios add-commit, push-pull, branche, pr-merge (.A, deux parcours, indices à 3 paliers, quiz), type d'étape pr_state, 8 empreintes ; setup identique entre parcours ; libellés « vue Distant » à réaligner sur 3.3 ; relecture pédagogique pour Anaël · 48fd7a7
- 2026-10-19 02:56 · 6.2 · second-avis · lancé · —
- 2026-10-19 02:56 · 2.10 · dev · lancé (dev-story Sonnet ; 2.7, 2.8, 3.3 done ; ouvre 9.4) ; 5.4, 7.3, 6.4 éligibles en attente de créneau · —
- 2026-10-19 03:04 · 6.5 · fusion · suite complète 1265 passed / 46 skipped, CI branche en cours · —
- 2026-10-19 03:04 · 6.2 · second-avis · 1 high lu sur une base sans 3.3 (vue Distant vide ; levé par le rebase), 2 medium (libellé « vue Distant » ≠ « Distant + PR », tutoiement du collègue), 5 low (« signé » faux, réévaluation d'étape, pr_state silencieux, -u non exigé, restauration add-commit non testée) ; reviewer Opus lancé · —
- 2026-10-19 03:04 · 2.9 · review · rebase sans conflit, M1 (écriture pendant la suspension retenue et proposée), M2 (mesure stricte des 2 s ; cause : mtime à la seconde en polling), L4-L7 corrigés ; L3 reporté, L8 écarté ; 1151 passed, CI branche verte · 58a1fa7
- 2026-10-19 03:04 · — · décision pour Anaël · 2.9 : message « fichier supprimé sur le disque » ? effacement de la notice après enregistrement ou commande ? · —
- 2026-10-19 03:04 · 2.9 · fusion · empilée sur 6.5 sans conflit, branche poussée, suite complète du sommet et CI en cours · —
- 2026-10-19 03:05 · 6.5 · fusion · CI branche verte sur 6 jobs, commit de fusion sur main, story done · c089c65

## Reprise (arrêt propre du 2026-10-18, fin de soirée)

État au moment de l'arrêt : 25 stories `done` (Epic 1 ; 2.1 à 2.7 et 2.11 ; 3.1, 3.2 ; 4.1, 4.2, 4.3 ; 6.6 ; 7.1 ; 8.2 ; 9.1, 9.2). Aucun agent en cours. `main` à jour et poussé (63d065e).

Branche à reprendre en premier (worktree existant sous `.claude/worktrees/`) :

| Story | Branche · SHA · worktree | Étape suivante |
|---|---|---|
| 4.5 | `story/4-5-quiz-retablir` · 9c3119a · agent-af869e12ac1ac0300 | `reviewer` Opus avec la liste du second avis (journal, 2 high prouvés) ; rebase sur main (contient 4.2 : brancher le premier essai sur ProgressStore, API dans la spec 4.2 ; conflits probables operations.py, steps.py, store.js, workspace.js) |

Éligibles à lancer ensuite (dépendances done) : 4.4 (crée l'intention `restart` déjà postée par 4.5 ; efface restore_failed, quiz, quiz_first), 3.3, 3.4, 3.5, 7.2, 7.4 ★, 2.8, 4.6, 4.7. Attention aux modules partagés : 3.3/3.4/3.5/7.4 touchent `github_sim` (une à la fois ou presque) ; 7.2 et 2.8 le terminal/wsfs ; 4.4, 4.6, 4.7 le moteur d'étapes (attendre la revue de 4.5 pour 4.4). Puis suivre les vagues.

Méthode qui a bien marché ce soir pour tenir le rythme : empiler les branches revues (rebase de chacune sur la précédente), pousser toutes les branches pour leurs CI en parallèle, suite complète locale une seule fois sur le sommet de pile, puis fusions en série.

Points ouverts pour Anaël (rien ne bloque) : httpx dans la table Stack ; `diagnostic_seen` dans AD-5 ; `dismiss_stale_reviews` (défaut false) ; 9.2 disponibilité des outils de la carte par sonde réelle (défaut gardé) ; 2.5 garde sur `rm -rf *` à la racine (défaut : accepté) ; tests sur vrai poste des installeurs (1.6, 1.7) ; vérifications Ollama réel (6.6, dont Ctrl+C pendant une réponse lente) ; rendu navigateur (2.3, 9.1, 2.7 tracé des arêtes et troncature, 4.1, 9.2, 2.5).

Suivi : `/agent-cost-kit:avancement-run` (plugin 0.6.4 : sans détail par story quand il y a des epics, barres █░ ; actif après redémarrage de Claude Code).
