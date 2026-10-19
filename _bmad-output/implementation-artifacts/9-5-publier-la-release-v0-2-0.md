---
story: "9.5"
key: 9-5-publier-la-release-v0-2-0
title: Publier la release v0.2.0
status: review
branch: story/9-5-release-v0-2-0
ad: [AD-13, AD-18]
---

# Story 9.5 : Publier la release v0.2.0

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 9.5 ». Type mixte : l'agent prépare, l'orchestrateur publie après accord d'Anaël, Anaël fait la mesure et SM-9.

## Préparé (dans la branche)

- `pyproject.toml` et `uv.lock` : `0.2.0` (`uv lock --offline`, `uv lock --check` vert) ; `tests/test_seed.py` aligné.
- `CURRENT_MILESTONE = "v0.2"` (`web/shell.py`) : la page Vocabulaire est servie, `/fiche` (v0.3) reste 404. Tests réalignés : `test_surfaces_declarees_par_le_serveur`, `test_surface_non_livree_absente`. Stations 1 à 3 `delivered: true` dans `content/chain.yaml` (seule source), station 4 « Arrive en v0.3 » ; aucun texte « aperçu v0.2 » restant hors des notes de la v0.1.0 (historique).
- `README.md` : bandeau et présentation v0.2.0, barrières, installation épinglée `WDS_INSTALL_REF=v0.2.0`, jalons.
- `docs/releases/v0.2.0.md` : contenu, limites connues, durées CI du test de performance (alerte 90 s, échec 180 s), sections **à remplir par Anaël** (mesure des 45 s ; SM-9, tableau scénario × parcours).
- CI, contrôle AD-13 n°4 : l'étape `unshare -n` ne couvrait aucun scénario de station. Ajoutés (petit changement) `test_scenarios_socle`, `test_stations_pr`, `test_pre_commit_hook`, `test_code_vulnerable`, `test_outil_trop_puissant`, qui n'ouvrent aucun serveur local.

## Reports

- Les tests qui démarrent un serveur sur la boucle locale (`test_dependance_vulnerable`, `test_quality_gate`, `test_llm_scenarios`) ne sont pas dans l'étape `unshare -n` : l'interface `lo` d'un espace de noms neuf est éteinte. Les couvrir demande `ip link set lo up` dans l'espace ; non fait ici, à décider.
- Non vérifié localement : l'étape `unshare -n` ne tourne que sous Linux ; la CI de branche en juge.

## Reste humain ou à publier après accord

1. Mesure du run complet du pipeline sur le poste de référence (45 s au plus) et SM-9 : à remplir dans `docs/releases/v0.2.0.md`.
2. Publication (orchestrateur) : tag annoté `v0.2.0` sur le commit fusionné, release GitHub avec `docs/releases/v0.2.0.md` pour notes, topic `status-test`.
