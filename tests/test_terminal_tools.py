"""ruff et pytest dans le terminal (Story 7.2) : garde, outil déclaré, sortie verbatim, liens
tirés d'une exécution machine, interruption, preuve `evidence_seen` (AD-4, AD-10, AD-14).

Les lancements d'outils sont remplacés par de petits sous-processus Python qui impriment la
sortie voulue ; le vrai ruff et le vrai pytest tournent dans `test_vrais_outils_dans_le_terminal`
quand l'environnement d'exercice est disponible (`WDS_EXERCISE_UV=1`, comme
`tests/test_exercise.py`).
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_procs_spawn import alive, wait_dead

from wavedevsecops import procs, terminal, toolrun
from wavedevsecops.config import Settings
from wavedevsecops.contracts import element_id
from wavedevsecops.engine import WorkspaceEngine, WorkspaceManager, prepare_workspace
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.terminal import TerminalLine, build_terminal_line, tools
from wavedevsecops.terminal.allowlist import Allowlist, get_allowlist
from wavedevsecops.terminal.parse import Refused, ToolCommand, parse_line
from wavedevsecops.toolrun import findings as machine
from wavedevsecops.wsfs import Layout

CONTENT = Path(__file__).resolve().parent.parent / "content" / "scenarios"
LINT = CONTENT / "defaut-de-lint.A.yaml"
BROKEN = CONTENT / "test-casse.A.yaml"
FREE = CONTENT / "bac-a-sable-libre.A.yaml"
WAIT = 60.0
PYTHON = getattr(sys, "_base_executable", sys.executable)
RAPPORT = "src/inventory/rapport.py"

RUFF_TEXT = (
    "src/inventory/rapport.py:3:8: F401 [*] `os` imported but unused\n"
    "src/inventory/rapport.py:9:1: E501 autre ligne\n"
    "Found 2 errors.\n"
)


@pytest.fixture
def allow() -> Allowlist:
    return get_allowlist(Settings())


def _parse(line: str):
    return parse_line(line, get_allowlist(Settings()))


# ------------------------------------------------------------------ garde (AD-4)
@pytest.mark.parametrize(
    ("line", "write"),
    [
        ("ruff check .", False),
        ("ruff check src tests", False),
        ("ruff check --statistics .", False),
        ("ruff check --select F401 .", False),
        ("ruff check --select=F401 --fix src", True),
        ("pytest", False),
        ("pytest -q --tb=short", False),
        ("pytest tests/test_stock.py::test_add_cumulates_quantities -x", False),
        ("pytest -k 'stock and not unknown' tests", False),
        ("pytest -qx -rA", False),
    ],
)
def test_la_garde_accepte_ruff_et_pytest(line: str, write: bool) -> None:
    command = _parse(line)
    assert isinstance(command, ToolCommand)
    assert command.name == line.split()[0] and command.write is write
    assert command.barrier_id in {"lint", "tests"}


@pytest.mark.parametrize(
    ("line", "needle"),
    [
        ("ruff", "attend une sous-commande"),
        ("ruff format .", "attend une sous-commande"),
        ("ruff check --config evil.toml .", "n'est pas acceptée"),
        ("ruff check --select", "attend une valeur"),
        ("ruff check ../autre", "n'est pas un chemin du dépôt"),
        ("ruff check /etc", "n'est pas un chemin du dépôt"),
        ("pytest -p evil_plugin", "n'est pas acceptée"),
        ("pytest -c autre.ini", "n'est pas acceptée"),
        ("pytest --rootdir=/", "n'est pas acceptée"),
        ("pytest --junitxml=x.xml", "n'est pas acceptée"),
        ("pytest ../hors", "n'est pas un chemin du dépôt"),
        ("pytest C:\\Windows", "n'est pas un chemin du dépôt"),
        ("pytest .git/config", "n'est pas un chemin du dépôt"),
        ("pytest -k", "attend une valeur"),
        ("pytest | cat", "n'y a aucun effet"),
        ("ruff check . > sortie.txt", "n'y a aucun effet"),
        ("pytest && ls", "n'y a aucun effet"),
    ],
)
def test_la_garde_refuse_avec_explication(line: str, needle: str) -> None:
    with pytest.raises(Refused) as refused:
        _parse(line)
    assert needle in refused.value.text
    # La liste citée vient du fichier : outils compris.
    assert "ruff, pytest" in refused.value.text


def test_la_liste_blanche_de_ruff_et_pytest_est_un_seul_fichier(allow: Allowlist) -> None:
    assert set(allow.tools) == {"ruff", "pytest"}
    assert {"-p", "-c", "--rootdir", "--junitxml", "--config", "--output-format"}.isdisjoint(
        {o for spec in allow.tools.values() for o in spec.options}
    )
    assert allow.tools["ruff"].write_options == ["--fix"]
    assert not allow.tools["pytest"].write_options


# ------------------------------------------------------------------ constats machine (AD-10)
def test_constats_ruff_depuis_le_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    absolute = str(repo / "src" / "a.py")
    payload = json.dumps(
        [
            {"filename": absolute, "location": {"row": 3, "column": 8}, "code": "F401"},
            {"filename": "src/b.py", "location": {"row": 5, "column": 1}, "code": "E501"},
            {"filename": "/ailleurs/c.py", "location": {"row": 1, "column": 1}, "code": "X"},
        ]
    )
    found = machine.parse_ruff(payload, repo)
    assert found.lines == {"src/a.py": frozenset({3}), "src/b.py": frozenset({5})}
    assert found.covers("src/a.py", 3) and not found.covers("src/a.py", 4)
    assert not found.covers("src/c.py", 1)
    assert machine.parse_ruff("pas du json", repo).error


def test_constats_pytest_depuis_le_rapport_junit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_a.py").write_text("", encoding="utf-8")
    xml = (
        "<testsuites><testsuite>"
        '<testcase classname="tests.test_a" name="test_ok"/>'
        '<testcase classname="tests.test_a.TestX" name="test_ko"><failure message="m"/></testcase>'
        '<testcase classname="tests.test_b" name="test_err"><error message="m"/></testcase>'
        "</testsuite></testsuites>"
    )
    found = machine.parse_junit(xml, repo)
    assert list(found.lines) == ["tests/test_a.py"]  # tests/test_b.py n'existe pas : écarté
    assert found.covers("tests/test_a.py", 7)  # tout numéro de ligne du fichier en échec
    assert machine.parse_junit("<pas du xml", repo).error


def test_ruff_machine_retire_les_options_humaines_et_d_ecriture() -> None:
    args = machine.machine_ruff_args(["check", "--fix", "--statistics", "--select", "F", "src"])
    assert args == ["check", "--select", "F", "src", "--output-format", "json", "--no-fix"]


def test_seuls_les_passages_designes_par_la_machine_sont_des_liens() -> None:
    found = machine.Findings({"src/inventory/rapport.py": frozenset({3})})
    spans = tools.link_spans(RUFF_TEXT, found, {"src/inventory/rapport.py"})
    assert [(s["text"], s["element_id"]) for s in spans] == [
        ("src/inventory/rapport.py:3", element_id("path", "worktree", "src/inventory/rapport.py"))
    ]
    start = spans[0]["start"]
    assert RUFF_TEXT[start : spans[0]["end"]] == "src/inventory/rapport.py:3"
    # Ligne 9 : le texte la nomme, la machine non -> pas de lien (jamais tiré du texte humain).
    assert len(spans) == 1


def test_liens_fichier_ligne_chemins_windows_et_positions_utf16() -> None:
    found = machine.Findings({"tests/test_é.py": frozenset()})
    text = "𝄞 échec tests\\test_é.py:7: AssertionError\nsrc/x.py:1: autre\n"
    (span,) = tools.link_spans(text, found, {"tests/test_é.py"})
    assert span["text"] == "tests\\test_é.py:7"
    # « 𝄞 » vaut deux unités UTF-16 : les positions sont celles de `String.prototype.slice`.
    units = text.encode("utf-16-le")
    begin = span["start"] * 2
    assert units[begin : span["end"] * 2].decode("utf-16-le") == span["text"]
    assert span["element_id"] == element_id("path", "worktree", "tests/test_é.py")
    # Un fichier absent du dépôt n'est pas lié, même si la machine le désigne.
    assert tools.link_spans(text, found, set()) == []


# ------------------------------------------------------------------ dans un espace ouvert
class Box:
    """Un espace ouvert sur un scénario de station 1, avec le journal de ses événements."""

    def __init__(self, settings: Settings, git_path: Path, scenario: Path, track: str) -> None:
        self.settings = settings
        loaded = load_scenario(scenario, settings)
        prepare_workspace(loaded, track, settings=settings, git_path=git_path, replace=True)
        self.ws = f"{track}.{loaded.scenario.key}"
        self.manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        self.engine: WorkspaceEngine = self.manager.get(self.ws)
        self.layout: Layout = self.manager.layout(self.ws)
        self.events: list[Envelope] = []
        self.manager.events(self.ws).attach(None, self.events.append)
        deadline = time.monotonic() + WAIT
        while len(self.events) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)

    def start(self, line: str):
        op = build_terminal_line(self.engine, TerminalLine(line=line))
        return op, self.engine.submit(op)

    def run(self, line: str):
        op, future = self.start(line)
        outcome = future.result(WAIT)
        mine = [e for e in self.events if e.op_id == op.op_id]
        exits = [e for e in mine if e.kind == Kind.OP_EXIT]
        return op, (exits[-1].payload["code"] if exits else outcome.code), mine

    def facts(self) -> list[dict]:
        return ProgressStore.for_dir(self.settings.resolved_data_dir()).facts()


@pytest.fixture
def no_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ni `uv sync` à l'ouverture, ni environnement à vérifier : les outils sont remplacés."""
    monkeypatch.setattr(toolrun, "needs_environment", lambda *a, **k: False)
    monkeypatch.setattr(tools, "_prepare_environment", lambda *a, **k: True)


@pytest.fixture
def lint_box(tmp_path: Path, git_path: Path, no_sync: None) -> Iterator[Box]:
    box = Box(Settings(data_dir=tmp_path / "data"), git_path, LINT, "no_ai")
    try:
        yield box
    finally:
        box.manager.close()


def _fake_tool(monkeypatch: pytest.MonkeyPatch, text: str, code: int, *, sleep: float = 0.0):
    """`toolrun.spawn_tool` remplacé par un Python qui imprime `text` puis sort avec `code`."""
    calls: list[tuple[str, tuple[str, ...], Path, Path]] = []
    real_spawn = procs.spawn

    def fake(tool_id, args, *, cwd, venv, timeout, settings=None):  # noqa: ANN001, ANN202
        calls.append((tool_id, tuple(args), cwd, venv))
        # Octets UTF-8 tels quels : pas de conversion des fins de ligne propre à Windows.
        script = f"import sys, time; sys.stdout.buffer.write({text.encode()!r}); "
        script += f"sys.stdout.flush(); time.sleep({sleep}); sys.exit({code})"
        return real_spawn([PYTHON, "-c", script], env=dict(os.environ), cwd=cwd, timeout=timeout)

    monkeypatch.setattr(toolrun, "spawn_tool", fake)
    return calls


def test_outil_non_declare_refuse_avec_son_explication(
    tmp_path: Path, git_path: Path, no_sync: None
) -> None:
    box = Box(Settings(data_dir=tmp_path / "data"), git_path, FREE, "llm")
    try:
        _op, code, events = box.run("ruff check .")
        outputs = [e.payload for e in events if e.kind == Kind.TERMINAL_OUTPUT]
        assert code == terminal.EXIT_REFUSED
        assert [o["stream"] for o in outputs] == ["refused"] and not outputs[0]["tool"]
        assert "« ruff » n'est pas disponible dans ce scénario" in outputs[0]["text"]
        assert "ses étapes ne déclarent pas cet outil" in outputs[0]["text"]
        assert not box.facts()
    finally:
        box.manager.close()


def test_le_scenario_ne_declare_que_ses_outils(lint_box: Box) -> None:
    assert terminal.declared_tools(lint_box.engine) == {"git", "ruff"}
    _op, code, events = lint_box.run("pytest")  # pytest n'est pas déclaré par ce scénario
    assert code == terminal.EXIT_REFUSED
    text = "".join(e.payload["text"] for e in events if e.kind == Kind.TERMINAL_OUTPUT)
    assert "« pytest » n'est pas disponible dans ce scénario" in text


def test_ruff_sortie_verbatim_en_bloc_etiquete_liens_machine_et_preuve(
    lint_box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_tool(monkeypatch, RUFF_TEXT, 1)
    seen: list[tuple] = []

    def fake_collect(tool_id, args, **kwargs):  # noqa: ANN001, ANN202
        seen.append((tool_id, tuple(args), kwargs["repo"], kwargs["venv"]))
        return machine.Findings({RAPPORT: frozenset({3})})

    monkeypatch.setattr(machine, "collect", fake_collect)
    op, code, events = lint_box.run("ruff check .")
    assert code == 1
    ((tool_id, args, cwd, venv),) = calls
    assert (tool_id, args) == ("ruff", ("check", ".")) and cwd == lint_box.layout.repo
    assert venv == toolrun.venv_dir(lint_box.layout.root)  # l'environnement d'exercice
    # Exécution machine : même outil, mêmes arguments, même arbre.
    assert seen == [("ruff", ("check", "."), lint_box.layout.repo, venv)]

    kinds = [e.kind.value for e in events]
    assert kinds.index("terminal_output") < kinds.index("op_exit")
    blocks = [e.payload for e in events if e.kind == Kind.TERMINAL_OUTPUT and e.payload["tool"]]
    assert len(blocks) == 1
    (block,) = blocks
    assert block["tool"] == "ruff" and block["text"] == RUFF_TEXT  # verbatim, octet pour octet
    (span,) = block["spans"]
    assert span["text"] == "src/inventory/rapport.py:3"
    assert span["element_id"] == element_id("path", "worktree", RAPPORT)
    exit_texts = [e.payload["text"] for e in events if e.payload.get("stream") == "exit"]
    assert exit_texts == ["Code de sortie : 1"]
    # La preuve de la barrière `lint` est soumise une fois, quand la sortie s'affiche (AD-14).
    evidence = [f for f in lint_box.facts() if f["kind"] == "evidence_seen"]
    assert [(f["barrier_id"], f["scenario_id"], f["track"]) for f in evidence] == [
        ("lint", "defaut-de-lint", "no_ai")
    ]
    assert evidence[0]["op_id"] == op.op_id
    lint_box.run("ruff check .")  # le premier passage fait foi : pas de doublon
    assert len([f for f in lint_box.facts() if f["kind"] == "evidence_seen"]) == 1


def test_sortie_machine_en_echec_garde_la_sortie_sans_liens(
    lint_box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tool(monkeypatch, RUFF_TEXT, 1)
    monkeypatch.setattr(machine, "collect", lambda *a, **k: machine.Findings(error="illisible"))
    _op, code, events = lint_box.run("ruff check .")
    (block,) = [e.payload for e in events if e.kind == Kind.TERMINAL_OUTPUT and e.payload["tool"]]
    assert code == 1 and block["text"] == RUFF_TEXT and block["spans"] == []
    notices = [e.payload["text"] for e in events if e.payload.get("stream") == "app"]
    assert notices and "Les liens vers le code ne sont pas disponibles" in notices[0]


def test_succes_sans_execution_machine_et_preuve_vue(
    lint_box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tool(monkeypatch, "All checks passed!\n", 0)

    def refused(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("pas d'exécution machine quand l'outil réussit")

    monkeypatch.setattr(machine, "collect", refused)
    _op, code, events = lint_box.run("ruff check .")
    (block,) = [e.payload for e in events if e.kind == Kind.TERMINAL_OUTPUT]
    assert code == 0 and block["text"] == "All checks passed!\n" and block["tool"] == "ruff"
    assert [f["barrier_id"] for f in lint_box.facts() if f["kind"] == "evidence_seen"] == ["lint"]


def test_outil_indisponible_renvoie_au_diagnostic(
    lint_box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise toolrun.ToolUnavailable(
            toolrun.ToolStatus("ruff", "mismatch", reason="environnement abîmé (uv sync)")
        )

    monkeypatch.setattr(toolrun, "spawn_tool", broken)
    _op, code, events = lint_box.run("ruff check .")
    text = "".join(e.payload["text"] for e in events if e.kind == Kind.TERMINAL_OUTPUT)
    assert code == tools.EXIT_UNAVAILABLE
    assert "environnement abîmé (uv sync)" in text and "Ouvrez le diagnostic" in text
    assert not [f for f in lint_box.facts() if f["kind"] == "evidence_seen"]


def test_ctrl_c_arrete_l_outil_sans_preuve(lint_box: Box, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_tool(monkeypatch, "début\n", 0, sleep=60)
    started = time.monotonic()
    op, future = lint_box.start("ruff check .")
    deadline = time.monotonic() + WAIT
    while lint_box.engine.state != "command" and time.monotonic() < deadline:
        time.sleep(0.02)
    time.sleep(0.5)
    assert lint_box.engine.interrupt()
    future.result(WAIT)
    mine = [e for e in lint_box.events if e.op_id == op.op_id]
    code = [e.payload["code"] for e in mine if e.kind == Kind.OP_EXIT][-1]
    assert code == terminal.EXIT_INTERRUPTED and time.monotonic() - started < 30
    text = "".join(e.payload["text"] for e in mine if e.kind == Kind.TERMINAL_OUTPUT)
    assert "début" in text and "Commande interrompue." in text
    assert not [f for f in lint_box.facts() if f["kind"] == "evidence_seen"]


def test_delai_depasse_arrete_l_outil(
    tmp_path: Path, git_path: Path, no_sync: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path / "data", tool_timeout_s=1.0)
    box = Box(settings, git_path, LINT, "no_ai")
    try:
        _fake_tool(monkeypatch, "lent\n", 0, sleep=60)
        _op, code, events = box.run("ruff check .")
        text = "".join(e.payload["text"] for e in events if e.kind == Kind.TERMINAL_OUTPUT)
        assert code == terminal.EXIT_TIMEOUT and "dépassé 1 s" in text
    finally:
        box.manager.close()


def test_seule_l_option_fix_est_une_ecriture(lint_box: Box) -> None:
    assert build_terminal_line(lint_box.engine, TerminalLine(line="ruff check .")).writes is False
    fix = build_terminal_line(lint_box.engine, TerminalLine(line="ruff check --fix ."))
    assert fix.writes is True  # refusée en `quiz_altered` (AD-1)


def test_environnement_d_exercice_cree_a_l_ouverture_si_le_scenario_declare_un_outil(
    tmp_path: Path, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Path, Path]] = []

    def fake_sync(project, venv, settings=None, **kwargs):  # noqa: ANN001, ANN202
        calls.append((project, venv))
        return procs.ProcResult(0)

    monkeypatch.setattr(toolrun, "sync_environment", fake_sync)
    settings = Settings(data_dir=tmp_path / "data")
    prepared = prepare_workspace(
        load_scenario(LINT, settings), "no_ai", settings=settings, git_path=git_path
    )
    assert calls == [(prepared.layout.repo, toolrun.venv_dir(prepared.layout.root))]
    calls.clear()  # un scénario sans outil de la chaîne ne crée pas d'environnement
    prepare_workspace(load_scenario(FREE, settings), "llm", settings=settings, git_path=git_path)
    assert calls == []


def test_echec_de_la_creation_de_l_environnement_n_empeche_pas_l_ouverture(
    tmp_path: Path, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        toolrun, "sync_environment", lambda *a, **k: procs.ProcResult(None, error="hors ligne")
    )
    settings = Settings(data_dir=tmp_path / "data")
    prepared = prepare_workspace(
        load_scenario(BROKEN, settings), "llm", settings=settings, git_path=git_path
    )
    assert (prepared.layout.repo / "tests" / "test_rupture.py").is_file()


def test_secours_cree_l_environnement_et_s_arrete_sur_ctrl_c(
    lint_box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Report de la 6.6 : le `uv sync` de secours du terminal est interruptible."""
    monkeypatch.undo()  # retire `no_sync` : on veut le vrai `_prepare_environment`
    real_spawn = procs.spawn
    spawned: list[procs.Handle] = []

    def sleeping(argv, *, env, cwd, timeout):  # noqa: ANN001, ANN202
        handle = real_spawn(
            [PYTHON, "-c", "import time; time.sleep(60)"], env=env, cwd=cwd, timeout=timeout
        )
        spawned.append(handle)
        return handle

    uv = toolrun.ToolStatus("uv", "ok", "0.13.1", Path(PYTHON), "host")
    monkeypatch.setattr(toolrun, "resolve", lambda tool_id, *a, **k: uv)
    monkeypatch.setattr(toolrun.procs, "spawn", sleeping)
    op, future = lint_box.start("ruff check .")
    deadline = time.monotonic() + WAIT
    while not spawned and time.monotonic() < deadline:
        time.sleep(0.02)
    assert spawned and lint_box.engine.interrupt()
    future.result(WAIT)
    pid = spawned[0].pid
    assert wait_dead(pid) and not alive(pid)
    mine = [e for e in lint_box.events if e.op_id == op.op_id]
    text = "".join(e.payload["text"] for e in mine if e.kind == Kind.TERMINAL_OUTPUT)
    assert "Commande interrompue." in text
    assert not [f for f in lint_box.facts() if f["kind"] == "evidence_seen"]


# ------------------------------------------------------------------ vrais outils
USE_TEMPLATE_LOCK = os.environ.get("WDS_EXERCISE_UV") == "1"


@pytest.mark.skipif(not USE_TEMPLATE_LOCK, reason="WDS_EXERCISE_UV=1 : environnement verrouillé")
@pytest.mark.parametrize(
    ("scenario", "track", "line", "needle", "link", "barrier"),
    [
        (LINT, "no_ai", "ruff check .", "F401", RAPPORT, "lint"),
        (LINT, "llm", "ruff check .", "F401", RAPPORT, "lint"),
        (BROKEN, "no_ai", "pytest", "test_rupture", "tests/test_rupture.py", "tests"),
        (BROKEN, "llm", "pytest -q --tb=short", "test_rupture", "tests/test_rupture.py", "tests"),
    ],
)
def test_vrais_outils_dans_le_terminal(
    git_path: Path,
    scenario: Path,
    track: str,
    line: str,
    needle: str,
    link: str,
    barrier: str,
) -> None:
    # Le cache uv préchargé par l'installeur (hors ligne) est celui des vrais outils.
    settings = Settings(data_dir=Path(os.environ["WDS_EXERCISE_DATA"]))
    box = Box(settings, git_path, scenario, track)
    try:
        _op, code, events = box.run(line)
        blocks = [e.payload for e in events if e.kind == Kind.TERMINAL_OUTPUT and e.payload["tool"]]
        (block,) = blocks
        assert code == 1 and needle in block["text"]
        assert block["tool"] == line.split()[0]
        linked = [s["element_id"] for s in block["spans"]]
        assert element_id("path", "worktree", link) in linked, block
        assert barrier in [f["barrier_id"] for f in box.facts() if f["kind"] == "evidence_seen"]
    finally:
        box.manager.close()
