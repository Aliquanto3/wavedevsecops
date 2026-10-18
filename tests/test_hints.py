"""Indices par paliers (Story 4.6) : ordre d'ouverture, disponibilité calculée par le serveur,
faits du premier passage (palier, temps avant la demande, temps de lecture) — avec un vrai git."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    INTENTS,
    OpContext,
    Operation,
    OperationRefused,
    StepRunner,
    WorkspaceManager,
    build_operation,
    hints,
    load_run,
)
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.scenarios import load_scenario, parse_scenario

WAIT = 60.0

SCENARIO = """\
schema_version: 1
scenario_id: indices
mode: A
title_text: Scénario d'essai des indices
tracks: [llm, no_ai]
tools: [git]
setup:
  - op: write_file
    path: README.md
    content: "# Projet\\n"
  - op: commit
    message: Ajoute le README
    as: premier
steps:
  - step_id: creer_branche
    type: repo_state
    title_text: Créer la branche feature
    instruction_text: Créez la branche `feature` et placez-vous dessus.
    explanation_text: Une branche est un pointeur.
    hints:
      lead_text: Une branche se crée avec une sous-commande de `git switch`.
      partial_text: git switch -c ___
      solution_text: git switch -c feature
    expect:
      head:
        branch: feature
  - step_id: sans_indice
    type: repo_state
    title_text: Revenir sur main
    instruction_text: Revenez sur `main`.
    explanation_text: HEAD suit la branche active.
    expect:
      head:
        branch: main
"""


class Box:
    def __init__(self, manager, engine, git, events, settings, clock) -> None:  # noqa: ANN001
        self.manager, self.engine, self.git = manager, engine, git
        self.events, self.settings, self._clock = events, settings, clock

    @property
    def now(self) -> float:
        return self._clock["now"]

    def wait(self, seconds: float) -> None:
        self._clock["now"] += seconds

    def hint(self, tier: int) -> list[Envelope]:
        start = len(self.events)
        op = build_operation(self.engine, "hint_open", {"tier": tier})
        self.engine.submit(op).result(WAIT)
        return self.events[start:]

    def act(self, *git_args: str) -> list[Envelope]:
        """Une commande de l'apprenant (`terminal_line`), qui compte comme un essai."""
        start = len(self.events)
        repo = self.engine.layout.repo

        def body(ctx: OpContext) -> int:
            if git_args:
                ctx.output(self.git.internal(*git_args, cwd=repo) or "ok")
            return 0

        self.engine.submit(Operation("terminal_line", body)).result(WAIT)
        return self.events[start:]

    def tiers(self) -> list[dict]:
        panel = self.engine.snapshot()["step_panel"]
        current = next(s for s in panel["steps"] if s["state"] == "current")
        return current["hints"]["tiers"]

    def facts(self) -> list[dict]:
        path = self.settings.resolved_data_dir() / "progress.json"
        if not path.exists():
            return []
        facts = json.loads(path.read_text(encoding="utf-8")).get("facts", [])
        return [f for f in facts if f["kind"] == "hint_opened"]


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path, monkeypatch) -> Iterator:
    boxes: list[Box] = []
    clock = {"now": 1_780_000_000.0}
    monkeypatch.setattr(hints, "clock", lambda: clock["now"])
    hints.register_intents()

    def make() -> Box:
        content = tmp_path / "content"
        (content / "scenarios").mkdir(parents=True)
        path = content / "scenarios" / "indices.A.yaml"
        path.write_text(SCENARIO, encoding="utf-8", newline="\n")
        settings = Settings(data_dir=tmp_path / "data", content_dir=content)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        loaded = load_scenario(path, settings)
        events: list[Envelope] = []
        manager.events("llm.indices.A").attach(None, events.append)
        engine, setup = manager.create(loaded, "llm")
        setup.result(WAIT)
        git = Git.for_workspace(git_path, engine.layout.root, settings)
        box = Box(manager, engine, git, events, settings, clock)
        box.loaded = loaded
        boxes.append(box)
        return box

    yield make
    for box in boxes:
        box.manager.close()


def _states(box: Box) -> list[str]:
    return [t["state"] for t in box.tiers()]


def test_le_panneau_montre_trois_paliers_dont_deux_verrouilles(make_box) -> None:
    box = make_box()
    tiers = box.tiers()
    assert [t["label_text"] for t in tiers] == ["Piste", "Commande partielle", "Solution"]
    assert _states(box) == ["available", "locked", "locked"]
    assert tiers[1]["condition_text"] == "Ouvrez d'abord la piste."
    assert tiers[2]["condition_text"] == "Ouvrez d'abord la commande partielle."
    # Le texte d'un palier fermé n'est jamais envoyé au front ; aucun compteur.
    assert all("text" not in t for t in tiers)
    panel = box.engine.snapshot()["step_panel"]
    assert panel["has_hints"] is True
    assert "hint_count" not in json.dumps(panel)
    assert "hints" not in panel["steps"][1]  # l'étape sans indice n'en montre pas


def test_un_palier_ne_s_ouvre_qu_apres_le_precedent(make_box) -> None:
    box = make_box()
    with pytest.raises(OperationRefused, match="Ouvrez d'abord la piste"):
        build_operation(box.engine, "hint_open", {"tier": 2})
    with pytest.raises(OperationRefused, match="Ouvrez d'abord la commande partielle"):
        build_operation(box.engine, "hint_open", {"tier": 3})
    events = box.hint(1)
    assert [e.payload for e in events if e.kind == Kind.HINT_OPENED] == [
        {"step_id": "creer_branche", "tier": 1}
    ]
    assert _states(box) == ["open", "available", "locked"]
    assert box.tiers()[0]["text"].startswith("Une branche se crée")
    with pytest.raises(OperationRefused, match="Ouvrez d'abord la commande partielle"):
        build_operation(box.engine, "hint_open", {"tier": 3})


def test_la_solution_attend_un_essai_ou_vingt_secondes(make_box) -> None:
    box = make_box()
    box.hint(1)
    box.hint(2)
    tiers = box.tiers()
    assert tiers[1]["text"] == "git switch -c ___"  # les blancs viennent du contenu
    assert tiers[2]["state"] == "locked"
    assert tiers[2]["condition_text"] == "Disponible après un essai ou un moment de lecture."
    assert "text" not in tiers[2]
    panel = box.engine.snapshot()["step_panel"]
    current = next(s for s in panel["steps"] if s["state"] == "current")
    assert current["hints"]["solution_unlock_ms"] == 20_000
    assert current["hints"]["unlocked_text"] == "La solution est disponible."
    with pytest.raises(OperationRefused, match="Disponible après un essai"):
        build_operation(box.engine, "hint_open", {"tier": 3})

    box.wait(19.9)
    assert _states(box)[2] == "locked"
    box.wait(0.1)
    assert _states(box)[2] == "available"
    box.hint(3)
    assert box.tiers()[2]["text"] == "git switch -c feature"


def test_un_essai_debloque_la_solution(make_box) -> None:
    box = make_box()
    box.hint(1)
    box.hint(2)
    assert _states(box)[2] == "locked"
    box.act("status")  # une commande tapée, même sans effet sur l'étape
    assert _states(box)[2] == "available"
    assert load_run(box.engine.layout)["hints"]["creer_branche"]["attempts"] == 1


def test_un_essai_avant_la_commande_partielle_ne_la_contourne_pas(make_box) -> None:
    box = make_box()
    box.act("status")
    box.hint(1)
    assert _states(box) == ["open", "available", "locked"]
    box.hint(2)
    assert _states(box)[2] == "available"  # l'essai a déjà eu lieu pendant l'étape


def test_rouvrir_un_palier_ne_le_compte_pas_deux_fois(make_box) -> None:
    box = make_box()
    box.hint(1)
    box.wait(3)
    again = box.hint(1)  # déjà ouvert : l'opération est abandonnée sans bruit
    assert [e.kind for e in again] == []
    box.act("status")
    [fact] = box.facts()
    assert (fact["tier"], fact["step_id"]) == (1, "creer_branche")
    box.hint(1)
    box.act("status")
    assert len(box.facts()) == 1


def test_le_fait_porte_palier_delai_et_temps_de_lecture(make_box) -> None:
    box = make_box()
    box.wait(5)
    box.hint(1)  # 5 s après le début de l'étape
    box.wait(7)
    events = box.hint(2)  # 7 s de lecture du palier 1 : son fait est soumis maintenant
    assert [f["tier"] for f in box.facts()] == [1]
    assert Kind.PROGRESS_UPDATED in [e.kind for e in events]
    box.wait(4)
    box.act("status")  # 4 s de lecture du palier 2, clos par l'action suivante
    first, second = box.facts()
    assert (first["tier"], first["delay_ms"], first["read_ms"]) == (1, 5000, 7000)
    assert (second["tier"], second["delay_ms"], second["read_ms"]) == (2, 12000, 4000)
    assert (first["track"], first["scenario_id"], first["mode"]) == ("llm", "indices", "A")
    state = ProgressStore.for_dir(box.settings.resolved_data_dir()).progress(
        "llm", "indices", "A"
    )
    assert state.hints == 2


def test_la_validation_clot_la_lecture_du_dernier_indice(make_box) -> None:
    box = make_box()
    box.hint(1)
    box.wait(9)
    box.act("switch", "-c", "feature")  # réussit l'étape
    assert load_run(box.engine.layout)["step_id"] == "sans_indice"
    [fact] = box.facts()
    assert (fact["tier"], fact["read_ms"]) == (1, 9000)
    assert "hint_pending" not in load_run(box.engine.layout)


def test_une_etape_sans_indice_refuse_hint_open(make_box) -> None:
    box = make_box()
    box.act("switch", "-c", "feature")
    with pytest.raises(OperationRefused, match="n'a pas d'indice"):
        build_operation(box.engine, "hint_open", {"tier": 1})
    panel = box.engine.snapshot()["step_panel"]
    assert all("hints" not in step for step in panel["steps"])


def test_l_etape_suivante_commence_son_propre_chrono(make_box) -> None:
    box = make_box()
    box.wait(30)
    box.hint(1)
    box.act("switch", "-c", "feature")
    entries = load_run(box.engine.layout)["hints"]
    assert entries["sans_indice"]["since"] == box.now
    assert entries["creer_branche"]["opened"]["1"]["delay_ms"] == 30_000


def test_rejeu_des_paliers_clos_apres_un_arret_brutal(make_box) -> None:
    box = make_box()
    box.hint(1)
    box.wait(2)
    box.hint(2)  # clôt le palier 1 ; le palier 2 court encore
    replayed = StepRunner(box.settings).replay(box.engine)
    tiers = [(f["kind"], f["tier"], f["read_ms"]) for f in replayed if f["kind"] == "hint_opened"]
    assert tiers == [("hint_opened", 1, 2000)]  # le palier ouvert n'est pas rejoué


def test_un_arret_brutal_ne_fait_pas_perdre_le_debut_de_l_etape(make_box) -> None:
    box = make_box()
    box.wait(10)
    StepRunner(box.settings).replay(box.engine)
    assert load_run(box.engine.layout)["hints"]["creer_branche"]["since"] <= box.now


def test_hint_open_est_au_catalogue_et_enregistre() -> None:
    hints.register_intents()
    assert "hint_open" in INTENTS


def test_lint_blanc_manquant_dans_la_commande_partielle() -> None:
    bad = SCENARIO.replace("git switch -c ___", "git switch -c feature")
    scenario = parse_scenario(bad, "indices.A.yaml")
    messages = [m for _, m in scenario.authoring_warnings()]
    assert any("aucun blanc" in m for m in messages)
    assert not parse_scenario(SCENARIO, "indices.A.yaml").authoring_warnings()


def test_recommencer_clot_la_lecture_avant_de_reconstruire(make_box) -> None:
    """Revue M1 : le palier encore en lecture devient un fait avant la reconstruction."""
    box = make_box()
    box.hint(1)
    box.wait(6)
    _engine, setup = box.manager.create(box.loaded, "llm", replace=True)
    setup.result(WAIT)
    [fact] = box.facts()
    assert (fact["tier"], fact["read_ms"]) == (1, 6000)
    assert "hint_pending" not in load_run(box.engine.layout)


def test_une_commande_refusee_compte_comme_essai(make_box) -> None:
    """Revue L5 : une commande tapée, même refusée par la liste blanche, est un essai."""
    from wavedevsecops import terminal  # noqa: PLC0415

    terminal.register_intents()
    box = make_box()
    allowlist = Path(__file__).parents[1] / "content" / "terminal-allowlist.yaml"
    (box.settings.content_path() / allowlist.name).write_bytes(allowlist.read_bytes())
    box.hint(1)
    box.hint(2)
    box.wait(3)
    op = build_operation(box.engine, "terminal_line", {"line": "rm -rf ."})
    box.engine.submit(op).result(WAIT)
    assert _states(box)[2] == "available"
    assert [(f["tier"], f["read_ms"]) for f in box.facts()] == [(1, 0), (2, 3000)]


def test_le_temps_de_lecture_est_plafonne(make_box) -> None:
    """Revue L2 : application quittée jusqu'au lendemain, lecture plafonnée."""
    box = make_box()
    box.hint(1)
    box.wait(24 * 3600)
    box.act("status")
    [fact] = box.facts()
    assert fact["read_ms"] == hints.READ_MS_MAX


def test_le_bilan_compte_l_indice_ouvert(make_box) -> None:
    """Intégration 4.6 → 4.7 : le fait `hint_opened` émis à la clôture arrive dans le bilan."""
    box = make_box()
    box.hint(1)
    box.act("switch", "-c", "feature")
    box.act("switch", "main")  # dernière étape : scénario terminé
    summary = box.engine.snapshot()["step_panel"]["summary"]
    assert summary is not None
    assert summary["hints"] == 1
    assert summary["text"].endswith("1 indice")
