"""Indices par paliers (FR-13, AD-2, AD-7, AD-14, AD-17) : `hint_open {tier}`.

Trois paliers par étape : la piste, la commande partielle (avec des blancs), la solution. Ils
s'ouvrent dans l'ordre, sans pénalité. La disponibilité d'un palier et sa raison sont calculées
ici, par le serveur (AD-2) ; le front les affiche et n'y change rien.

Règle de la solution : un essai a eu lieu sur l'étape (commande tapée, choix validé, réponse
envoyée) ou `SOLUTION_DELAY_S` secondes se sont écoulées depuis l'ouverture de la commande
partielle.

État dans `run.json["hints"][step_id]` : `since` (début de l'étape), `attempts` (essais) et
`opened[tier] = {at, delay_ms, read_ms}`. `hint_pending` désigne le dernier palier ouvert dont le
temps de lecture court encore : il se clôt à l'action suivante (autre palier, commande, choix,
changement de l'extérieur, validation). Le fait `hint_opened{tier, delay_ms, read_ms}` n'est donc
soumis à `progress` qu'à cette clôture ; `run.json` est écrit d'abord, et `StepRunner.replay`
rejoue les paliers clos après un arrêt brutal. Rouvrir un palier déjà ouvert ne fait rien.
"""

from __future__ import annotations

import math
import time
from typing import Any

from pydantic import BaseModel, Field

from wavedevsecops.contracts import AppError
from wavedevsecops.engine.intents import INTENTS, Intent, register_intent
from wavedevsecops.engine.operations import OpContext, Operation, OperationRefused, WorkspaceEngine
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.events import Kind

HINT_INTENT = "hint_open"
ATTEMPT_INTENTS = frozenset({"terminal_line", "quiz_choice", "answer_submit"})
"""Opérations de l'apprenant qui comptent comme un essai sur l'étape."""
SOLUTION_DELAY_S = 20
READ_MS_MAX = 15 * 60 * 1000
"""Plafond du temps de lecture : au-delà, l'apprenant a quitté l'application ou fait autre chose."""
TIERS = (
    (1, "Piste", "lead_text"),
    (2, "Commande partielle", "partial_text"),
    (3, "Solution", "solution_text"),
)

NO_HINTS_TEXT = "Cette étape n'a pas d'indice."
LOCK_TEXTS = {
    2: "Ouvrez d'abord la piste.",
    "3_first": "Ouvrez d'abord la commande partielle.",
    "3_wait": "Disponible après un essai ou un moment de lecture.",
}
UNLOCKED_TEXT = "La solution est disponible."
OPENING_TEXT = "Ouverture de l'indice."

clock = time.time
"""Horloge murale en secondes (remplaçable par les tests)."""


class HintOpen(BaseModel):
    tier: int = Field(ge=1, le=3)


def _entry(run: dict[str, Any], step_id: str) -> dict[str, Any]:
    hints = run.get("hints")
    entry = hints.get(step_id) if isinstance(hints, dict) else None
    return entry if isinstance(entry, dict) else {}


def _opened(entry: dict[str, Any]) -> dict[str, Any]:
    opened = entry.get("opened")
    return opened if isinstance(opened, dict) else {}


def availability(entry: dict[str, Any], now: float) -> dict[int, tuple[str, str, int | None]]:
    """`tier -> (état, condition en clair, attente restante en ms)` ; état : `open`,
    `available` ou `locked`. L'attente n'existe que pour la solution qui patiente."""
    opened = _opened(entry)
    out: dict[int, tuple[str, str, int | None]] = {}
    for tier, _, _ in TIERS:
        if str(tier) in opened:
            out[tier] = ("open", "", None)
        elif tier == 1:
            out[tier] = ("available", "", None)
        elif tier == 2:
            ready = "1" in opened
            out[tier] = ("available", "", None) if ready else ("locked", LOCK_TEXTS[2], None)
        else:
            second = opened.get("2")
            if not isinstance(second, dict):
                out[tier] = ("locked", LOCK_TEXTS["3_first"], None)
                continue
            waited = now - float(second.get("at") or 0)
            if int(entry.get("attempts") or 0) > 0 or waited >= SOLUTION_DELAY_S:
                out[tier] = ("available", "", None)
            else:
                left = math.ceil((SOLUTION_DELAY_S - waited) * 1000)
                out[tier] = ("locked", LOCK_TEXTS["3_wait"], left)
    return out


def panel_hints(run: dict[str, Any], step: Any, now: float | None = None) -> dict[str, Any] | None:
    """Les trois onglets de l'étape courante pour le panneau Scénario ; `None` sans indices."""
    hints = getattr(step, "hints", None)
    if hints is None:
        return None
    states = availability(_entry(run, step.step_id), clock() if now is None else now)
    tiers = []
    for tier, label, field in TIERS:
        state, condition, _ = states[tier]
        item: dict[str, Any] = {"tier": tier, "label_text": label, "state": state}
        if state == "open":
            item["text"] = getattr(hints, field)
        elif state == "locked":
            item["condition_text"] = condition
        tiers.append(item)
    return {"tiers": tiers, "solution_unlock_ms": states[3][2], "unlocked_text": UNLOCKED_TEXT}


def start_step(run: dict[str, Any], step_id: str | None, now: float) -> dict[str, Any]:
    """`run["hints"]` avec le début de l'étape `step_id` (sans toucher aux paliers ouverts)."""
    hints = dict(run.get("hints") or {})
    if step_id:
        entry = dict(_entry(run, step_id))
        entry.setdefault("since", now)
        hints[step_id] = entry
    return hints


def _fact(run: dict[str, Any], step_id: str, tier: int, opened: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "hint_opened",
        "step_id": step_id,
        "tier": tier,
        "delay_ms": opened.get("delay_ms"),
        "read_ms": opened.get("read_ms"),
        "track": run.get("track"),
        "scenario_id": run.get("scenario_id"),
        "mode": run.get("mode"),
    }


def close_pending(run: dict[str, Any], now: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Clôt le temps de lecture du dernier palier ouvert : `(run mis à jour, faits à soumettre)`."""
    pending = run.get("hint_pending")
    rest = {k: v for k, v in run.items() if k != "hint_pending"}
    if not isinstance(pending, dict):
        return run, []
    step_id, tier = str(pending.get("step_id") or ""), str(pending.get("tier") or "")
    entry = dict(_entry(run, step_id))
    opened = dict(_opened(entry))
    mine = opened.get(tier)
    if not isinstance(mine, dict):
        return rest, []
    read_ms = max(0, int((now - float(mine.get("at") or now)) * 1000))
    closed = {**mine, "read_ms": min(read_ms, READ_MS_MAX)}
    opened[tier] = closed
    hints = {**dict(run.get("hints") or {}), step_id: {**entry, "opened": opened}}
    return {**rest, "hints": hints}, [_fact(run, step_id, int(tier), closed)]


def on_operation(ctx: OpContext, run: dict[str, Any]) -> dict[str, Any]:
    """Suites d'une action de l'apprenant, avant la validation de l'étape : l'essai est compté
    et le temps de lecture du dernier indice se clôt. Rend `run.json` mis à jour (déjà écrit)."""
    intent = ctx.op.intent
    if intent == HINT_INTENT or not (run.get("hint_pending") or intent in ATTEMPT_INTENTS):
        return run
    now = clock()
    updated, facts = close_pending(run, now)
    step_id = updated.get("step_id")
    if intent in ATTEMPT_INTENTS and step_id:
        hints = start_step(updated, step_id, now)
        entry = {**hints[step_id], "attempts": int(hints[step_id].get("attempts") or 0) + 1}
        updated = {**updated, "hints": {**hints, step_id: entry}}
    if updated != run:
        save_run(ctx.layout, updated)
    if facts:
        ctx.submit_facts(facts)
    return updated


def settle(ctx: OpContext) -> None:
    """Point de clôture hors de la validation d'étape : clôt la lecture du dernier indice (et
    compte l'essai d'une commande refusée). À appeler par toute opération qui suit une action de
    l'apprenant sans passer par `StepRunner.validate` : rétablissement, commande refusée par la
    liste blanche, et « Recommencer » (4.4) avant de reconstruire `run.json`."""
    if not ctx.layout.run_json.exists():
        return
    try:
        run = load_run(ctx.layout)
    except AppError:
        return
    on_operation(ctx, run)


def replay_facts(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Faits des paliers dont le temps de lecture est clos, rejoués au réveil (doublons ignorés)."""
    facts = []
    hints = run.get("hints")
    for step_id, entry in hints.items() if isinstance(hints, dict) else ():
        for tier, opened in _opened(entry if isinstance(entry, dict) else {}).items():
            if isinstance(opened, dict) and opened.get("read_ms") is not None and tier.isdigit():
                facts.append(_fact(run, str(step_id), int(tier), opened))
    return facts


def build_hint_open(engine: WorkspaceEngine, body: HintOpen) -> Operation:
    """Refuse un palier verrouillé (409, avec sa condition) ; sinon rend l'opération d'ouverture."""
    from wavedevsecops.engine.steps import StepRunner  # noqa: PLC0415 - steps importe ce module

    run = load_run(engine.layout)
    scenario = StepRunner(engine.settings).scenario(run)
    step = next(
        (s for s in (scenario.steps if scenario else ()) if s.step_id == run.get("step_id")), None
    )
    if step is None or step.hints is None:
        raise OperationRefused(NO_HINTS_TEXT)
    tier = body.tier
    state, condition, _ = availability(_entry(run, step.step_id), clock())[tier]
    if state == "locked":
        raise OperationRefused(condition)
    step_id = step.step_id

    def still_wanted(ctx: OpContext) -> bool:
        """Revérifié dans la file : étape changée, palier déjà ouvert ou encore verrouillé."""
        data = load_run(ctx.layout)
        if data.get("step_id") != step_id:
            return False
        return availability(_entry(data, step_id), clock())[tier][0] == "available"

    def open_hint(ctx: OpContext) -> int | None:
        data = load_run(ctx.layout)
        now = clock()
        data, facts = close_pending(data, now)
        hints = start_step(data, step_id, now)
        entry = hints[step_id]
        delay_ms = max(0, int((now - float(entry["since"])) * 1000))
        opened = {**_opened(entry), str(tier): {"at": now, "delay_ms": delay_ms, "read_ms": None}}
        hints[step_id] = {**entry, "opened": opened}
        pending = {"step_id": step_id, "tier": tier}
        save_run(ctx.layout, {**data, "hints": hints, "hint_pending": pending})
        ctx.emit(Kind.HINT_OPENED, {"step_id": step_id, "tier": tier})
        if facts:
            ctx.submit_facts(facts)
        return 0

    return Operation(
        HINT_INTENT,
        open_hint,
        writes=False,
        validate=False,
        precheck=still_wanted,
        reason_text=OPENING_TEXT,
    )


def register_intents() -> None:
    """Enregistre `hint_open` (idempotent)."""
    if HINT_INTENT not in INTENTS:
        register_intent(Intent(HINT_INTENT, HintOpen, build_hint_open))
