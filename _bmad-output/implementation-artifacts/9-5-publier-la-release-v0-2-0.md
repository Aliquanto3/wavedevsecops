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
- CI, contrôle AD-13 n°4 : l'étape `unshare -n` ne couvrait aucun scénario de station. Ajoutés `test_scenarios_socle`, `test_stations_pr`, `test_pre_commit_hook`, `test_code_vulnerable`, `test_outil_trop_puissant`, puis en revue `test_blockers`, `test_dependance_vulnerable`, `test_quality_gate`, `test_llm_scenarios`. Plusieurs démarrent un serveur sur la boucle locale (point OSV local, fixture `osv_url`) : l'étape rallume `lo` dans l'espace de noms (`ip link set lo up`) avant de lancer les tests en runner. Toutes les stations 1 à 3 des deux parcours tournent ainsi réseau coupé, boucle locale seule.

## Reports

- Non vérifié localement : l'étape `unshare -n` ne tourne que sous Linux ; la CI de branche en juge (à vérifier : l'étape est verte et ses tests ne sont pas tous ignorés, `ip link set lo up` réussit sous `sudo unshare`).
- Limite « le seuil porte sur un total, pas sur chaque fichier » : consignée en revue de la 8.5, absente du débrief de `outil-trop-puissant` et de `couverture-sous-le-seuil`. Les notes le disent ; l'ajouter au débrief touche du contenu empreinté, laissé à une story de contenu.

## Reste humain ou à publier après accord

1. Mesure du run complet du pipeline sur le poste de référence (45 s au plus) et SM-9 : à remplir dans `docs/releases/v0.2.0.md`.
2. Publication (orchestrateur), après accord d'Anaël et fusion sur `main`, CI de `main` verte. Ordre : tag poussé avant la release (les liens `/v0.2.0/install.sh` et `/v0.2.0/install.ps1` du README répondent 404 tant que le tag n'existe pas).

   ```sh
   git switch main && git pull --ff-only
   gh run list --branch main --limit 1          # vert sur les trois OS
   git tag -a v0.2.0 -m "WaveDevSecOps v0.2.0 : stations 1 à 3 de la chaîne DevSecOps, deux parcours, hors ligne"
   git push origin v0.2.0
   gh release create v0.2.0 --verify-tag --title "WaveDevSecOps v0.2.0" --notes-file docs/releases/v0.2.0.md
   curl -fsI https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/v0.2.0/install.sh   # 200
   ```

   Topic : `status-test` est déjà posé, rien à changer.

## Revue

Revue sur la branche rebasée sur `main` (42f2456).

| Sévérité | Source | Constat | Décision |
|---|---|---|---|
| high | second avis 1 | `test_outil_trop_puissant` (fixture `osv_url`, `cli.start_instance` sur 127.0.0.1) ajouté à l'étape `unshare -n`, où `lo` est éteinte : étape Linux rouge. | Corrigé : `sh -c 'ip link set lo up && exec "$@"'` dans l'espace, et ajout de `test_blockers`, `test_dependance_vulnerable`, `test_quality_gate`, `test_llm_scenarios` : toutes les stations sous `unshare -n`. CI Linux juge. |
| medium | second avis 2 | « n'ouvrent aucun serveur local » faux (fichier de story ; les notes de release ne le disaient pas). | Corrigé dans le fichier de story. |
| low | second avis 3 | Durées CI 4,21 s et 9,08 s du run 39251263153. | Écarté : vérifié dans le log du run (`--durations`), sur `f917b1a`. |
| low | second avis 4 | Liens `/v0.2.0/` du README en 404 avant le tag. | Attendu ; ordre tag puis release noté dans les commandes de publication. |
| low | second avis 5 | `content/diagnostic.yaml` « Outils de la chaîne (v0.2+) ». | Écarté : reste exact (outils requis à partir de la v0.2), à côté de « Outils requis (v0.2) » ; contenu empreinté, pas de gain. |
| low | second avis 6 | Limite « total, pas chaque fichier » dite dans les notes comme nommée au débrief, alors qu'elle ne l'est pas. | Corrigé dans les notes (mention explicite) ; ajout au débrief reporté. |
| low | revue | README : la ligne « Jenkins, GitHub Actions, GitLab CI et Sonar… » se retrouvait rattachée à la nouvelle puce « Barrières de la v0.2 ». | Corrigé : ligne remise sous la puce « Chaîne DevSecOps ». |

Complexité : 0 constat (aucune structure qui grossit à l'exécution dans le diff).
