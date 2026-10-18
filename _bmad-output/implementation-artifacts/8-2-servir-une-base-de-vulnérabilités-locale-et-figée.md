---
story: "8.2"
key: 8-2-servir-une-base-de-vulnérabilités-locale-et-figée
title: Servir une base de vulnérabilités locale et figée
status: review
branch: story/8-2-osv-local
ad: [AD-11, AD-12, AD-19]
---

# Story 8.2 : Servir une base de vulnérabilités locale et figée

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 8.2 ».

## Livré

- `content/osv/` : extrait OSV daté du 2026-10-18 (170 enregistrements `GHSA-*` et `PYSEC-*` copiés tels que renvoyés par `api.osv.dev`, dans `vulns/<id>.json`), `index.json` (date, source, paquet -> identifiants) et `ATTRIBUTION.md` (CC-BY 4.0, sources GitHub Advisory Database et PyPA). Paquets : tous ceux des `uv.lock` des deux gabarits (dont `jinja2`, `requests`, `urllib3`, `pyyaml`, `pip`, `certifi`, `idna`), toutes versions confondues, pour que les stories 8.x puissent épingler une version vulnérable et sa version corrigée.
- `src/wavedevsecops/osv/` : module sans dépendance interne. Charge l'extrait une fois en mémoire (objet immuable), répond à `POST /osv/v1/query` au format de l'API OSV (`{"package": {"name", "ecosystem"}, "version"}` ou `purl`) : enregistrements dont `affected` touche la version (liste `versions` ou plages `ECOSYSTEM` / `SEMVER`, ordre PEP 440 maison), `{}` si rien, tous les enregistrements du paquet si la version est absente, 400 si le corps est invalide, 503 si l'extrait est absent (jamais une réponse « propre » par défaut).
- `web/app.py` : ajout ciblé de la route `POST /osv/v1/query` (corps limité à 64 Ko, 413 au-delà). La route est `async` et ne touche ni disque, ni verrou, ni file, ni thread : elle répond pendant qu'un outil tourne. Le middleware existant fait le reste : `Host` contrôlé, aucun cookie ni `Origin` exigé, toute autre méthode sous `/osv/` en 405, aucun CORS.
- `config.py` : `Settings.osv_path()` et `Settings.osv_url(port)`, seule source de l'URL `http://127.0.0.1:<port>/osv/v1/query`.
- `scripts/update_osv.py` : script de maintenance, seul code qui contacte `api.osv.dev` (urllib, https). Relit les paquets des `uv.lock` des gabarits, réécrit `vulns/` et `index.json` avec la date, ignore les enregistrements `withdrawn`. Rien ne se met à jour à l'exécution.
- Tests (`tests/test_osv.py`) : extrait et attribution, paquets des gabarits couverts, versions verrouillées des gabarits sans vulnérabilité (départ au vert), versions vulnérables et corrigées attendues, ordre des versions identique à `packaging`, HTTP (version vulnérable, nom non normalisé, version corrigée, version absente, paquet inconnu, autre écosystème, `purl`, corps invalides, corps trop gros, méthodes refusées, sans cookie ni origine, `Host`, requêtes concurrentes), script de maintenance (réseau simulé), et deux tests de bout en bout avec le vrai `pip-audit --vulnerability-service osv --osv-url ... --no-deps --disable-pip` sur le serveur local (JSON vulnérable, CycloneDX propre). `test_local_server.py` : la route n'est plus un 404.

## Décisions

- Un extrait complet par paquet (toutes versions) plutôt qu'une liste de versions choisies : le scénario « dépendance vulnérable » (8.3) choisira la version épinglée sans devoir refaire l'extrait ; le coût est de 170 petits fichiers JSON.
- Ordre des versions réimplémenté (PEP 440 simplifié) plutôt que d'ajouter `packaging` aux dépendances de l'application : la table Stack et `uv.lock` restent inchangés. Un test compare le résultat à `packaging` sur toutes les versions de l'extrait.
- pip-audit renvoie l'identifiant `PYSEC-*` d'une vulnérabilité et range le `GHSA-*` équivalent dans `aliases` : les stories 8.3 et suivantes doivent tester les deux.
- Pas de suivi des `page_token` : l'API locale renvoie tout en une réponse.

## Reports

- Ajout à `content/pipeline.yaml` (jetons `{osv_url}`, options exactes de pip-audit) : story 8.3, qui fixe aussi le choix de la version vulnérable épinglée.
- Précharger dans `uv-cache` la version corrigée de la dépendance vulnérable choisie : installeur (story 7.1 et suivantes).
- Les deux tests pip-audit de bout en bout ne tournent pas sous `unshare -n` (loopback absent de l'espace de noms) : ils restent dans la suite normale.
- Licence : l'attribution est générale (CC-BY 4.0) ; les sources autres que GHSA et PYSEC, absentes de l'extrait actuel, n'y sont pas détaillées.

## Revue

Revue unique (Opus), après rebase sur `main` (story 2.2 : conflit de cumul dans `web/app.py`, les deux ajouts gardés). Second avis : Haiku.

- **medium** · second avis · corrigé — `await request.body()` lisait tout le corps avant la limite ; le point est public et une page web peut y poster (`text/plain`, sans preflight). Désormais : `Content-Length` annoncé au-delà de 64 Ko refusé (413) sans lecture, flux lu par morceaux et coupé à 64 Ko + 1 (cas `chunked`). En plus, une requête portant un `Origin` étranger est refusée (403) : pip-audit n'en envoie jamais, un navigateur toujours, ce qui ferme la voie « POST simple » d'une page web.
- medium (sous-constat) · second avis · rejeté — exiger `Content-Type: application/json` : pip-audit 2.10.1 poste `data=json.dumps(...)` sans `Content-Type` (`pip_audit/_service/osv.py`), ce contrôle le casserait. Le refus d'un `Origin` étranger couvre le même risque.
- low · second avis · corrigé — JSON très imbriqué : `RecursionError` donnait un 500 ; désormais 400.
- low · second avis · corrigé — partie locale ignorée (`1.0+local` égal à `1.0`) : faux positif après `last_affected: 1.0`. La clé d'ordre porte maintenant la partie locale selon PEP 440 ; tests avec `packaging` comme oracle.
- low · second avis · corrigé — évènement de plage illisible ignoré (faux négatif possible) : échec fermé, la version est jugée affectée ; version demandée illisible avec plages : affectée. La liste `versions` est aussi comparée en PEP 440 (`1.0` = `1.0.0`).
- low · second avis · corrigé — `update_osv.py` effaçait `vulns/` avant les requêtes : le nouvel extrait s'écrit dans `.update/` puis est échangé ; une coupure réseau laisse l'ancien extrait entier (test avec réseau simulé).
- info · revue · noté — le test `chunked` passe aussi sur l'ancien code (il prouve le 413, pas la borne mémoire) ; la borne tient à la lecture par `request.stream()`.
