---
story: "9.3"
key: 9-3-trouver-les-scénarios-de-station-dans-le-catalogue
title: Trouver les scénarios de station dans le catalogue
status: review
branch: story/9-3-catalogue-stations
ad: [AD-7, AD-14, AD-16]
---

# Story 9.3 : Trouver les scénarios de station dans le catalogue

Source : `epics.md`, section « Story 9.3 » ; FR-9, FR-27, UX-DR29 ; reports des specs 6-1 et 7-2.

## Livré

- Serveur (`web/catalogue.py`) : `catalogue_body` accepte la section `stations` en plus du socle. Les scénarios de station sortent du socle (la numérotation du socle reste continue) et forment une seconde section « Stations » : `groups` par station (`station`, `text` « Station n · Nom », `scenarios`). Le nom de la station vient de `content/chain.yaml` (`load_chain_texts`) ; sans le fichier, « Station n ». La section n'existe que s'il y a au moins un scénario de station. Disponibilité et état (AD-14, AD-16) sont ceux du socle.
- Contenu : nouveau champ optionnel `description_text` du scénario (une phrase), renseigné pour `defaut-de-lint` et `test-casse`.
- Ordre (`scenarios/order.py`, ajout) : `STATIONS_SECTION`, `STATION_ORDER`. `catalogue_rank` place les scénarios de station après le socle, donc le rapport (6.5) et le « Scénario suivant » gardent l'ordre du catalogue.
- Front (`catalogue.js`, ajout) : si la section porte `groups`, un sous-titre « Station n · Nom » à filet `discipline-harness` par station, puis une carte par scénario (titre, phrase, une seule ligne d'état : « État · détail », ou « ⊘ Indisponible · Nécessite <outil> · Voir le diagnostic »), sans disque numéroté. `catalogue.css` : `.station-title`, `.station-card-description`.
- Tests : `tests/test_catalogue_stations.py` (section serveur, outil absent nommé, section absente sans scénario de station, rang, rendu Node) ; `test_catalogue.py` lit la première section.

## Décisions

- Les cartes de station n'ont qu'un mode affiché par ligne d'état ; si un second mode arrive, il ajoute une ligne (une par mode), pas une colonne.

## Reports

- L'encart « Ce qui l'aurait bloqué » du scénario `.env` n'existe pas encore (story 8.x) : l'étiquette « Arrive en v0.2 » et le lien vers le scénario de la barrière sont à retirer ou poser dans cette story, d'après la déclaration des jalons côté serveur.
- À vérifier dans un vrai navigateur : filet de station, cartes compactes à une colonne, thème sombre, lecture NVDA (régions « Station n · Nom »).
