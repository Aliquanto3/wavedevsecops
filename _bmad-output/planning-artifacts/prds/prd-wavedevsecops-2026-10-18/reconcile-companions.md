# Réconciliation des compagnons de spec avec le PRD

Sources : scenarios.md, milestones.md, success-metrics.md, risks.md, glossary.md, pedagogy-reference.md. Cibles : prd.md, addendum.md. Décisions postérieures : .memlog.md (elles priment). Statuts : ok / affaibli / absent / contradictoire. Aucune contradiction non justifiée n'a été trouvée.

## 1. scenarios.md

| Élément | Localisation PRD | Statut |
|---|---|---|
| Scénarios YAML déclaratifs, types d'étape extensibles | FR-14, NFR-10 | ok |
| Chaque étape porte une explication écrite | FR-11 (mode A), FR-12, FR-24 | ok |
| Deux parcours, même progression, seul le code d'exercice change | FR-16 | ok |
| 1 add/commit : A ; B `.env` committé + annonce des barrières | FR-9, FR-11, FR-12 | ok |
| 2 push/pull : A avec commit de collègue ; B `push --force` écrasant un collègue | FR-7, FR-9, FR-12 | ok |
| 3 branche (A) | FR-9, FR-11, UJ-1 | ok |
| 4 PR/merge via GitHub simulé (A) | FR-6, FR-9 | ok |
| 5 conflit (A) | FR-9, UJ-2 | ok |
| 6 stash (A) ; B stash oublié | FR-9, FR-12 | ok |
| 7 rebase (A) ; B rebase laissé en conflit | FR-9, FR-12 | ok |
| 8 récupération reflog/reset (A) | FR-9 (« récupération »), UJ-2 ; reflog/reset non nommés en FR | affaibli (mineur) |
| « Mode A : oui » pour les 8 thèmes | FR-11 générique, pas de tableau thème x mode | affaibli (mineur) |
| Cases B vides non exigées | implicite (4 scénarios B listés en FR-12) | ok |
| Agent B scénarisé, déterministe, sans leçon sur les agents | FR-12 (hors périmètre), NFR-3 | ok |
| Quiz : mauvaise commande exécutée, expliquée, annulée | FR-15, glossaire PRD « Quiz » | ok |
| Code LLM : appel simple, prompt système, outils, boucle ; exécution facultative | FR-16, FR-17 | ok |
| St.1 ruff, pytest : défaut de lint, test cassé | FR-21 | ok |
| St.1 hook gitleaks : secret dans un commit | FR-21 | ok |
| St.2 checks / revue obligatoire / protection de `main` : check en échec, PR sans revue, push direct sur `main` | FR-22 | ok |
| St.3 bandit : code vulnérable | FR-24 | ok |
| St.3 pip-audit + SBOM : dépendance vulnérable | FR-25 | ok |
| St.3 quality gate : couverture sous le seuil | FR-26 | ok |
| St.3 LLM gitleaks : clé d'API en dur | FR-28 | ok |
| St.3 LLM bandit + deux approbations : outil trop puissant | FR-28, UJ-3 | ok |
| St.3 LLM test de config : config non locale par défaut ou endpoint hors liste | FR-28 | ok |
| St.3 LLM revue humaine : injection de prompt seulement nommée | FR-28 | ok |
| St.4 approbation, rollback : promotion sans approbation, version défaillante en prod simulée | FR-30 ; FR-31 | affaibli : le défaut « version défaillante en prod simulée » qui déclenche le rollback n'est pas écrit |
| Station 3 : scénarios dans les deux parcours | FR-27 | ok |
| Entretien RSSI : quiz, chaque réponse désigne une preuve | FR-34, UJ-4 | ok |
| Fiche barrière → risque → preuve, ISO 27001 / NIS2 / DORA / CRA | FR-35, addendum | ok |

## 2. milestones.md

| Élément | Localisation PRD | Statut |
|---|---|---|
| Un seul produit, release SemVer par jalon (manifeste, tag annoté, release GitHub avec notes) | §1, §6, NFR-11 | ok |
| Présentation officielle à `v1.0.0` | §1 | ok |
| v0.1 (CAP-1 à 9) | §7 (FR-1 à FR-20b), NFR-10 | ok |
| v0.2 (CAP-10 à 14, 16, 17) | §7 (FR-21 à 28, 32, 33) | ok |
| v0.3 (CAP-15) | §7, FR-29 à FR-31 | ok |
| v1.0 : lot de finition, installation hors ligne de tous les outils, entretien RSSI et fiche s'ils ne sont pas livrés, présentation aux collègues et ateliers (CAP-8, 18, 19) | §7, §10 | ok (« ateliers » repris en §2.2 seulement) |
| Après v0.1 : test d'une heure avec 2 collègues sinon Anaël ; seul moyen de valider le graphe | §7 (note), §8 | ok |

## 3. success-metrics.md

| Critère | Localisation PRD | Statut |
|---|---|---|
| Collègues si disponibles, sinon Anaël | §8 chapeau | ok |
| v0.1 Anaël sans indice, quiz ≥ 80 % du premier coup | SM-1 | ok |
| v0.1 Installation seuls, sans admin, < 10 min, chronomètre | SM-2 | ok |
| v0.1 Socle en 1 h | SM-3 | ok |
| v0.1 Explication du mode B | SM-4 (précisé par le memlog) | ok |
| v1.0 Installation complète < 10 min, réseau coupé | SM-5 | ok |
| v1.0 Séances courtes | SM-6, NFR-6 | ok |
| v1.0 Entretien RSSI ≥ 80 %, preuve, fiche | SM-7 | ok |
| v1.0 Anaël, tous scénarios des deux parcours sans indice | SM-8 | ok |

## 4. risks.md

| Risque et parade | Localisation PRD | Statut |
|---|---|---|
| Installation sans admin ; binaires portables, critère < 10 min | §9, §10 q.1, SM-2, SM-5 | ok (parade dispersée) |
| pip-audit en ligne ; instantané ou résultat simulé | §9, §10 q.3, FR-25, SM-C2 | ok |
| Restauration du bac à sable ; snapshot, état identique | §9, §10 q.2, FR-15 | ok |
| Développement « big bang » ; releases 0.x, test après v0.1 | NFR-11, §7 ; absent de la liste §9 | affaibli : risque non nommé en §9 |
| Vue du graphe validée par son seul auteur ; test collègues sinon Anaël | §9, §7, §8 | ok |
| Code LLM en décor devenu cible ; barrières CAP-14, exécution facultative | §9, FR-28, FR-17 | ok |
| Agent B trop propre ; erreurs réalistes | §9, FR-12, SM-C1 | ok |
| Parades en général | §9 énumère les risques sans leurs parades | affaibli |

## 5. glossary.md

| Terme | Localisation PRD | Statut |
|---|---|---|
| Secrets scanning | jamais écrit (gitleaks seul, FR-21, FR-28) | absent |
| SAST | FR-24, §2.1 | ok |
| SCA / SBOM | FR-25 | ok |
| Quality gate | FR-26 | ok |
| Quatre yeux | §2.1 seulement ; aucune FR ne le relie à « revue obligatoire, deux approbations » | affaibli |
| Protection de branche | FR-8, FR-22 | ok |
| Traçabilité (PR, checks, tag, approbation) | jamais écrit | absent |
| DAST seulement nommé | FR-33, §6 | ok |
| Bac à sable, `origin`, GitHub simulé, mode A, mode B, parcours, station, barrière, carte de la chaîne | §3 (« à l'identique », par renvoi), usage cohérent | ok |
| Hors périmètre : Docker, K8s, IaC, observabilité, secrets managers ; MR GitLab après v1.0 | §6, §7 | ok |

Synonymes repérés : « volet distant » (FR-4) pour `origin` ; « dépôt d'exercice » (FR-25, NFR-10) à côté de « bac à sable », sans définition.

## 6. pedagogy-reference.md

| Élément | Localisation PRD | Statut |
|---|---|---|
| Montrer ce qui se passe vraiment, pendant que cela se passe | §1 « vraiment, vue par vue » ; FR-4 | affaibli : « pendant que cela se passe, plutôt qu'après coup » perdu, aucune exigence de synchronisation immédiate |
| Volets synchronisés, sélection qui éclaire les correspondants | §1, FR-4, FR-5 | ok |
| Vue schéma qui situe chaque pièce | FR-32 | ok |
| Programme guidé en scénarios qui préparent l'état et donnent la consigne | FR-9, FR-11 | ok |
| Explication courte en français attachée à chaque élément | §1 (mention), FR-11 (par étape), NFR-8 | affaibli : pas d'exigence « chaque élément » (check, barrière, commit) |
| Échecs = matériau pédagogique, jamais un plantage | §1, NFR-7, FR-11 | ok |
| Install : commande unique PowerShell, sans admin, clone/zip | FR-18, addendum | ok |
| Page de diagnostic au premier lancement | FR-19, addendum | ok |
| Proxys d'entreprise | FR-18, addendum, UJ-2 | ok |
| Stack candidate non décidée | addendum, §10 q.5 | ok |

## Écarts et corrections proposées

1. Principe « montrer pendant que cela se passe » (prd.md §1, FR-4). Ajouter à FR-4 une conséquence testable : chaque commande et chaque enregistrement sont reflétés dans tous les volets pendant l'exécution, avant l'explication ; et dans §1 « pendant que cela se passe, pas après coup ».
2. Explication courte attachée à chaque élément (§1, NFR-8). Ajouter un NFR (ou une conséquence de FR-5) : tout élément affiché (commit, check, barrière, étape de carte, ligne de pipeline) porte une explication courte en français.
3. Termes du glossaire : « Secrets scanning » et « Traçabilité » absents ; « Quatre yeux » non relié. Dans FR-33, lister les 8 termes avec leur barrière (secrets scanning → gitleaks, st. 1 et 3 ; traçabilité → PR, checks, tag, approbation, st. 2 et 4 ; quatre yeux → revue obligatoire et deux approbations, st. 2 et 3).
4. Station 4 (FR-31) : écrire « une version défaillante est servie en prod simulée ; l'apprenant déclenche le rollback, la prod sert la version précédente ».
5. Risques (§9) : ajouter le risque « big bang » (releases 0.x à chaque jalon, test après v0.1) et une parade brève par risque, avec renvoi à FR/SM/§10.
6. Mineurs : nommer `reflog` / `reset` et préciser « les 8 thèmes ont un scénario mode A » en FR-9/FR-11 ; définir « dépôt d'exercice » en §3 et aligner « volet distant » sur `origin` ; recopier les définitions du glossaire en §3 si le PRD doit se lire seul.
