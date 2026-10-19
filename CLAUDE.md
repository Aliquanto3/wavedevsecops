# WaveDevSecOps

Application pédagogique locale (git, GitHub, CI/CD, DevSecOps), hors ligne. Python 3.14 géré par uv.
Architecture : `_bmad-output/planning-artifacts/architecture/*/ARCHITECTURE-SPINE.md` (lire par extraits).

## Commandes

- Installer : `uv sync`
- Lint : `uv run ruff check .`
- Tests rapides : `uv run pytest -q -m "not slow"` (ajouter `-n auto` pour paralléliser) ; suite complète : CI
- Contrôle rapide de fin de story : `python .claude/cost-kit/controle_rapide.py`

## Règles à ne pas casser (vérifiées par les tests)

- Dépendances (AD-1) : `contracts`, `events`, `config` sont des feuilles ; personne n'importe `web` ni `cli` (sauf `cli` → `web`) ; seul `procs` crée des processus, appelé par `gitio` et `toolrun`.
- Hors ligne (AD-13) : aucun import réseau dans `src/` hors `llmrun` (et `socket` pour l'écoute de `web`/`cli`) ; aucune URL externe dans `web/static/` ; les tests tournent sous un hook d'audit `socket.connect` loopback seulement.
- Réglages : un seul `Settings` dans `config.py`, seul lecteur de l'environnement (`WDS_*`).
- Versions : celles de la table Stack du spine, épinglées dans `pyproject.toml` et `uv.lock`.
- Langue : textes en français (vouvoiement) ; identifiants et noms de fichiers en anglais.
