---
story: "9.3"
key: 9-3-trouver-les-scénarios-de-station-dans-le-catalogue
title: Trouver les scénarios de station dans le catalogue
status: done
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

## Revue

Rebase sur `story/6-4-reprendre-scenario` (9d311b9) sans conflit.

- Medium · second avis M1 · corrigé : un scénario de station absent de `STATION_ORDER` prendrait le rang des hors-ordre du socle, avant les stations connues (« Scénario suivant », rapport). Test de dérive `test_scenarios_de_station_livres_figurent_dans_l_ordre_conseille`, comme celui du socle.
- Medium · second avis M2 · corrigé : après 6.4, les cartes de station n'avaient ni « Reprendre » ni l'encart « Recommencer ». Les actions de `modeColumn` passent dans `appendActions`, partagé avec `stationMode` ; test Node `test_carte_de_station_reprendre_et_recommencer`.
- Medium · second avis M3 · rejeté : aucun conflit au rebase (6.4 et 9.3 touchent des blocs distincts).
- Low · second avis L4 · reporté : 3e critère (encart `.env`, story 8.x), déjà consigné en Reports.
- Low · second avis L5 · reporté : un scénario `section: stations` sans `station` s'affiche « Station 0 » ; erreur de contenu, à refuser par la validation du modèle si le cas se présente.
- Low · second avis L6 · rejeté : `chain.yaml` relu à chaque `/api/catalogue`, petit fichier, lu seulement s'il y a des scénarios de station ; le catalogue lit déjà tous les scénarios du disque.
- Low · second avis L7 · rejeté : `test_catalogue.py` lit la première section ; la liste exacte des sections est vérifiée dans `test_catalogue_stations.py`.
- Low · second avis L8 · corrigé : le nom accessible du bouton d'une carte de station porte le mode (« Ouvrir <titre> en mode A »), via `appendActions`.
- Low · second avis L9 · rejeté : `.station-groups`, `.station-title`, `.station-card-description` existent ; la carte compacte reprend `.scenario-card`. Rendu réel déjà en Reports (navigateur).
- Low · second avis L10 · corrigé en partie : état Reprendre/Recommencer d'une carte de station testé sous Node ; le 409 et l'état `ProgressStore` passent par le même code que le socle (testés dans `test_reprise.py`).
- Complexité : 0 constat (structures bornées par le nombre de scénarios du contenu).
