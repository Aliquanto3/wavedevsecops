# Référence pédagogique et technique : WaveStack

Dépôt local : `C:\Users\Utilisateur\Documents\GitHub\agentic-harness-training-demo` (spec : `_bmad-output/specs/spec-agentic-harness-training-demo/SPEC.md`).

## Principes pédagogiques repris

- Montrer ce qui se passe vraiment, pendant que cela se passe, plutôt que l'expliquer après coup.
- Plusieurs volets synchronisés sur le même état ; sélectionner un élément éclaire ses correspondants.
- Une vue schéma qui situe chaque pièce (chez WaveStack : schéma d'architecture ; ici : carte de la chaîne).
- Programme guidé en scénarios qui préparent l'état et donnent la consigne.
- Une explication courte, en français, attachée à chaque élément.
- Les échecs sont du matériau pédagogique, jamais un plantage.

## Pratiques d'installation reprises

- Commande unique d'installation sous PowerShell, sans droits administrateur, et voie depuis un clone ou un zip.
- Page de diagnostic au premier lancement.
- Prise en compte des proxys d'entreprise.

## Stack de WaveStack, candidate et non décidée

Python 3.13, `uv`, FastAPI, uvicorn, pydantic, Jinja2, PyYAML ; `ruff` et `pytest` ; licence Apache-2.0 ; textes d'interface en français, identifiants en anglais. La reprise de cette stack est une question ouverte d'architecture (voir SPEC.md).
