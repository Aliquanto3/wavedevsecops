"""Rapport de progression exportable (Story 6.5, FR-36, AD-14).

Le rapport est calculé à la lecture depuis `progress.json` (rien n'est écrit) : par parcours,
score du premier coup et indices (mêmes textes que le bilan, `progress.summary`), remises à zéro
et horodatages. Il ne quitte jamais le poste de lui-même : l'apprenant l'enregistre, puis choisit
à qui le transmettre. Rendus : HTML autonome (Jinja2, styles et polices en ligne, aucune
ressource externe, AD-13) et CSV UTF-8 avec BOM, séparateur `;`.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, select_autoescape

from wavedevsecops.progress import FILENAME, _read_json
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.progress.summary import build_summary
from wavedevsecops.scenarios.order import catalogue_rank

RESET_KIND = "scenario_reset"
"""Fait « remise à zéro » (story 4.4) : un par Recommencer réussi, consigné sans pénalité."""
STATE_TEXTS = {"todo": "À faire", "in_progress": "En cours", "done": "Terminé"}
PRIVACY_TEXT = "Rien n'est envoyé : vous choisissez à qui transmettre le fichier."
EMPTY_TEXT = (
    "Aucun scénario terminé pour l'instant. "
    "Le rapport contiendra seulement les dates d'installation et de premier lancement."
)
UNKNOWN_DATE_TEXT = "Non renseigné"
REPORT_TITLE = "Rapport de progression WaveDevSecOps"
CSV_HEADER = (
    "Parcours",
    "Scénario",
    "Mode",
    "État",
    "Questions justes du premier coup",
    "Questions posées",
    "Indices ouverts",
    "Remises à zéro",
    "Terminé le",
)
EXPORT_NAMES = {"html": "rapport-wavedevsecops.html", "csv": "rapport-wavedevsecops.csv"}
EXPORT_TYPES = {
    "html": "text/html; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}


def resets_text(count: int) -> str:
    """« 0 remise à zéro », « 1 remise à zéro », « 2 remises à zéro »."""
    return f"{count} remise à zéro" if count < 2 else f"{count} remises à zéro"


def when_text(value: object) -> str:
    """Date lisible « 19/10/2026 14:03 » depuis un horodatage ISO ; illisible ou absent : texte."""
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return value
    return UNKNOWN_DATE_TEXT


def _base_dates(data_dir: Path) -> tuple[Any, Any]:
    path = data_dir / FILENAME
    if not path.exists():
        return None, None
    data = _read_json(path)
    return data.get("installed_at"), data.get("first_launch_at")


def build_report(
    data_dir: Path,
    *,
    titles: dict[str, str] | None = None,
    tracks: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rapport JSON : `tracks` (lignes par parcours), dates, `empty`, textes de confidentialité.

    `titles` (`scenario_id` → titre) et `tracks` (`track` → libellé) viennent de la couche web ;
    un identifiant inconnu est affiché tel quel.
    """
    titles = titles or {}
    tracks = tracks or {}
    store = ProgressStore.for_dir(data_dir)
    facts = store.facts()
    resets: dict[tuple[str, str, str], int] = {}
    completed: dict[tuple[str, str, str], str] = {}
    for raw in facts:
        key = (raw.get("track"), raw.get("scenario_id"), raw.get("mode"))
        if not all(isinstance(part, str) for part in key):
            continue
        if raw.get("kind") == RESET_KIND:
            resets[key] = resets.get(key, 0) + 1  # type: ignore[index]
        elif raw.get("kind") == "scenario_completed":
            completed.setdefault(key, str(raw.get("at") or ""))  # type: ignore[arg-type]
    by_track: dict[str, list[dict[str, Any]]] = {}
    for (track, scenario_id, mode), progress in store.all_progress().items():
        summary = build_summary(progress)
        count = resets.get((track, scenario_id, mode), 0)
        at = completed.get((track, scenario_id, mode), "")
        by_track.setdefault(track, []).append(
            {
                "scenario_id": scenario_id,
                "title": titles.get(scenario_id, scenario_id),
                "mode": mode,
                "state": progress.state,
                "state_text": STATE_TEXTS[progress.state],
                "quiz_correct": summary["quiz_correct"],
                "quiz_total": summary["quiz_total"],
                "score_text": summary["score_text"],
                "hints": summary["hints"],
                "hints_text": summary["hints_text"],
                "resets": count,
                "resets_text": resets_text(count),
                "completed_at": at,
                "completed_text": when_text(at) if at else "",
            }
        )
    out_tracks = []
    for track in sorted(by_track):
        rows = sorted(by_track[track], key=lambda r: (catalogue_rank(r["scenario_id"]), r["mode"]))
        out_tracks.append({"track": track, "label": tracks.get(track, track), "rows": rows})
    installed, first = _base_dates(data_dir)
    stamp = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    return {
        "title": REPORT_TITLE,
        "generated_at": stamp,
        "generated_text": when_text(stamp),
        "installed_at": installed,
        "installed_text": when_text(installed),
        "first_launch_at": first,
        "first_launch_text": when_text(first),
        "empty": not any(r["state"] == "done" for t in out_tracks for r in t["rows"]),
        "empty_text": EMPTY_TEXT,
        "privacy_text": PRIVACY_TEXT,
        "tracks": out_tracks,
    }


_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ r.title }}</title>
<style>
{{ font_css|safe }}
:root { color-scheme: light dark; --ink: #1d2433; --bg: #fff; --line: #9aa3b5; --soft: #eef1f7; }
@media (prefers-color-scheme: dark) {
  :root { --ink: #eef1f7; --bg: #161b27; --line: #5b6579; --soft: #232a3a; }
}
@media print { :root { --ink: #1d2433; --bg: #fff; --line: #9aa3b5; --soft: #eef1f7; } }
body { margin: 0 auto; max-width: 60rem; padding: 1.5rem 1rem; color: var(--ink);
  background: var(--bg); font: 1rem/1.5 "Atkinson Hyperlegible", system-ui, sans-serif; }
h1 { font-size: 1.6rem; margin: 0 0 .25rem; }
h2 { font-size: 1.2rem; margin: 2rem 0 .5rem; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: .4rem .6rem; border: 1px solid var(--line); }
th { background: var(--soft); }
dl { display: grid; grid-template-columns: max-content 1fr; gap: .25rem 1rem; }
dt { font-weight: 700; }
dd { margin: 0; }
.privacy { background: var(--soft); border-left: 4px solid var(--line); padding: .5rem .75rem; }
@media print { body { max-width: none; } h2 { break-after: avoid; } tr { break-inside: avoid; } }
</style>
</head>
<body>
<h1>{{ r.title }}</h1>
<p>Établi le {{ r.generated_text }}.</p>
<p class="privacy">{{ r.privacy_text }}</p>
<dl>
<dt>Installation</dt><dd>{{ r.installed_text }}</dd>
<dt>Premier lancement</dt><dd>{{ r.first_launch_text }}</dd>
</dl>
{% if r.empty %}<p>{{ r.empty_text }}</p>{% endif %}
{% for t in r.tracks %}
<h2>{{ t.label }}</h2>
<table>
<thead><tr><th scope="col">Scénario</th><th scope="col">Mode</th><th scope="col">État</th>
<th scope="col">Score</th><th scope="col">Indices</th><th scope="col">Remises à zéro</th>
<th scope="col">Terminé le</th></tr></thead>
<tbody>
{% for row in t.rows %}<tr><th scope="row">{{ row.title }}</th><td>{{ row.mode }}</td>
<td>{{ row.state_text }}</td><td>{{ row.score_text }}</td><td>{{ row.hints_text }}</td>
<td>{{ row.resets_text }}</td><td>{{ row.completed_text }}</td></tr>
{% endfor %}</tbody>
</table>
{% endfor %}
</body>
</html>
"""
_HTML = Environment(autoescape=select_autoescape(default=True)).from_string(_TEMPLATE)


def render_html(report: dict[str, Any], font_css: str = "") -> str:
    """HTML autonome : styles et polices (`font_css`, `@font-face` en data URI) dans le fichier."""
    return _HTML.render(r=report, font_css=font_css)


def _cell(value: object) -> str:
    """Texte sûr pour un tableur : une cellule qui ressemble à une formule est neutralisée."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def render_csv(report: dict[str, Any]) -> bytes:
    """CSV UTF-8 avec BOM, séparateur `;` (accents corrects dans un tableur français)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Installation", report["installed_text"]])
    writer.writerow(["Premier lancement", report["first_launch_text"]])
    writer.writerow([])
    writer.writerow(CSV_HEADER)
    for track in report["tracks"]:
        for row in track["rows"]:
            writer.writerow(
                [
                    _cell(track["label"]),
                    _cell(row["title"]),
                    row["mode"],
                    row["state_text"],
                    row["quiz_correct"],
                    row["quiz_total"],
                    row["hints"],
                    row["resets"],
                    row["completed_text"],
                ]
            )
    return out.getvalue().encode("utf-8-sig")
