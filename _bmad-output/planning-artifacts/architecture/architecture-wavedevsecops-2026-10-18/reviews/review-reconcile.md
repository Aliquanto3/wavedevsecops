# Revue de réconciliation : ARCHITECTURE-SPINE contre PRD, addendum et EXPERIENCE

Date : 2026-10-18. Périmètre : exigences, contraintes et exigences discrètes (ton, ordre, données d'accessibilité fournies par le serveur, hors ligne, déterminisme, français) que la spine a omises, contredites ou laissées sans propriétaire. Les décisions du PRD et de l'UX ne sont pas rediscutées. Les éléments purement visuels sont ignorés.

## Verdict

La spine règle les sept questions du PRD §10 et les deux points UX, sans contradiction frontale avec les entrées. Elle laisse toutefois sans propriétaire plusieurs données que l'UX exige du serveur : annotations de projection, désignation et indices, liens de sortie d'outil, confinement des routes de fichiers. Elle est utilisable après correction de 3 constats « high » (F-1 à F-3).

## 1. Questions du PRD §10 et points UX

| Point | Statut | Où |
|---|---|---|
| Q1 installer git, gitleaks et les autres outils sans admin | Réglée. PortableGit sous Windows, pixi/conda-forge ailleurs, gitleaks vérifié par `checksums.txt`, le reste via uv. MinGit écarté avec raison. | AD-15 |
| Q2 instantanés et restauration | Réglée. Copie, empreinte canonique, trois essais Windows, échec = `restore_failed`. | AD-6 |
| Q3 pip-audit hors ligne | Réglée. Vrai outil, point OSV local figé. | AD-11 |
| Q4 exécution du pipeline simulé | Réglée. | AD-10 |
| Q5 stack | Réglée. Table Stack, Apache-2.0. Python 3.14 au lieu de 3.13 : choix assumé. | Stack |
| Q6 couche LLM | Réglée. API compatible OpenAI, Ollama par défaut, `llmrun` seul à sortir. | AD-13 |
| Q7 commandes de fichiers et confinement | Réglée sur le terminal (voir F-4 pour les autres routes). | AD-4 |
| UX : git en locale française / MinGit | Réglé. Contexte apprenant en `fr_FR`, contexte interne en `C`, langue sondée au diagnostic, MinGit écarté. Voir F-12 pour le cas Linux sans locale générée. | AD-3, AD-15, AD-16 |
| UX : versions minimales dans le diagnostic | Réglé. Table AD-16, source unique `tools.toml`. Voir F-6 pour les textes « Que faire ? ». | AD-16 |

Les reports (station 4, invocation pip-audit, délais, approbations, « Reprendre ») sont cohérents avec PRD §10 (second bloc) et UX questions 6 et 9.

## 2. Constats

### F-1 (high) : annotations de projection exigées par l'UX sans propriétaire
**Où :** AD-2, AD-17 (`state_projected{views}`), AD-8.
**Source :** UX Component Patterns (`new-mark`, « Rétabli », `graph-*`), Accessibility Floor (annonces, graphe, correspondances), NFR-13, FR-5.
**Constat :** la spine dit que le front « ne calcule ni correspondance ni score » et que tout texte vient du serveur, mais elle ne définit pas ce que le serveur doit fournir pour :
- `new-mark` : éléments nouveaux depuis la dernière commande (et retrait à la suivante), éléments « Rétabli » après un rétablissement. Il faut un delta entre deux `RepoState`.
- La phrase de la région `role="status"` (« Commande terminée. Vues mises à jour : 1 commit et 1 branche nouveaux. Étape 3 validée. »), qui dépend de ce delta et du verdict.
- Le nom accessible de chaque nœud du graphe (« Commit a1b2c3d, Add config, par l'agent, parent 9f8e7d6, pointé par la branche locale feature et HEAD, nouveau »). Il exige l'auteur-rôle (agent, collègue, apprenant), les parents, les refs pointeuses et l'état (perdu, sélectionné, attendu, votre choix).
- Le résumé des correspondances (« 3 éléments liés : ref origin/main, PR n°2, fichier config.py »). AD-2 interdit au front de calculer les correspondances, donc le serveur doit émettre la table de liens `element_id` → `element_id` de l'UX (commit↔diff, check↔lignes `pipeline-tabs`, barrière↔hook/check/terme, etc.).
- L'explication attachée à chaque instance d'élément (NFR-13) : `explanations.yaml` est indexé par type, mais rien ne dit qui associe type, instance et texte, ni comment le front l'obtient sans inventer de phrase.
- Les raisons de `merge-blocked` : « une par ligne, chacune liée à l'élément en cause ». AD-8 calcule la raison, pas son lien.
**Correction suggérée :** ajouter à AD-2 un contrat de projection : chaque élément porte `{element_id, type, actor, flags[new|restored|lost|selected_expected], label_text, a11y_name_text, explain_key}` ; la projection porte `links` (table de correspondances), `delta_summary_text` et `announce_text`. Faire porter les raisons de blocage par `{text, element_id}`. Ajouter dans AD-17 le contenu de `state_projected`.

### F-2 (high) : désignation, réponse unique, résolution de SHA et indices n'ont ni intention, ni événement, ni état
**Où :** AD-1 (liste des opérations), AD-17 (`kind`), AD-7, AD-14, AD-5 (`run.json`).
**Source :** FR-12, FR-13, FR-34 ; UX Désignation et Indices à paliers.
**Constat :**
- Aucune opération typée pour « Valider ma réponse » (un seul essai, correction serveur, réponse RSSI en deux cases réponse + preuve), ni pour la demande d'indice.
- Aucune route ni événement pour la résolution d'un SHA abrégé (au moins 7 caractères, aperçu « `a3f9d21` · Add config · Agent », erreur sans consommer l'essai). Elle doit être une lecture, hors file.
- Aucune route pour `designate-list` (désignables groupés par vue, y compris preuves non commit : sortie d'outil, check, revue, SBOM, tag).
- Pas de `kind` pour le verdict de désignation (« ✓ Votre choix », « ✓ Attendu », « ≡ Accepté aussi ») ni pour le déblocage de la solution (annoncé à l'écran).
- L'état des indices (palier ouvert, verrouillé, condition du déverrouillage, « un essai » = commande tapée ou choix validé, UX Q5) n'a pas de propriétaire. `run.json` ne porte que « étape courante, état du quiz ». « Rouvrir un palier ne compte pas deux fois » doit être appliqué avant l'écriture du fait dans `progress`.
- Les ensembles de bonnes réponses sont exprimés en `commit:<sha40>`. Un auteur ne connaît pas le SHA à l'écriture du YAML, et la réponse peut porter sur un commit créé par l'apprenant. Il manque un mécanisme d'alias (les ops de setup nomment un SHA, le YAML référence l'alias).
**Correction suggérée :** compléter AD-1 (opérations `answer_submit`, `hint_open`) et AD-17 (`answer_verdict`, `hint_state`, `hint_unlocked`) ; AD-7 : alias symboliques nommés par les ops de setup, résolus en `element_id` à l'exécution ; `run.json` : état des indices et de la réponse en cours ; lectures `GET /api/resolve-sha` et `GET /api/designables`.

### F-3 (high) : liens de sortie d'outil et langue de la sortie
**Où :** AD-3, AD-10, AD-9, AD-17 (`terminal_output`).
**Source :** UX Correspondances (« seuls les SHA, refs, chemins et blocs de sortie d'outil qui existent dans le bac à sable sont liables »), `tool-output` (fichier:ligne vers Code), State Patterns (commit refusé par le hook, lint ou test en échec), Accessibility Floor (sortie en anglais portant `lang="en"`).
**Constat :**
- AD-10 produit des constats structurés pour le pipeline seulement. Les exécutions locales de la station 1 (hook gitleaks, `ruff`, `pytest` tapés dans le terminal) n'ont pas de constats, donc pas de lien fichier:ligne vers Code ni de lien dans le panneau (« avec un lien vers la ligne »).
- `terminal_output{stream, text}` ne porte ni segments liables (SHA, refs, chemins, blocs d'outil) ni la langue de la sortie. AD-3 interdit d'analyser la sortie pour l'état, mais rien n'autorise ni n'organise l'analyse pour le lien. Sans règle, chaque story le fera à sa façon.
- Le front ne peut pas décider seul si un SHA du terminal « existe dans le bac à sable ».
**Correction suggérée :** AD-10 : étendre aux exécutions locales la sortie machine (gitleaks `--report-format json`, `ruff --output-format json`, junit pour pytest) lancée en second, jamais par analyse du texte. AD-17 : `terminal_output` porte `lang` et `spans[{start, end, element_id}]` calculés par le serveur contre le `RepoState`, uniquement pour affichage.

### F-4 (medium) : le confinement ne couvre que le terminal
**Où :** AD-4, AD-5, AD-13 (règle « seuls gitio et toolrun lancent des sous-processus »).
**Source :** FR-2 (« aucune commande acceptée ne lit ni n'écrit hors du bac à sable »), FR-3, UX `code-editor`, `external-change-notice`.
**Constat :**
- Les routes de lecture de fichier, d'enregistrement depuis la vue Code et d'« Ouvrir dans mon éditeur » ne sont régies par aucun invariant de chemin (`resolve()` sous la racine, hors `.git/`). AD-5 liste les propriétaires de `repo/` sans les enregistrements de la vue Code.
- L'ouverture dans l'éditeur externe (et `webbrowser` pour le lancement) lance un processus, ce qui entre en conflit avec la règle des sous-processus.
- Le cas « Le fichier a changé sur le disque » (éditeur non enregistré, « Garder ma version » / « Recharger ») exige une détection de concurrence (empreinte de base envoyée avec l'enregistrement). L'opération « enregistrement de fichier » ne la prévoit pas.
**Correction suggérée :** AD-4 devient « résolution de chemin » partagée par le terminal et les routes de fichiers ; AD-5 ajoute le propriétaire « routes de fichiers » ; exception explicite pour l'ouverture externe (module `opener` listé) ; l'enregistrement porte `base_hash`, refusé en 409 avec `reason_text` si le disque a changé.

### F-5 (medium) : environnement Python d'exercice absent de la disposition
**Où :** AD-5, AD-12, AD-13, AD-9.
**Source :** FR-21 (ruff et pytest lancés par l'apprenant), FR-17, NFR-1.
**Constat :** `ci/` crée un environnement par run, mais la station 1 lance `pytest` et `ruff` dans le terminal sur `repo/`, et `llmrun` exécute le code d'exercice « dans l'environnement d'exercice ». Aucun dossier de la disposition ne porte cet environnement, ni la règle de sa création hors ligne (et de son exclusion des instantanés et de l'empreinte). `pytest` du groupe `chain` ne voit pas forcément les dépendances du dépôt d'exercice.
**Correction suggérée :** ajouter `venv/` (jetable, hors instantanés) à l'espace de travail, créé par `uv sync --offline` au setup ou à la première utilisation, propriétaire `toolrun`.

### F-6 (medium) : diagnostic, proxy et lancement : textes et champs sans home
**Où :** AD-16, AD-15, `tools.toml`, NFR-12 (carte des capacités).
**Source :** FR-19, UX Diagnostic, Flow 3, Voice and Tone.
**Constat :**
- `tools.toml` n'a pas de champ pour la marche à suivre en français par outil (« Que faire ? », dépliable « installation sans droits administrateur ») ni pour le nom des scénarios touchés (calculé, mais à projeter nominativement).
- La section Proxy (proxy détecté avec valeur en partie masquée, `NO_PROXY` contient `127.0.0.1` et `localhost`, état de `UV_SYSTEM_CERTS`) n'a pas de règle, alors que le module `diagnostic` porte un nœud « proxy ». Le masquage doit aussi s'appliquer aux logs (`app.log`) : un proxy peut contenir des identifiants.
- Rien sur l'écriture du diagnostic dans la console de lancement, ni sur le comportement « port occupé » (autre port, adresse affichée, rappel `NO_PROXY`, proposition de la fenêtre pywebview, Flow 3). NFR-12 est réduit à une ligne.
- Message d'échec de l'installeur en français avec les variables à régler si proxy détecté (Flow 3, étape 1) : seul le cas de la somme de contrôle est dit en français (AD-15).
**Correction suggérée :** `tools.toml` : champs `fix_text`, `fix_steps_text`. AD-16 : règle proxy (détection, masquage des identifiants dans l'affichage et les logs). AD-15 : messages de l'installeur en français. Ajouter un paragraphe « lancement » à la carte des capacités (port, console, repli).

### F-7 (medium) : faits de suivi manquants pour le catalogue, la fiche et « Reprendre »
**Où :** AD-14, AD-5 (`run.json`).
**Source :** UX Catalogue (état « À faire / En cours / Terminé », « Étape 3 sur 6 », « Reprendre » sur le dernier scénario ouvert), Exports (« Preuve pas encore vue : scénario <nom> »), Vocabulaire (« La voir jouer »).
**Constat :** AD-14 n'enregistre pas « barrière ou preuve vue » (nécessaire à la fiche et au vocabulaire), ni « dernier scénario et mode ouverts ». L'état « En cours » avec le rang d'étape doit venir de `progress` (le catalogue ne peut pas lire chaque `run.json`). Les remises à zéro visibles au bilan (UX Q7) sont couvertes par les faits.
**Correction suggérée :** ajouter les faits `barrier_proof_seen{barrier_id, scenario_id, element_id}` et `scenario_opened{scenario_id, mode}` ; `progress` projette état et rang d'étape vers le catalogue.

### F-8 (medium) : reprise après arrêt brutal, nettoyage des instantanés, budgets de durée
**Où :** AD-6, AD-17 (dernière ligne), AD-1.
**Source :** NFR-7, FR-15 (« sans laisser l'apprenant sur un état faux »), UX State Patterns (« Préparation du bac à sable… 2 s », « Rétablissement… 1 s », « Application arrêtée »), NFR-6.
**Constat :**
- Un arrêt pendant `quiz_altered`, `restoring` ou `setup` laisse un état faux ou partiel. La spine renvoie à `run.json` sans dire que le moteur doit, au démarrage, détecter ces états et proposer « Recommencer » (ou restaurer).
- Les instantanés « avant chaque choix de quiz » s'accumulent sans règle de purge.
- Aucun budget de durée pour le setup, la restauration et un run de pipeline (qui crée un environnement et lance six outils à chaque push), alors que NFR-6 et les textes UX supposent des durées de l'ordre de la seconde.
**Correction suggérée :** AD-6 : au démarrage, un état `restoring`/`setup`/`quiz_altered` résiduel déclenche la restauration de l'instantané 0 ; garder seulement l'instantané 0 et le dernier. AD-10 et AD-6 : budgets mesurés en CI (setup, restauration, run complet) avec seuil d'alerte.

### F-9 (medium) : installation par jalon et budget de 10 minutes
**Où :** AD-15, AD-12.
**Source :** FR-18 (v0.1 : git et application en moins de 10 min ; v1.0 : tous les outils), SM-2, SM-5, UX Diagnostic (« Outils requis (v0.1) » et « (v0.2+) »).
**Constat :** l'installateur provisionne tout d'un bloc, y compris le préchargement du cache uv de « chaque version de paquet qu'un état de scénario peut demander ». Rien ne le lie au champ `jalon` de `tools.toml`, ni à la mesure de 10 minutes de SM-2 en v0.1.
**Correction suggérée :** AD-15 : l'installateur ne provisionne que les outils dont `jalon` ≤ jalon livré ; le préchargement du cache est mesuré dans le budget. Le test de CI chronomètre l'installation sur les trois systèmes.

### F-10 (medium) : ton et contenus : règles de la UX non portées par la spine
**Où :** Consistency Conventions (Langue, Textes affichés), AD-8, AD-4, AD-18.
**Source :** UX Voice and Tone.
**Constat :** la convention porte le français et le vouvoiement, mais pas : « pas de point d'exclamation, pas d'emoji », « un message nomme qui décide (git, le hook, le pipeline simulé, le GitHub simulé, WaveDevSecOps) », « un échec n'est jamais une faute de l'apprenant », gabarit unique du score avec accord (« 0 indice », « 1 indice », « 2 indices »). Le refus de push sur `main` doit afficher la sortie réelle (stderr du hook `pre-receive`) puis un message de l'application (« Refusé par la protection de `main` : tout passe par une PR. ») : AD-8 ne prévoit que la sortie du hook. Le message de refus de tag non SemVer est reporté avec la station 4, ce qui est acceptable.
**Correction suggérée :** ajouter un champ `decider` aux payloads `_text` d'erreur ou de refus ; un lint de contenu en CI (AD-18) sur les YAML et gabarits (ponctuation, emoji, tutoiement) ; rendre le gabarit du score un seul helper de `progress` ; AD-8/AD-4 : `terminal-app-message` après le refus du hook.

### F-11 (low) : Ctrl+C et interruption hors de la file
**Où :** AD-1, AD-4.
**Constat :** « Ctrl+C termine l'arbre de processus de la commande en cours », mais l'opération courante occupe la file ; une interruption ne peut pas passer par la file. Il faut une intention hors file explicitement prévue. Même remarque pour l'annulation d'un run de pipeline (AD-10) pendant `restoring`.
**Correction suggérée :** `POST /api/interrupt` hors file, qui cible l'opération en cours.

### F-12 (low) : locale française sur Linux et macOS
**Où :** AD-3, AD-15.
**Constat :** `LANG=fr_FR.UTF-8` n'a d'effet sous Linux que si la locale est générée sur le poste, même avec git de conda-forge ; la spine le traite comme informatif (« jamais bloquant ») : c'est cohérent avec UX. Il faut seulement que le texte du diagnostic dise la cause probable (locale absente ou traductions absentes) et que `terminal_output` porte `lang` (voir F-3).

### F-13 (low) : déterminisme et sorties verbatim
**Où :** AD-8, AD-10, AD-6, AD-18.
**Source :** FR-12, NFR-3, flow 5 (dépôt où les barrières ont déjà joué).
**Constat :**
- La date du commit de merge du `github_sim` n'est pas fixée (seuls message et identité le sont), donc son SHA varie.
- La sortie verbatim d'un outil contient des chemins de clone (`ci/<pr>-<sha>/…`), des durées et des versions. Un état de départ de l'entretien RSSI qui contient des checks déjà joués ne sera pas identique d'une machine à l'autre. Il faut décider si ce setup exécute le vrai pipeline (non déterministe) ou injecte des résultats pré-enregistrés (ce qui touche SM-C2).
- L'op de setup « injecter des checks, approbations, tag » n'existe pas dans la liste d'AD-7 (`open_pr`, `set_protection`…).
**Correction suggérée :** fixer la date du merge ; normaliser les chemins (clone sous un chemin court fixe, ou remplacement documenté) ; décider et documenter le mode de l'entretien RSSI dans AD-7.

### F-14 (low) : correspondance réglementaire : granularité et vérification
**Où :** AD-14 (`barriers.yaml`).
**Source :** FR-35, addendum (tableau S/I, « numéros ISO non vérifiés »).
**Constat :** la mention « explicite / interprétation » est portée dans l'addendum par référence de contrôle, parfois mixte (« S/I »). `barriers.yaml` n'indique pas qu'il la porte par contrôle, ni l'intitulé court exigé, ni le rappel de relire les numéros ISO avant v1.0. Les neuf barrières de l'addendum (dont rollback, tag SemVer, approbation de livraison) sont à garder en lignes même avant la station 4 (« Preuve pas encore vue »).
**Correction suggérée :** schéma de `barriers.yaml` : `controls[{ref, short_title, mention}]` par référentiel ; ajouter une tâche de vérification avant v1.0.

### F-15 (low) : détails mineurs
- **README (NFR-9)** : « le README l'énonce explicitement » n'est porté par aucune règle. Ajouter à AD-13 ou AD-18 un contrôle de présence de l'énoncé.
- **Carte de la chaîne (FR-32)** : le contenu de la carte (stations, nœuds de barrière, arêtes vers checks, hooks, termes, frontière CI/CD) n'a pas de fichier propriétaire. `barriers.yaml` pourrait le porter.
- **Dépôt origin et hooks** : AD-3 impose `core.hooksPath` par `GIT_CONFIG_COUNT`, qui prime sur la config du dépôt. L'environnement est hérité par le `receive-pack` local lancé par `push`, donc `origin.git` risque de chercher son `pre-receive` dans le dossier de `repo/`, malgré « un dossier par dépôt » d'AD-9. À vérifier par un test sur les trois systèmes.
- **Éditeur** : AD-3 pose `core.editor` et `sequence.editor` ; `GIT_EDITOR` et `GIT_SEQUENCE_EDITOR` de l'environnement de l'apprenant les priment et devraient aussi être posés ou retirés.
- **Terminal** : la liste blanche ne contient ni `rebase --continue/--abort` explicitement ni `merge --abort`, nécessaires aux scénarios « rebase laissé en conflit » et « conflit ». Les options autorisées par sous-commande devraient être listées dans le fichier de données unique d'AD-4.

## 3. Synthèse

| Sévérité | Constats |
|---|---|
| high | F-1, F-2, F-3 |
| medium | F-4, F-5, F-6, F-7, F-8, F-9, F-10 |
| low | F-11, F-12, F-13, F-14, F-15 |

Rien n'est classé « critical » : aucune exigence du PRD n'est contredite, et les trois « high » se corrigent par ajout de contrats dans AD-2, AD-1/AD-17 et AD-10 sans changer le paradigme.
