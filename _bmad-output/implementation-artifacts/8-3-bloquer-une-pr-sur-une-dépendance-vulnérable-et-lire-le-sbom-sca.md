---
story: "8.3"
key: 8-3-bloquer-une-pr-sur-une-dépendance-vulnérable-et-lire-le-sbom-sca
title: Bloquer une PR sur une dépendance vulnérable et lire le SBOM (SCA)
status: review
branch: story/8-3-sca-sbom
ad: [AD-10, AD-11, AD-14]
---

# Story 8.3 : Bloquer une PR sur une dépendance vulnérable et lire le SBOM (SCA)

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 8.3 » ; FR-25, FR-27, FR-33, UX-DR22, AR-23. pip-audit 2.10.1 est déjà dans la table Stack, `tools.toml` et les gabarits : aucune dépendance ajoutée (le SBOM vient de `pip-audit -f cyclonedx-json`, pas d'un autre outil).

## Livré

- **Job `pip_audit`** (`content/pipeline.yaml`, après bandit) : outil `pip-audit`, `required: true`, barrière `dependencies`. Options exactes (AR-23), consignées dans le fichier : `--vulnerability-service osv --osv-url {osv_url} --no-deps --disable-pip --progress-spinner off -r requirements.txt`. Trois exécutions sur le même arbre : humaine (affichée, verbatim), `-f json` (constats, si échec), `-f cyclonedx-json` (SBOM, à chaque run). Codes `success: [0]`, `failure: [1]` ; tout autre code : erreur de l'outil. Le point OSV est celui de 8.2 (aucun appel externe).
- **Lecteurs** (`ci/findings.py`, valeurs de `ci.Parse`) : `pip_audit_json` (un constat par couple dépendance/faille, doublons de pip-audit écartés, fichier `requirements.txt` et ligne de l'épinglage, alias CVE/GHSA, versions corrigées, et « Base embarquée, figée au <date de l'extrait> » dans le message ; dépendance non auditée : `unscanned_file`) et `cyclonedx_json` (composants du SBOM : nom, version, licences si le document en porte, vulnérabilités rattachées). Texte vide ou illisible : `ValueError` (échec sans détail, la sortie humaine reste), jamais un vert.
- **SBOM dans le contrat** : `Check.sbom` (`SbomComponent`, `SbomVuln`, ajout seulement, défaut vide) écrit par le pipeline (`JobResult.sbom`, `github_sim.set_check_state(sbom=)`), exclu de l'empreinte comme `output`.
- **`sbom-view`** (vue Distant + PR, sous le check) : « Voir le SBOM » / « Masquer le SBOM » sur tout check qui a un SBOM ; tableau en lecture seule (étiquette « Lecture seule ») composant, version, licence, vulnérabilités ; ligne vulnérable sur fond `danger-soft` avec ✗ et l'identifiant. Chaque ligne a un `element_id` `sbom:<paquet>@<version>`, est sélectionnable, désignable (`designable`, type `sbom` accepté par `designate`), nommée (`names`, clé d'explication `remote.sbom`) et liée au check, à `requirements.txt` et à `pyproject.toml`. Ouvrir le SBOM soumet la preuve `evidence_seen` de la barrière (comme « Voir la sortie »).
- **Gabarits** : `requirements.txt` épinglé (sans dépendance pour `no_ai`, les pins de `uv.lock` pour `llm`) ; job `pip_audit` balisé `wds:job` / `wds:end` dans les 6 fichiers CI.
- **Scénario `dependance-vulnerable.A.yaml`** (parcours sans IA, station 3, `STATION_ORDER` après `code-vulnerable`) : `main` exige `pip_audit` ; la branche `feature` épingle `jinja2==3.1.2` dans `pyproject.toml` et `requirements.txt`. Étapes : pousser, ouvrir la PR, lire le blocage (`pip_audit` en échec), désigner le composant vulnérable dans le SBOM (`designate`), corriger vers `3.1.6` et pousser (`pip_audit` vert **et** jinja2 présent au SBOM : `pr_state.sbom_has`).
- **Étape `pr_state`** : `sbom_has` (`{job_id: [paquets]}`), lu sur les SHA courants. Un fichier de dépendances vidé ou supprimé, ou une dépendance remplacée, ne valide donc pas l'étape (leçon 6.2). Les contournements par option sont impossibles : l'argv du job est fixé.
- **Station 2 réalignée** : `pr-sans-revue` attend aussi `pip_audit: success` ; harnais `test_stations_pr.py` donne un `osv_url` au gestionnaire (outils remplacés, aucune connexion). Glossaire : `sca` et `sbom` renseignent `scenario_id: dependance-vulnerable`.
- Empreintes mises à jour (`update_fingerprints.py`, stables sur deux passes). Tests : `tests/test_dependance_vulnerable.py` (contrat du job, lecteurs, scénario, étape, projection et liens, désignation, vrai pip-audit contre le point OSV local : refus puis acceptation, contournements, départ vert des deux gabarits) ; `test_pipeline*.py`, `test_glossary.py`, `test_exercise.py` réalignés.

## Décisions

- **Fichier lu par pip-audit : `requirements.txt`.** pip-audit n'accepte `--no-deps --disable-pip` qu'avec `-r` (un `pyproject.toml` en argument est refusé) : le gabarit porte donc un `requirements.txt` épinglé, que l'apprenant met à jour avec `pyproject.toml`. Les lignes du SBOM sont liées aux deux.
- **`uv.lock` inchangé par le scénario** : la version vulnérable (3.1.2) n'est pas dans le cache préchargé, et `uv sync --offline --frozen` du pipeline échouerait sur un verrou qui la liste. Le verrou garde jinja2 3.1.6 (déjà préchargé : dépendance de diff-cover), donc la version corrigée est bien « préchargée » et la synchronisation hors ligne réussit avant comme après.
- **Licence** : pip-audit n'écrit pas de licence dans le CycloneDX sans résolution (`--no-deps --disable-pip`) ; la colonne affiche « non indiquée » et prend la licence du document quand il en porte une. Écart assumé avec le critère « la licence », sans outil ni dépendance de plus.
- **`sbom-view` dans la vue Distant + PR**, sous le check, plutôt que dans la vue Code : le SBOM appartient au check (UX : « sur le check »). Pas d'ouverture depuis l'arbre de fichiers (reporté).
- Données hors empreinte : `sbom` (sortie du job, comme `output`).

## Reports

- « Voir le SBOM » depuis l'arbre de fichiers de la vue Code (le critère dit « sur le check ou dans l'arbre ») : le SBOM n'est ouvrable que depuis le check.
- Licences réelles dans le SBOM : demanderait une source de métadonnées hors ligne (extrait OSV enrichi ou lecture des `METADATA` de l'environnement), non livrée ici.
- Scénario du parcours LLM (gabarit `llm`, même défaut sur httpx) : story des barrières LLM.
- `uv.lock` cohérent avec `pyproject.toml` après la correction : l'apprenant ne peut pas lancer `uv lock` dans le terminal (liste blanche) ; la CI utilise `--frozen`.
- Test navigateur de `sbom-view` : couvert par le contrat de projection, pas par un test DOM.

## À vérifier sur poste réel

1. Pousser `feature`, ouvrir la PR : `pip_audit` passe à « Échec · Obligatoire », le détail nomme jinja2 3.1.2, `PYSEC-2026-1471` (et ses alias) et cite « Base embarquée, figée au 2026-10-18 » ; « Merger » est inactif.
2. « Voir le SBOM » : la ligne jinja2 3.1.2 est sur fond rouge clair avec ✗ et ses identifiants, liée à `requirements.txt`, `pyproject.toml` et au check ; la désigner puis valider.
3. Passer jinja2 à `3.1.6` dans les deux fichiers, committer, pousser : le check repasse au vert et le SBOM garde jinja2 3.1.6 sans ✗.

## Revue

Revue Opus du 2026-10-19, après rebase sur `origin/main` (5.8 ; `content/fingerprints.json` régénéré, stable sur deux passes).

- High · second avis 1 · corrigé : `create_app` construisait `WorkspaceManager(settings)` sans `osv_url` ; dans l'application réelle, `{osv_url}` manquait et pip_audit (requis) sortait en erreur, PR bloquée. `osv_url=settings.osv_url(port)` ; test par `create_app`.
- High · revue · corrigé : les tests lents de `test_pipeline.py` (8 tests) cassés par le nouveau job : harnais sans `osv_url`, attente de 4 checks codée en dur, listes de jobs à 4. Harnais complété, pip-audit simulé par défaut (rapport et SBOM vides lisibles).
- Medium · second avis 2 · corrigé : fingerprints régénérés après rebase.
- Medium · second avis 3 · corrigé en partie : une exigence de `requirements.txt` absente du SBOM (marqueur d'environnement faux sur le runner, que pip-audit saute sans le dire) donne un constat `unscanned_file` dans `parse_cyclonedx_json`, donc un check rouge (tests unitaire et lent avec le vrai pip-audit). « Fichier vidé = vert » rejeté : le gabarit no_ai n'a aucune dépendance et doit rester vert ; l'étape `sbom_has` refuse déjà ce contournement (test lent existant).
- Medium · second avis 4 · reporté (décision pour Anaël) : seul `requirements.txt` est audité, conformément à AR-23 (`-r requirements.txt`, `--no-deps`). Corriger seulement `requirements.txt` valide l'étape même si `pyproject.toml` garde 3.1.2 (`uv sync --frozen` ne le voit pas). L'étape est un `pr_state`, sans condition de contenu ; ajouter `tree.contains` au `pr_state` changerait un contrat partagé. Piste : un job `uv lock --check` ou une condition de contenu dans une story ultérieure.
- Low · second avis 5 · corrigé : SBOM expiré ou illisible : constat `unscanned_file` au lieu d'un vert silencieux (test). Les doublures de `test_stations_pr.py` produisent désormais un SBOM lisible.
- Low · second avis 6 · rejeté : les gabarits CI commentent déjà `{osv_url}` (« adresse du point OSV ; dans WaveDevSecOps : le point local ») ; ajouter l'URL publique d'OSV mettrait une URL externe dans le contenu sans gain.
- Complexité : 0 constat (lecteurs linéaires sur le rapport et le fichier d'exigences ; aucune structure qui grossit par événement).
