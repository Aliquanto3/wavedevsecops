# Extrait OSV figé : attribution

Ce dossier contient un extrait daté (voir `index.json`, champ `extracted_on`) de la base de
vulnérabilités ouverte OSV (https://osv.dev), obtenu auprès de https://api.osv.dev pour les
paquets Python des gabarits d'exercice (`content/exercise/*/uv.lock`). Les enregistrements de
`vulns/` sont copiés tels que renvoyés par l'API, sans modification.

## Licences et attributions

- La base OSV est un agrégat : chaque enregistrement reste soumis à la licence de sa source.
- Les enregistrements `GHSA-*` viennent de la GitHub Advisory Database
  (https://github.com/advisories), sous licence CC-BY 4.0 : © GitHub, Inc. et contributeurs.
- Les enregistrements `PYSEC-*` viennent de la base de la Python Packaging Authority
  (https://github.com/pypa/advisory-database), sous licence CC-BY 4.0 : © PyPA et contributeurs.
- Les données OSV elles-mêmes sont publiées sous licence CC-BY 4.0
  (https://creativecommons.org/licenses/by/4.0/) ; voir https://google.github.io/osv.dev/faq/.
- Les autres sources (`CVE-*`, `OSV-*`, …) gardent leur propre licence, indiquée dans le champ
  `database_specific` ou `references` de l'enregistrement quand elle existe.

L'extrait est utilisé ici à des fins pédagogiques, hors ligne ; il est figé et n'est pas à jour.
Il se met à jour uniquement avec `uv run python scripts/update_osv.py` (jamais à l'exécution).
