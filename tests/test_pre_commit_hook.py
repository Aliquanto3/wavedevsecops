"""Story 7.3 : hook pre-commit (gitleaks par `pre-commit run`), refus affiché, `pre-commit install`
refusé (AD-4, AD-9, AD-10, AD-14).

Le hook d'un espace est un processus à part que git lance : les tests sans outils réels posent un
faux hook (il porte le marqueur du vrai pour être reconnu) ; le vrai `pre-commit run` et le vrai
gitleaks tournent dans `test_vrai_hook_pre_commit` quand l'environnement d'exercice et gitleaks
sont disponibles (`WDS_EXERCISE_UV=1`, `WDS_EXERCISE_DATA`, `tools/gitleaks/` provisionné).
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest
from test_terminal_tools import PYTHON, WAIT, Box, no_sync  # noqa: F401 - no_sync : fixture

from wavedevsecops import hooks, toolrun
from wavedevsecops.config import Settings
from wavedevsecops.contracts import element_id
from wavedevsecops.events import Kind
from wavedevsecops.terminal.allowlist import get_allowlist
from wavedevsecops.terminal.parse import Refused, parse_line
from wavedevsecops.toolrun import findings as machine

SCENARIO = Path(__file__).resolve().parent.parent / "content" / "scenarios"
SECRET = SCENARIO / "secret-dans-un-commit.A.yaml"
FILE = "src/inventory/reappro.py"
SENTENCE = (
    "Refusé par le hook pre-commit : gitleaks a trouvé un secret. Le commit n'a pas été créé."
)


def _fake_hook(layout, tmp_path: Path, *, exit_code: int, refusal: dict | None) -> None:
    """Remplace `hooks/pre-commit` par un script qui imprime comme pre-commit, écrit la trace
    du refus (comme le vrai hook) et sort avec `exit_code`. Le marqueur du vrai hook y figure en
    commentaire : l'application le reconnaît."""
    script = tmp_path / "faux_hook.py"
    cache = layout.cache.as_posix()
    body = [
        "import pathlib, sys",
        f"pathlib.Path({cache!r}).mkdir(parents=True, exist_ok=True)",
        "sys.stderr.write('gitleaks...........Failed\\n')",
    ]
    body.append("sys.stderr.write('- hook id: gitleaks\\nFile: src/inventory/reappro.py\\n')")
    if refusal is not None:
        body.append(
            f"pathlib.Path({cache!r}, 'hook-pre-commit.json').write_text({json.dumps(refusal)!r})"
        )
    body.append(f"sys.exit({exit_code})")
    script.write_text("\n".join(body) + "\n", encoding="utf-8")
    hook = layout.hooks / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n# faux hook, comme : -m wavedevsecops.hooks pre-commit\n"
        f'exec "{Path(PYTHON).as_posix()}" "{script.as_posix()}"\n',
        encoding="utf-8",
        newline="\n",
    )
    hook.chmod(0o755)


@pytest.fixture
def box(tmp_path: Path, git_path: Path, no_sync: None) -> Box:  # noqa: F811
    space = Box(Settings(data_dir=tmp_path / "data"), git_path, SECRET, "no_ai")
    try:
        yield space
    finally:
        space.manager.close()


def _outputs(events) -> list[dict]:
    return [e.payload for e in events if e.kind == Kind.TERMINAL_OUTPUT]


def _commits_ahead(space: Box) -> list[str]:
    _op, code, events = space.run("git log --oneline origin/main..HEAD")
    assert code == 0
    return "".join(o["text"] for o in _outputs(events)).splitlines()


# ------------------------------------------------------------------ pose du hook
def test_le_scenario_pose_un_hook_pre_commit_d_une_ligne_sh_en_lf(box: Box) -> None:
    raw = (box.layout.hooks / "pre-commit").read_bytes()
    assert raw == hooks.hook_script("pre-commit", Path(sys.executable)).encode("utf-8")
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert raw.decode("utf-8").splitlines()[1].endswith('-m wavedevsecops.hooks pre-commit "$@"')
    assert not (box.layout.hooks / "pre-receive").exists()  # seul le hook demandé est posé
    assert hooks.pre_commit_installed(box.layout.hooks)
    # Le chemin de Python n'entre pas dans l'empreinte (AD-6) et `refresh` le réécrit.
    assert hooks.canonical_script(raw) == hooks.canonical_script(
        hooks.hook_script("pre-commit", Path("C:/autre/python.exe")).encode("utf-8")
    )
    assert hooks.refresh(box.layout.hooks, Path("/ailleurs/python")) == ["pre-commit"]


def test_la_configuration_du_scenario_ne_lance_que_gitleaks(box: Box) -> None:
    config = (box.layout.repo / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "entry: gitleaks git --pre-commit --staged --no-banner" in config
    assert "language: system" in config and "repo: local" in config
    assert "ruff" not in config and "pytest" not in config
    assert terminal_tools(box) == {"git", "gitleaks", "pre-commit"}


def terminal_tools(space: Box) -> set[str]:
    from wavedevsecops import terminal

    return set(terminal.declared_tools(space.engine))


# ------------------------------------------------------------------ garde (AD-4)
@pytest.mark.parametrize("sub", ["install", "uninstall", "install-hooks"])
def test_pre_commit_install_est_refuse_avec_son_explication(sub: str) -> None:
    allow = get_allowlist(Settings())
    for line in (f"pre-commit {sub}", f"pre-commit {sub} --hook-type pre-push"):
        with pytest.raises(Refused) as refused:
            parse_line(line, allow)
        assert f"« pre-commit {sub} » est refusé" in refused.value.text
        assert "les hooks sont posés par le scénario" in refused.value.text
        assert "Commandes git acceptées" in refused.value.text  # la liste du fichier est citée


def test_les_autres_commandes_pre_commit_restent_inconnues_du_terminal() -> None:
    with pytest.raises(Refused) as refused:
        parse_line("pre-commit run", get_allowlist(Settings()))
    assert "n'est pas une commande de ce terminal" in refused.value.text


# ------------------------------------------------------------------ refus affiché (faux hook)
def test_commit_refuse_bloc_tool_output_alerte_et_aucun_commit(box: Box, tmp_path: Path) -> None:
    _fake_hook(
        box.layout, tmp_path, exit_code=1, refusal={"tool": "gitleaks", "lines": {FILE: [3]}}
    )
    assert box.run(f"git add {FILE}")[1] == 0
    _op, code, events = box.run("git commit -m 'Ajoute la clé'")
    assert code == 1
    outputs = _outputs(events)
    blocks = [o for o in outputs if o["tool"]]
    (block,) = blocks
    assert block["tool"] == "gitleaks" and "Failed" in block["text"] and FILE in block["text"]
    alerts = [o for o in outputs if o["stream"] == "refused"]
    (alert,) = alerts
    assert alert["text"].startswith(SENTENCE)
    (span,) = alert["spans"]
    assert alert["text"][span["start"] : span["end"]] == f"{FILE}:3" == span["text"]
    assert span["element_id"] == element_id("path", "worktree", FILE)
    # Ordre : sortie réelle, code de sortie, alerte ; la sortie de git n'est pas dupliquée.
    streams = [(o["stream"], bool(o["tool"])) for o in outputs]
    assert streams == [("stdout", True), ("exit", False), ("refused", False)]
    assert _commits_ahead(box) == []  # aucun commit dans le graphe
    assert "secret-scan" in [f["barrier_id"] for f in box.facts() if f["kind"] == "evidence_seen"]


def test_refus_d_un_autre_hook_sans_lien_ni_preuve(box: Box, tmp_path: Path) -> None:
    _fake_hook(box.layout, tmp_path, exit_code=1, refusal={"tool": "pre-commit", "lines": {}})
    assert box.run(f"git add {FILE}")[1] == 0
    _op, code, events = box.run("git commit -m x")
    assert code == 1
    (alert,) = [o for o in _outputs(events) if o["stream"] == "refused"]
    assert alert["text"] == "Refusé par le hook pre-commit. Le commit n'a pas été créé."
    assert alert["spans"] == []
    assert not [f for f in box.facts() if f["kind"] == "evidence_seen"]


def test_un_commit_qui_passe_garde_la_sortie_de_git_et_les_refus_ne_collent_pas(
    box: Box, tmp_path: Path
) -> None:
    _fake_hook(
        box.layout, tmp_path, exit_code=1, refusal={"tool": "gitleaks", "lines": {FILE: [3]}}
    )
    assert box.run(f"git add {FILE}")[1] == 0
    assert box.run("git commit -m x")[1] == 1
    # Le secret est retiré : le hook passe, sans trace de refus, et le commit existe.
    _fake_hook(box.layout, tmp_path, exit_code=0, refusal=None)
    (box.layout.repo / FILE).write_text("KEY = 'ok'\n", encoding="utf-8")
    assert box.run(f"git add {FILE}")[1] == 0
    _op, code, events = box.run("git commit -m 'Sans la clé'")
    assert code == 0
    outputs = _outputs(events)
    assert not [o for o in outputs if o["tool"] or o["stream"] == "refused"]
    assert any("Sans la clé" in o["text"] for o in outputs)
    assert len(_commits_ahead(box)) == 1  # le premier commit refusé n'existe pas


def test_no_verify_contourne_le_hook_comme_avec_git(box: Box, tmp_path: Path) -> None:
    _fake_hook(
        box.layout, tmp_path, exit_code=1, refusal={"tool": "gitleaks", "lines": {FILE: [3]}}
    )
    assert box.run(f"git add {FILE}")[1] == 0
    _op, code, events = box.run("git commit --no-verify -m x")
    assert code == 0 and not [o for o in _outputs(events) if o["tool"]]


# ------------------------------------------------------------------ hook : outil manquant
def test_outil_manquant_refuse_en_francais_avec_renvoi_au_diagnostic(box: Box) -> None:
    err = io.StringIO()
    # `pre-commit` n'est pas dans l'environnement d'exercice de cet espace (aucun `uv sync`).
    assert hooks.pre_commit(box.layout.repo, io.StringIO(), err) == hooks.EXIT_REFUSED
    text = err.getvalue()
    assert "Le hook « pre-commit » ne peut pas tourner : pre-commit est indisponible" in text
    assert "Le commit n'a pas été créé. Ouvrez le diagnostic" in text
    assert hooks.read_refusal(box.layout) is None


def test_gitleaks_absent_refuse_en_francais(box: Box, monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(tool_id, *args, **kwargs):  # noqa: ANN001, ANN202
        if tool_id == "pre-commit":
            return toolrun.ToolStatus(tool_id, "ok", "4.7.0", Path(PYTHON), "environment")
        return toolrun.ToolStatus(
            tool_id, "missing", reason="gitleaks est introuvable sur le poste"
        )

    monkeypatch.setattr(toolrun, "resolve", resolve)
    err = io.StringIO()
    assert hooks.pre_commit(box.layout.repo, io.StringIO(), err) == hooks.EXIT_REFUSED
    assert "gitleaks est indisponible (gitleaks est introuvable sur le poste)" in err.getvalue()
    assert "Ouvrez le diagnostic" in err.getvalue()


def test_le_hook_ne_fait_rien_hors_de_repo_ou_sans_configuration(box: Box, tmp_path: Path) -> None:
    err = io.StringIO()
    assert hooks.pre_commit(box.layout.origin, io.StringIO(), err) == 0  # dépôt nu
    (box.layout.repo / ".pre-commit-config.yaml").unlink()
    assert hooks.pre_commit(box.layout.repo, io.StringIO(), err) == 0
    assert err.getvalue() == ""


# ------------------------------------------------------------------ toolrun : environnement
def test_environnement_de_pre_commit_resout_gitleaks_et_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def resolve(tool_id, settings=None, **kwargs):  # noqa: ANN001, ANN202
        return toolrun.ToolStatus(
            tool_id, "ok", "1", tmp_path / tool_id / f"{tool_id}.exe", "provisioned"
        )

    monkeypatch.setattr(toolrun, "resolve", resolve)
    settings = Settings(data_dir=tmp_path / "data")
    base = {"Path": "/usr/bin", "UV_OFFLINE": "1"}
    env = toolrun.hook_environment(base, tmp_path / "venv", settings)
    assert list(env) == ["Path", "UV_OFFLINE", "UV_PROJECT_ENVIRONMENT"]  # une seule clé PATH
    assert env["Path"].split(os.pathsep) == [
        str(tmp_path / "gitleaks"),
        str(tmp_path / "uv"),
        "/usr/bin",
    ]
    assert env["UV_PROJECT_ENVIRONMENT"] == str(tmp_path / "venv")
    assert base == {"Path": "/usr/bin", "UV_OFFLINE": "1"}  # l'entrée n'est pas modifiée


def test_constats_gitleaks_depuis_le_rapport_json(tmp_path: Path) -> None:
    report = json.dumps(
        [
            {"File": "src/a.py", "StartLine": 3, "Secret": "REDACTED"},
            {"File": "src/a.py", "StartLine": 9},
            {"File": "../hors.py", "StartLine": 1},
            {"File": "src/b.py"},
        ]
    )
    found = machine.parse_gitleaks(report, tmp_path)
    assert found.lines == {"src/a.py": frozenset({3, 9})}
    assert machine.parse_gitleaks("[]", tmp_path).lines == {}
    assert machine.parse_gitleaks("pas du json", tmp_path).error
    assert machine.parse_gitleaks("{}", tmp_path).error


def test_machine_gitleaks_code_3_est_un_secret_et_1_une_panne(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Même convention que le pipeline (7.4) : `--exit-code 3` ; autre code non nul = panne."""
    from wavedevsecops import procs

    argv_seen: list[list[str]] = []

    def run(code: int, report: str):  # noqa: ANN202
        def fake(tool_id, args, *, cwd, venv, timeout, settings=None):  # noqa: ANN001, ANN202
            argv_seen.append(list(args))
            path = Path(args[args.index("--report-path") + 1])
            script = (
                f"import pathlib, sys; pathlib.Path({str(path)!r}).write_text({report!r}); "
                f"sys.exit({code})"
            )
            return procs.spawn(
                [PYTHON, "-c", script], env=dict(os.environ), cwd=cwd, timeout=timeout
            )

        monkeypatch.setattr(toolrun, "spawn_tool", fake)
        return machine.collect(
            "gitleaks",
            hooks.GITLEAKS_ARGS,
            repo=tmp_path,
            venv=tmp_path / "venv",
            cache=tmp_path / "cache",
            settings=Settings(data_dir=tmp_path),
            timeout=WAIT,
        )

    found = run(3, '[{"File": "x.py", "StartLine": 2}]')
    assert found.lines == {"x.py": frozenset({2})} and not found.error
    assert argv_seen[0][:4] == ["git", "--pre-commit", "--staged", "--no-banner"]
    assert (
        "--exit-code" in argv_seen[0] and argv_seen[0][argv_seen[0].index("--exit-code") + 1] == "3"
    )
    assert "--redact" in argv_seen[0]
    assert run(0, "").lines == {}
    assert run(1, "").error  # gitleaks en panne : ni lien, ni refus attribué à un secret
    assert not list((tmp_path / "cache").glob("gitleaks-*.json"))  # rapport effacé


# ------------------------------------------------------------------ vrais outils
EXERCISE_DATA = os.environ.get("WDS_EXERCISE_DATA", "")
GITLEAKS = Path(EXERCISE_DATA) / "tools" / "gitleaks" if EXERCISE_DATA else None
REAL = (
    os.environ.get("WDS_EXERCISE_UV") == "1"
    and GITLEAKS is not None
    and any((GITLEAKS / name).is_file() for name in ("gitleaks", "gitleaks.exe"))
)


@pytest.mark.skipif(
    not REAL, reason="WDS_EXERCISE_UV=1 et gitleaks provisionné dans WDS_EXERCISE_DATA"
)
@pytest.mark.parametrize("track", ["no_ai", "llm"])
def test_vrai_hook_pre_commit(git_path: Path, track: str) -> None:
    settings = Settings(data_dir=Path(EXERCISE_DATA))
    space = Box(settings, git_path, SECRET, track)
    try:
        assert space.run(f"git add {FILE}")[1] == 0
        _op, code, events = space.run("git commit -m 'Ajoute la clé'")
        outputs = _outputs(events)
        assert code == 1, outputs
        (block,) = [o for o in outputs if o["tool"]]
        assert block["tool"] == "gitleaks"
        assert "gitleaks" in block["text"] and "Failed" in block["text"]
        assert "AKIA" not in block["text"] or "REDACTED" in block["text"] or FILE in block["text"]
        (alert,) = [o for o in outputs if o["stream"] == "refused"]
        assert alert["text"].startswith(SENTENCE) and f"{FILE}:3" in alert["text"]
        assert [s["element_id"] for s in alert["spans"]] == [element_id("path", "worktree", FILE)]
        assert _commits_ahead(space) == []
        assert "secret-scan" in [
            f["barrier_id"] for f in space.facts() if f["kind"] == "evidence_seen"
        ]

        # Le secret est retiré, le fichier recommité : le hook laisse passer.
        (space.layout.repo / FILE).write_text(
            '"""Accès au service de réapprovisionnement."""\n\nimport os\n\n'
            'AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")\n',
            encoding="utf-8",
        )
        assert space.run(f"git add {FILE}")[1] == 0
        _op, code, events = space.run("git commit -m 'Lit la clé dans l environnement'")
        assert code == 0, _outputs(events)
        assert len(_commits_ahead(space)) == 1
    finally:
        space.manager.close()
