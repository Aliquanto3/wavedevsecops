# Addendum au PRD : WaveDevSecOps

Ce fichier rassemble ce qui sert l'architecture et l'UX sans avoir sa place dans le PRD.

## Stack candidate (non décidée)

Stack reprise de WaveStack (`pedagogy-reference.md`) : Python 3.13, `uv`, FastAPI, uvicorn, pydantic, Jinja2, PyYAML ; `ruff` et `pytest` ; licence Apache-2.0. Dépôt de référence : `C:\Users\Utilisateur\Documents\GitHub\agentic-harness-training-demo`. Sa reprise est la question ouverte 5 du PRD.

## Pratiques d'installation reprises de WaveStack

- Commande unique sous PowerShell, sans droits administrateur, plus une voie d'installation depuis un clone ou un zip.
- Page de diagnostic au premier lancement.
- Prise en charge des proxys d'entreprise.

## Choix d'Anaël pendant le PRD (2026-10-18)

- **Terminal :** git plus quelques commandes de fichiers. Options écartées : un shell complet, pour son risque de sortie du bac à sable ; git seul, qui empêche de créer un fichier en ligne de commande.
- **Édition :** dans la vue code, avec en plus un bouton pour ouvrir le fichier dans l'éditeur externe. Il faut donc surveiller les fichiers modifiés hors de l'application.
- **Navigation :** ordre conseillé et accès libre. Chaque scénario doit donc préparer son propre état, sans s'appuyer sur le précédent.
- **Indices :** trois paliers (piste, commande partielle, solution), et chaque palier ouvert compte.

## Recherche web du 2026-10-18 (synthèse)

### Comparables
- Learn Git Branching : git simulé ; `reset` (début du niveau) et `undo` (pas précédent), sans remboursement du compteur de coups.
- Oh My Git! : application de bureau Godot, vrai git, script de mise en place déclaratif par niveau, victoire vérifiée par des commandes git. C'est le plus proche de WaveDevSecOps.
- Git-it : Electron, vérification par de vrais appels git ; fragilisé par un service GitHub tiers.
- Githug : terminal, `hint` / `reset` / `levels`.
- GitHub Skills : en ligne, avec un compte.

### Installation
- uv s'installe sans droits administrateur. Derrière un proxy qui intercepte TLS, il faut `UV_SYSTEM_CERTS=true` (ancien `--native-tls`).
- Pare-feu Windows : écouter sur `127.0.0.1` et non sur `0.0.0.0` (retours d'utilisateurs, sans source officielle).
- Ajouter localhost à `NO_PROXY`.
- WebView2 n'est utile que si l'on choisit pywebview ou Tauri.

### Pédagogie
- Auto-explication : g = 0,55 (Bisra et al., 2018). Les explications à menu fonctionnent (Aleven et Koedinger, 2002) mais se contournent en essayant chaque option.
- Désigner l'élément (commit, branche, ligne) est une production vérifiable contre le dépôt réel.
- Indices : dans le Cognitive Tutor, l'abus d'aide atteint 14 à 36 % des actions (clics jusqu'au bottom-out). Un bottom-out lu lentement fonctionne comme un exemple résolu (Shih et al., 2008). Une pénalité de score pousse à ne plus demander d'aide (help avoidance).
- Mesures utiles par indice : palier atteint, temps avant la demande, temps de lecture.

### Télémétrie
- Go est passé de l'opt-out à l'opt-in sous la pression de la communauté (2023). Audacity et GitLab ont reculé.
- ePrivacy art. 5(3) (lignes directrices EDPB 2/2023) couvre tout accès au terminal.
- Un score rattaché à un salarié est une donnée personnelle (base légale de l'employeur, CSE).
- Toute sortie réseau contredit la promesse « hors ligne ».

### Export de la fiche
- OSCAL est peu adopté hors du secteur public américain.
- Interprétation, sans source unique : un RSSI français tient sa déclaration d'applicabilité et ses tableaux de correspondance dans un tableur, et y annexe des PDF. Markdown ne lui apporte rien.
- Citer les numéros et intitulés courts des contrôles ISO, sans reproduire leur texte, qui est protégé.

### Correspondances réglementaires
S = explicite dans le texte, I = interprétation. « IR » désigne le règlement d'exécution NIS2 2024/2690 ; « RTS » le règlement délégué DORA 2024/1774.

| Barrière | ISO 27001:2022 Ann. A | NIS2 art. 21§2 | DORA | CRA Ann. I |
|---|---|---|---|---|
| gitleaks | 5.17, 8.28, 8.24 (I) | (e), (h) (I) | RTS 6-7, 16(3) (I) | P.I 2(d), 2(e) (I) |
| bandit (SAST) | 8.25, 8.28, 8.29 (S) | (e) ; IR 6.2, 6.5 (S) | RTS 16(3) (S) | P.I 2(a) ; P.II 3 (S) |
| pip-audit + SBOM | 8.8, 5.21 (S) | (d), (e) ; IR 6.6, 6.10 (S) | RTS 10(2)(d)(i), 16(8) (S) | P.II 1 SBOM (S) ; P.I 2(a), P.II 2 (S) |
| Quality gate | 8.29 (I) | (e), (f) ; IR 6.5 (I) | RTS 16 (I) | P.II 3 (I) |
| Revue obligatoire | 8.28, 8.32, 5.3 (S/I) | (e) ; IR 6.4 (I) | RTS 16(3) (S) | P.II 3 (I) |
| Protection de branche | 8.4, 5.15, 8.2, 8.32 (S) | (i) ; IR 11.2-11.3 (I) | art. 9(4)(c) ; RTS 21 (I) | P.I 2(f) (I) |
| Tag SemVer | 8.32, 8.9 (I) | IR 6.3-6.4 (I) | art. 9(4)(e) ; RTS 17 (I) | P.II 2 (I) |
| Approbation de livraison | 8.32, 5.3, 8.31 (S) | IR 6.4 (I) | RTS 17(1)(b) (S) | — |
| Rollback | 8.32, 8.13, 5.30 (I) | (c) ; IR 6.4 (I) | RTS 17(1)(e) repli (S) | P.I 2(h) (I) |

**Points de vigilance**
- Le règlement d'exécution NIS2 ne vise que certaines entités ; pour les autres, il sert de bonne pratique.
- Le CRA s'applique au 11/12/2027 (signalement dès le 11/09/2026) et vise les produits des clients.
- Aucun texte n'impose de seuil de couverture.
- Les numéros ISO n'ont pas été vérifiés en ligne (norme payante) : à relire avant v1.0.
