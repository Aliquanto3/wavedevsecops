# PRD Quality Review — WaveDevSecOps

## Overall verdict

Le PRD tient bien : la vision est spécifique, le périmètre par jalon est lisible, et la plupart des FR du socle git (FR-1, 4, 10, 12, 13, 15, 35) ont des conséquences réellement testables. Le risque principal est que les critères de réussite ne prouvent pas la thèse, car ils retombent sur l'auteur dès que les collègues manquent, et ils n'existent pas pour v0.2 et v0.3. Les FR des stations 3 et 4 et plusieurs FR de support sont trop minces pour nourrir des stories sans réinterprétation. Les sept questions d'architecture sont bien ouvertes et aucune ne bloque UX, architecture ou epics.

## Decision-readiness — adequate

Les décisions sont énoncées comme des décisions (terminal git + fichiers, indices sans pénalité, annulation des mauvaises commandes, export HTML + CSV), et les questions ouvertes du §10 sont de vraies questions : aucune n'a sa réponse dans la phrase suivante. Mais les compromis vivent dans `addendum.md` (« Options écartées : un shell complet… ») et non dans le PRD. Aucun `[NOTE FOR PM]` ne marque les vraies tensions, alors qu'il y en a : fiabilité des mesures confiées à l'auteur, taille du périmètre pour un seul auteur, FR-34/35 sans jalon fixe.

Une incohérence entre décision et question ouverte : NFR-12 tranche la forme (« application web servie par un serveur Python géré par `uv` », `127.0.0.1`, repli pywebview), alors que la question 5 demande encore « Stack : reprendre celle de WaveStack ? ». Soit NFR-12 est une contrainte, soit c'est une décision d'architecture.

Les questions 1 à 3 sont des verrous de faisabilité : MinGit et gitleaks sans admin sur trois systèmes, restauration fiable du bac à sable, pip-audit hors ligne. Elles ne bloquent pas l'architecture, qui est là pour les traiter. Mais le PRD ne dit pas ce qu'on accepte si l'une échoue, hors le cas pip-audit (SM-C2).

### Findings
- **medium** NFR-12 tranche ce que la question 5 laisse ouvert (§5 NFR-12, §10 Q5) — NFR-12 impose Python, `uv`, serveur local et navigateur, la Q5 demande si la stack WaveStack est reprise. L'architecte ne sait pas si c'est contraint. *Fix:* classer NFR-12 en contrainte (forme et sécurité d'écoute) et reformuler la Q5 sur les seuls choix de bibliothèques, ou retirer les détails `uv` / pywebview du PRD.
- **medium** Aucun repli pour les verrous de faisabilité (§10 Q1-Q3, §9) — le §9 liste le risque d'installation sans admin et de restauration, mais pas le seuil au-delà duquel on dégrade (ex. un outil non installable sur un système). *Fix:* ajouter, par risque, un critère de repli en une ligne, ou un `[NOTE FOR PM]` renvoyant à `risks.md`.
- **low** Les tensions réelles ne sont pas signalées (tout le PRD) — aucun `[NOTE FOR PM]`. *Fix:* en poser trois ou quatre aux endroits cités dans les autres sections.

## Substance over theater — strong

Pas de théâtre de personas : Camille tire l'installation sans admin et le proxy, Karim tire l'entretien RSSI et l'export, Anaël tire SM-1. Les NFR portent des seuils propres au produit (10 min, 1 h, `127.0.0.1`, CSV UTF-8 avec BOM). La vision ne pourrait pas se transposer à un autre produit. Le §2.2 (non-utilisateurs) fait un vrai travail d'exclusion.

### Findings
- **medium** L'argument de différenciation contredit la recherche du projet (§1 Vision vs `addendum.md` « Comparables ») — la Vision dit que « face à eux [Learn Git Branching, Oh My Git!, GitHub Skills], l'atout est le **vrai** git, hors ligne ». Or l'addendum décrit Oh My Git! comme « application de bureau, vrai git… le plus proche de nous ». Le vrai git hors ligne n'est donc pas distinctif face à lui. Le vrai différenciant est la chaîne DevSecOps et l'entretien RSSI avec preuve. *Fix:* recentrer l'atout sur git réel combiné à la chaîne et à la fiche barrière → risque → preuve, que les comparables n'offrent pas.
- **low** NFR-4 « outils réels et légers » (§5) — « légers » n'est pas mesurable. *Fix:* retirer le mot ou donner un plafond (taille d'installation, mémoire).

## Strategic coherence — adequate

La thèse est claire et suit une montée cohérente : voir le vrai git, comprendre ce que l'agent a fait, nommer les barrières, les défendre devant un RSSI. Le type de MVP (apprentissage / expérience) correspond au découpage par jalon. Les contre-critères SM-C1 à SM-C4 sont un point fort et visent les bons détournements (faciliter les quiz, simuler un outil, raccourcir les explications).

La faiblesse est dans les mesures. Aucune ne vérifie le résultat annoncé dans les JTBD : savoir réparer un dépôt réel après un agent, défendre son code devant un RSSI en situation. SM-1 et SM-8 mesurent la maîtrise de l'auteur, qui a écrit les quiz. SM-7 mesure un quiz de l'auteur. Ce sont des tests de complétion et de timing, pas de transfert.

### Findings
- **high** Les critères « collègues » tombent sur l'auteur (§8 intro, SM-2, SM-3, SM-4, §7 dernier paragraphe) — « vérifiés par deux collègues s'ils sont disponibles, sinon par Anaël ». SM-2 (« deux collègues installent seuls, chronomètre en main ») et SM-4 (compréhension du mode B) n'ont aucun sens validés par l'auteur, qui connaît l'installation et les scénarios. Le test de la thèse devient alors invérifiable en silence. *Fix:* garder la clause de repli mais l'étiqueter, dire quels SM sont alors « non validés » (et non « atteints »), et fixer ce que l'on accepte pour publier v0.1 dans ce cas.
- **medium** Aucun critère pour v0.2 et v0.3 (§8) — les SM sont regroupés « v0.1 » et « v1.0 ». Les stations 1 à 4 ne sont mesurées qu'à v1.0 (SM-5, 6, 8). Une release à v0.2 et v0.3 n'a donc pas de porte de sortie. *Fix:* ajouter un critère par jalon (ex. séance station 3 en 1 h par un collègue) ou dire explicitement que v0.2 et v0.3 sont validées par les scénarios seuls.
- **medium** Pas de mesure du transfert ni de l'usage (§8) — aucune mesure ne dit si l'apprenant sait ensuite réparer un vrai dépôt ou si des collègues et clients utilisent l'outil (ateliers, clients sont pourtant l'arc stratégique du §2.2). *Fix:* ajouter un critère léger et vérifiable : par exemple, un collègue résout un cas non scénarisé, et le nombre d'ateliers tenus avant v1.0.

## Done-ness clarity — adequate

Environ la moitié des FR ont des conséquences testables de très bonne qualité (identité octet pour octet, restauration complète de l'état dans FR-15, conformité à `git log --all`, ordre des paliers). En face, une série de FR s'arrêtent à la description et laisseront l'ingénieur ou le story-writer deviner. Ce sont surtout les stations 3 et 4, qui forment le cœur de la valeur annoncée.

### Findings
- **high** FR de stations 3 et 4 sans conséquence testable (§4.10, §4.11) — FR-24 (« échoue, avec l'explication du défaut »), FR-26 (« échoue quand la couverture passe sous le seuil » sans valeur ni source du seuil, ni comment l'apprenant la voit), FR-29 (« pose un tag SemVer, puis construit la version taguée » : que contient le build, quel résultat vérifier), FR-31 (« la prod simulée sert la version précédente » : comment le constater). Ce sont les barrières centrales du produit. *Fix:* pour chaque FR, donner l'état initial prévu, le résultat observable (check rouge nommé, message, version servie) et la valeur du seuil de couverture.
- **medium** FR sans aucune conséquence (§4.2, §4.3, §4.6, §4.7, §4.12) — FR-5 (« met en évidence ses correspondants »), FR-8 (modèle de PR « prêt pour les stations » : à quoi voit-on que c'est prêt ?), FR-17 (exécution facultative), FR-19 (diagnostic : liste des outils et message pour l'outil manquant, nombre d'outils par jalon). *Fix:* une conséquence par FR, même courte (ex. FR-19 : un outil retiré du PATH produit un message qui nomme l'outil et la commande de correction).
- **medium** Adjectifs ou durées vagues (§4.1 FR-3, §4.4 FR-13, §4.12) — « quelques secondes » (FR-3 et FR-13), « erreurs réalistes » (FR-12, SM-C1), « comportement identique sur les trois systèmes » (FR-2, NFR-5). *Fix:* un plafond chiffré pour FR-3 et FR-13 (ex. 3 s) ; pour « identique », dire que la suite de scénarios passe à l'identique sur les trois systèmes en CI.
- **low** FR-12 et FR-10 « octet pour octet » (§4.4) — l'identité exige des SHA stables (dates et auteurs fixés), ce qui est une contrainte d'architecture à nommer. *Fix:* préciser « SHA et refs identiques » ou dire que les horodatages sont figés par le scénario.

## Scope honesty — adequate

Le §6 fait un vrai travail (git simulé, Jenkins réel, chatbot avant v1.0, un scénario par référentiel), de même que la liste « Après v1.0 seulement » et les « Hors périmètre » au niveau des FR. Les trois `[ASSUMPTION]` en ligne sont tous repris au §11 et l'index ajoute honnêtement les hypothèses confirmées par Anaël.

Le trou est l'absence de ligne de coupe. Un seul auteur doit livrer trois systèmes, six outils installés sans admin, un GitHub simulé, trois syntaxes de pipeline, et des scénarios en double (deux parcours, modes A et B), sans estimation ni ordre de sacrifice si un jalon dérape. Le jalon v1.0 contient un « lot de finition (contenu fixé au découpage en stories) » et deux livrables phare « s'ils ne sont pas encore livrés ».

### Findings
- **medium** FR-34 et FR-35 flottent entre v0.2 et v1.0 (§4.13, §7) — l'entretien RSSI et la fiche sont la conclusion de l'arc (UJ-4, SM-7), mais la date de livraison est « au plus tard v1.0 » et la décision est renvoyée aux stories (§10 dernier paragraphe). Or la fiche couvre des barrières de la station 4 (tag, approbation, rollback, v0.3) : elle ne peut pas être complète avant. Les stories ne peuvent pas ordonner l'epic sans cette réponse. *Fix:* trancher : v1.0, avec une version réduite de la fiche optionnelle en v0.2 pour les barrières des stations 1 à 3.
- **medium** Pas de ligne de coupe pour un auteur seul (§7) — « lot de finition » non défini, aucun ordre de sacrifice. *Fix:* ajouter un `[NOTE FOR PM]` : en cas de retard, ce qui sort en premier (ex. trois écritures de pipeline réduites à deux, station 4 reportée) et ce qui est intouchable (socle git, entretien RSSI).
- **low** Peu d'`[ASSUMPTION]` pour ce volume d'inférences (§11) — par exemple, les barrières LLM de FR-28, le seuil de 80 %, et « une heure par station » viennent de la spec et ne sont pas marqués. Acceptable pour une dérivation de spec, mais à confirmer.

## Downstream usability — adequate

Le PRD est conçu pour alimenter UX, architecture et stories, et la structure s'y prête : IDs FR, UJ, SM, NFR, renvois croisés exacts, UJ avec protagoniste nommé. Mais il dépend d'autres fichiers pour des éléments dont la lecture isolée a besoin.

### Findings
- **high** Le glossaire n'est pas dans le PRD, et un terme est incohérent avec les jalons (§3, §4.13 FR-33, `glossary.md`) — « Le PRD reprend à l'identique le glossaire de la spec » signifie qu'un lecteur du PRD seul n'a pas la définition de *bac à sable*, *`origin`*, *GitHub simulé*, *mode A*, *mode B*, *parcours*, *station*, *barrière*, *carte de la chaîne*, termes pourtant au cœur de chaque FR. De plus, FR-33 (v0.2) exige que « chaque terme de `glossary.md`, sauf DAST, mène à une barrière visible ». Or le terme *Traçabilité* du glossaire est incarné par « PR, checks, tag SemVer, approbation de livraison (stations 2 et 4) » : le tag et l'approbation n'arrivent qu'en v0.3. FR-33 ne peut donc pas être validé à v0.2. *Fix:* recopier en une ligne chaque terme de produit dans le §3 ; limiter FR-33 à v0.2 aux termes dont la barrière existe à ce jalon et reporter *Traçabilité* à v0.3.
- **medium** Dépendances externes pour des contenus essentiels (§0, §8, §4.4) — le protocole de vérification des SM est « dans `success-metrics.md` », le catalogue de scénarios dans `scenarios.md`, les CAP-n dans la spec. Les FR indiquent « CAP-n » au niveau des sections, mais le PRD ne les liste jamais. FR-9 cite l'ordre des scénarios, ce qui suffit, mais FR-12 (« Les erreurs … ont chacune leur scénario ») dépend aussi de `scenarios.md`. *Fix:* soit un tableau CAP-n → FR en annexe, soit retirer les CAP-n du texte ; garder le protocole de mesure SM en une phrase dans le PRD.
- **medium** Aucun UJ pour la station 4 (§2.3) — FR-29 à FR-31 (v0.3) ne sont portés par aucun parcours, alors que les UJ-1 à UJ-4 couvrent le socle, les stations 1 à 3 et l'entretien. L'UX n'a rien à partir pour la promotion et le rollback. *Fix:* ajouter un UJ-5 court (Camille, v0.3) : tag, build, promotion refusée sans approbation, rollback.
- **low** UJ-2 mélange 1 h et plus (§2.3 UJ-2) — « en moins d'une heure » couvre branche, PR, conflit et récupération, mais le scénario B vient ensuite, et SM-3 exclut B. Le temps visé n'est pas clair. *Fix:* écrire « en moins d'une heure pour le socle, puis le scénario B ».

## Shape fit — strong

Outil d'apprentissage open source mené par un seul auteur, en chaîne vers UX, architecture et stories : quatre UJ avec protagoniste nommé, FR avec conséquences testables, SM avec contre-critères. Cette formalisation est justifiée par le public successif (collègues, ateliers, clients), pas du théâtre. Le seul bémol est la taille (35 FR, 12 NFR, 8 SM + 4 contre-critères) pour un seul auteur, traitée dans la section périmètre.

## Mechanical notes

- **ID continuity** : FR-1 à FR-35 contigus, avec une exception : FR-20b (§4.8). L'ID irrégulier est cité ailleurs (§7, NFR-9). *Fix:* renuméroter ou accepter le suffixe, mais le faire à l'identique partout. SM-1 à SM-8 et SM-C1 à C4 sont contigus. NFR-1 à NFR-12 contigus. Les renvois (FR-10 depuis FR-15, FR-20 depuis FR-13, NFR-9 depuis FR-20b, §10 depuis FR-17 et FR-25) résolvent tous.
- **Table des jalons (§7)** : FR-18 figure dans v0.1 (plage FR-1 à FR-20b) et dans v1.0, ce qui est voulu (« complétée en v1.0 ») mais mériterait une mention. La ligne v1.0 dit « Installation hors ligne de tous les outils », alors que FR-18 ne demande que l'installation sans admin puis l'exécution hors ligne : trancher si l'*installation* elle-même doit pouvoir se faire hors ligne (zip complet), ce qui change la portée de SM-5.
- **Index des hypothèses (§11)** : aller-retour correct, les trois `[ASSUMPTION]` en ligne (FR-2, FR-3, FR-5) sont indexés et l'index ne contient rien d'absent du texte. La ligne finale sur les hypothèses confirmées cite FR-10, 12, 13, 16, 20b, 35, NFR-9 et NFR-12, qui n'ont pas de marque en ligne : cohérent avec la confirmation, mais l'index mêle deux natures.
- **Glossaire / dérive de termes** : « volet » et « vue » alternent pour le même objet (FR-4 « Vues », « volet distant » ; FR-5 « volets » ; FR-34 « dans les vues »). « dépôt d'exercice » (FR-21, FR-25, NFR-10) et « code d'exercice » (FR-16, FR-17, FR-28) ne sont pas définis dans le §3. « Check », « barrière » et « outil » sont employés comme synonymes dans §4.10. Impact bas.
- **NFR-9 et FR-17** : la vérification CI « absence d'appel réseau dans le code de l'application » doit prévoir l'exception de FR-17 ; à préciser pour éviter un faux échec.
- **Sections requises** : vision, utilisateurs, FR, NFR, non-goals, périmètre, SM, risques, questions ouvertes, index des hypothèses présents. Pas de section « acceptation » séparée : les conséquences testables en tiennent lieu, avec les lacunes listées plus haut.
