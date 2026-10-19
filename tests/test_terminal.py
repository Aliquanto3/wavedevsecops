"""Terminal (Story 2.4) sur un vrai git et un vrai bac à sable, par la file d'opérations."""

from __future__ import annotations

import http.client
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from test_procs_spawn import alive, wait_dead
from test_workspace_api import Stream, _call

from wavedevsecops import cli, gitio, terminal
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    OpContext,
    Operation,
    OperationRefused,
    WorkspaceEngine,
    WorkspaceManager,
    prepare_workspace,
)
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.terminal import GitCommand, TerminalLine, build_terminal_line
from wavedevsecops.wsfs import Layout

FREE = Path(__file__).resolve().parent.parent / "content" / "scenarios" / "bac-a-sable-libre.A.yaml"
WS = "llm.bac-a-sable-libre.A"
WAIT = 60.0
PYTHON = getattr(sys, "_base_executable", sys.executable)


@dataclass
class Result:
    op_id: str
    code: int | None
    events: list[Envelope]

    @property
    def output(self) -> list[tuple[str, str, str]]:
        return [
            (e.payload["stream"], e.payload["text"], e.payload["lang"])
            for e in self.events
            if e.kind == Kind.TERMINAL_OUTPUT and e.op_id == self.op_id
        ]

    def text(self, stream: str | None = None) -> str:
        return "".join(t for s, t, _ in self.output if stream in (None, s))

    @property
    def streams(self) -> list[str]:
        return [s for s, _, _ in self.output]


class Space:
    """Un espace ouvert, avec le journal de ses événements et un terminal."""

    def __init__(self, settings: Settings, git_path: Path) -> None:
        self.settings = settings
        prepare_workspace(
            load_scenario(FREE, settings), "llm", settings=settings, git_path=git_path
        )
        self.manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        self.engine: WorkspaceEngine = self.manager.get(WS)
        self.layout: Layout = self.manager.layout(WS)
        self.events: list[Envelope] = []
        self.manager.events(WS).attach(None, self.events.append)
        # La projection d'ouverture est publiée par le fil de la file : on l'attend.
        deadline = time.monotonic() + WAIT
        while len(self.events) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)

    def start(self, line: str):
        op = build_terminal_line(self.engine, TerminalLine(line=line))
        return op, self.engine.submit(op)

    def run(self, line: str) -> Result:
        op, future = self.start(line)
        outcome = future.result(WAIT)
        exits = [e for e in self.events if e.kind == Kind.OP_EXIT and e.op_id == op.op_id]
        code = exits[-1].payload["code"] if exits else outcome.code
        return Result(op.op_id, code, [e for e in self.events if e.op_id == op.op_id])

    def wait_output(self, op_id: str, needle: str) -> None:
        deadline = time.monotonic() + WAIT
        while time.monotonic() < deadline:
            text = "".join(
                e.payload["text"]
                for e in list(self.events)
                if e.kind == Kind.TERMINAL_OUTPUT and e.op_id == op_id
            )
            if needle in text:
                return
            time.sleep(0.02)
        raise AssertionError(f"« {needle} » jamais vu dans la sortie")

    def write(self, path: str, text: str) -> None:
        (self.layout.repo / path).write_text(text, encoding="utf-8", newline="\n")

    def identify(self) -> None:
        assert self.run("git config user.name 'Ada Lovelace'").code == 0
        assert self.run("git config user.email ada@example.org").code == 0

    def install_hold_hook(self, tmp_path: Path) -> Path:
        """Hook `pre-commit` qui pose un `index.lock`, annonce son PID puis attend longtemps."""
        pid_file = tmp_path / "hold.pid"
        script = tmp_path / "hold.py"
        script.write_text(
            "import os, pathlib, sys, time\n"
            f"pathlib.Path({str(self.layout.repo / '.git' / 'index.lock')!r}).write_text('x')\n"
            f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
            "print('retenu', flush=True)\n"
            "time.sleep(120)\n",
            encoding="utf-8",
        )
        hook = self.layout.hooks / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(
            f'#!/bin/sh\nexec "{Path(PYTHON).as_posix()}" "{script.as_posix()}"\n',
            encoding="utf-8",
            newline="\n",
        )
        hook.chmod(0o755)
        return pid_file


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def space(settings: Settings, git_path: Path) -> Iterator[Space]:
    terminal.AFTER_COMMAND_HOOKS.clear()
    s = Space(settings, git_path)
    try:
        yield s
    finally:
        s.manager.close()
        terminal.AFTER_COMMAND_HOOKS.clear()


@pytest.fixture
def english(git_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(gitio._LANGUAGES, git_path, gitio.GitLanguage("en"))


def test_git_status_dans_repo_avec_la_sequence_de_la_file(space: Space, english: None) -> None:
    result = space.run("git status")
    assert result.code == 0
    assert "On branch main" in result.text("stdout")
    assert set(result.streams) == {"stdout"}
    kinds = [e.kind.value for e in result.events]
    assert kinds[:3] == ["engine_state", "op_started", "terminal_output"]
    assert kinds[-3:] == ["op_exit", "state_projected", "engine_state"]
    assert {lang for _, _, lang in result.output} == {"en"}


def test_git_parle_francais_quand_la_locale_existe(
    space: Space, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    language = gitio.probe_language(git_path)
    if language.lang != "fr":
        # La CI Linux génère fr_FR.UTF-8 : le chemin français y est obligatoire. Git for
        # Windows et macOS ne fournissent pas les catalogues de git : le test y est ignoré.
        if os.environ.get("CI") and sys.platform.startswith("linux"):
            pytest.fail("la CI Linux doit fournir une locale française à git")
        pytest.skip("aucune locale française de git sur ce poste (git parle anglais)")
    monkeypatch.setitem(gitio._LANGUAGES, git_path, gitio.GitLanguage("en"))
    english = space.run("git status")
    monkeypatch.setitem(gitio._LANGUAGES, git_path, language)
    result = space.run("git status")
    # La locale française change vraiment le texte de git (sans le comparer à une phrase fixe).
    assert result.text("stdout") != english.text("stdout")
    assert {lang for _, _, lang in result.output} == {"fr"}


def test_sans_locale_francaise_git_parle_anglais(
    space: Space, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(gitio._LANGUAGES, git_path, gitio.GitLanguage("en"))
    result = space.run("git log --oneline")
    assert "Ajoute le README" in result.text()
    assert {lang for _, _, lang in result.output} == {"en"}


def test_stderr_et_code_de_sortie_non_nul(space: Space, english: None) -> None:
    result = space.run("git switch branche-absente")
    assert result.code == 128 or result.code == 1
    assert "invalid reference" in result.text("stderr")
    assert result.streams[-1] == "exit"
    assert result.text("exit") == f"Code de sortie : {result.code}"
    assert "stdout" not in result.streams


def test_commit_sans_identite_configuree_prend_celle_de_l_apprenant(
    space: Space, english: None
) -> None:
    # Aucun `git config` préalable : l'identité vient du contexte apprenant, pas du poste.
    space.write("README.md", "# identité\n")
    committed = space.run("git commit -am 'sans identité'")
    assert committed.code == 0, committed.text()
    author = space.run("git log -1 '--format=%an|%ae|%cn'")
    assert author.text("stdout").strip() == (
        f"{gitio.LEARNER_NAME}|{gitio.LEARNER_EMAIL}|{gitio.LEARNER_NAME}"
    )
    # Un `git config user.name` tapé (portée du dépôt) prime sur l'identité par défaut.
    space.identify()
    assert space.run("git commit --allow-empty -m 'ada'").code == 0
    assert space.run("git log -1 --format=%an").text("stdout").strip() == "Ada Lovelace"


def test_commit_sans_message_garde_la_sortie_de_git_puis_explique(
    space: Space, english: None
) -> None:
    result = space.run("git commit --allow-empty")
    assert result.code not in (0, None)
    assert "empty commit message" in result.text("stderr").lower()
    assert result.streams[-2:] == ["exit", "app"]
    assert result.text("app") == 'git attend un message de commit. Ajoutez `-m "…"`.'
    tagged = space.run("git tag -a v1")
    assert tagged.code not in (0, None)
    assert tagged.streams[-1] == "app"
    ok = space.run("git tag -a v1 -m 'première version'")
    assert ok.code == 0 and "app" not in ok.streams


def test_revert_amend_et_merge_continue_aboutissent_sans_editeur(
    space: Space, english: None
) -> None:
    assert space.run("git revert HEAD").code == 0
    assert space.run("git commit --amend").code == 0
    assert "Revert" in space.run("git log --oneline -1").text()

    assert space.run("git switch -c autre").code == 0
    space.write("README.md", "# version autre\n")
    assert space.run("git commit -am 'autre'").code == 0
    assert space.run("git switch main").code == 0
    space.write("README.md", "# version main\n")
    assert space.run("git commit -am 'principal'").code == 0
    merged = space.run("git merge autre")
    assert merged.code == 1 and "CONFLICT" in merged.text("stdout")
    space.write("README.md", "# résolu\n")
    assert space.run("git add README.md").code == 0
    assert space.run("git merge --continue").code == 0

    assert space.run("git switch -c base HEAD~1").code == 0
    space.write("README.md", "# base\n")
    assert space.run("git commit -am 'base'").code == 0
    rebased = space.run("git rebase main")
    assert rebased.code == 1
    space.write("README.md", "# rebase résolu\n")
    assert space.run("git add README.md").code == 0
    assert space.run("git rebase --continue").code == 0


def test_ligne_refusee_a_l_ecran_sans_lancer_git(space: Space) -> None:
    result = space.run("git status | cat")
    assert result.streams == ["refused"]
    assert result.code == 2
    assert "Commandes git acceptées" in result.text("refused")
    gone = space.run("cd src")
    assert gone.streams == ["refused"] and "racine du dépôt" in gone.text()
    assert not (space.layout.repo / "src" / "x").exists()


def test_ligne_vide_ne_fait_rien(space: Space) -> None:
    before = len(space.events)
    op, future = space.start("   ")
    assert future.result(WAIT).projection is None
    assert len(space.events) == before and op.intent == "terminal_line"


def test_push_pull_fetch_agissent_sur_origin_et_refusent_un_chemin(
    space: Space, english: None, tmp_path: Path
) -> None:
    calls: list[tuple[str, int | None]] = []

    def hook(ctx: OpContext, command: GitCommand, code: int | None) -> None:
        calls.append((command.sub, code))

    terminal.AFTER_COMMAND_HOOKS.append(hook)
    assert space.run("git fetch origin").code == 0
    assert space.run("git pull origin main").code == 0
    assert space.run("git push origin main").code == 0
    assert calls == [("fetch", 0), ("pull", 0), ("push", 0)]
    assert space.run("git remote get-url origin").code == 0
    for line in (
        f"git push {tmp_path.as_posix()}",
        "git push https://example.org/depot.git",
        "git pull ../origin.git",
        "git fetch main",
        f"git remote show {tmp_path.as_posix()}",
        "git remote show https://example.org/depot.git",
        "git remote get-url ../origin.git",
    ):
        refused = space.run(line)
        assert refused.streams == ["refused"], line
        assert "n'est pas un remote du dépôt" in refused.text()
        assert "origin" in refused.text()
    assert len(calls) == 3  # un refus n'appelle pas les crochets


def test_push_sur_une_branche_protegee_est_refuse_et_explique(
    space: Space, english: None, git_path: Path
) -> None:
    """Story 3.5 : le hook `pre-receive` refuse (`remote:`), le terminal dit pourquoi."""
    from wavedevsecops import github_sim, hooks, wsfs
    from wavedevsecops.contracts.github import BranchProtection

    space.identify()
    space.write("notes.md", "notes\n")
    assert space.run("git add notes.md").code == 0
    assert space.run("git commit -m notes").code == 0
    git = gitio.Git.for_workspace(git_path, space.layout.root, space.settings)
    git.internal("config", "core.hooksPath", "../hooks", cwd=space.layout.origin)
    wsfs.write_executable(
        space.layout.hooks, "pre-receive", hooks.hook_script("pre-receive", Path(sys.executable))
    )
    github_sim.set_protection(git, space.layout, BranchProtection(branch="main"))
    refused = space.run("git push origin main")
    assert refused.code != 0
    assert "remote:" in refused.text("stderr")
    assert refused.text("app").strip() == (
        "Refusé par la protection de `main` : tout passe par une PR."
    )
    assert space.run("git switch -c feature").code == 0
    ok = space.run("git push origin feature")
    assert ok.code == 0 and ok.text("app") == ""


def _protect_main(space: Space, git_path: Path) -> gitio.Git:
    from wavedevsecops import github_sim, hooks, wsfs
    from wavedevsecops.contracts.github import BranchProtection

    git = gitio.Git.for_workspace(git_path, space.layout.root, space.settings)
    git.internal("config", "core.hooksPath", "../hooks", cwd=space.layout.origin)
    wsfs.write_executable(
        space.layout.hooks, "pre-receive", hooks.hook_script("pre-receive", Path(sys.executable))
    )
    github_sim.set_protection(git, space.layout, BranchProtection(branch="main"))
    return git


def test_un_refus_sans_avance_rapide_n_est_pas_attribue_a_la_protection(
    space: Space, english: None, git_path: Path
) -> None:
    """Revue 3.5 : git refuse un push sans avance rapide avant le hook ; le terminal ne
    l'attribue pas à la protection. Avec `--force`, le hook refuse, et le terminal le dit."""
    space.identify()
    space.write("a.md", "a\n")
    assert space.run("git add a.md").code == 0
    assert space.run("git commit -m a").code == 0
    assert space.run("git push origin main").code == 0
    git = _protect_main(space, git_path)
    git.internal("reset", "-q", "--hard", "HEAD~1", cwd=space.layout.repo)
    space.write("b.md", "b\n")
    assert space.run("git add b.md").code == 0
    assert space.run("git commit -m b").code == 0
    behind = space.run("git push origin main")
    assert behind.code != 0
    assert "protégée" not in behind.text("stderr") and behind.text("app") == ""
    forced = space.run("git push --force origin main")
    assert forced.code != 0
    assert "protection de `main`" in forced.text("app")


def test_push_all_explique_la_protection(space: Space, english: None, git_path: Path) -> None:
    """Revue 3.5 : `git push --all` depuis une autre branche vise aussi `main`."""
    space.identify()
    space.write("c.md", "c\n")
    assert space.run("git add c.md").code == 0
    assert space.run("git commit -m c").code == 0
    _protect_main(space, git_path)
    assert space.run("git switch -c feature").code == 0
    refused = space.run("git push --all origin")
    assert refused.code != 0
    assert "protection de `main`" in refused.text("app")


def test_le_terminal_repare_un_hook_dont_python_a_disparu(
    space: Space, english: None, git_path: Path
) -> None:
    """Revue 3.5 : un hook qui vise un Python disparu refuserait tout push ; le terminal le
    réécrit avec l'interpréteur de l'application avant `git push`."""
    from wavedevsecops import hooks, wsfs

    space.identify()
    _protect_main(space, git_path)
    stale = hooks.hook_script("pre-receive", space.layout.root / "ancien-venv" / "python")
    wsfs.write_executable(space.layout.hooks, "pre-receive", stale)
    assert space.run("git switch -c libre").code == 0
    space.write("d.md", "d\n")
    assert space.run("git add d.md").code == 0
    assert space.run("git commit -m d").code == 0
    assert space.run("git push origin libre").code == 0
    assert (space.layout.hooks / "pre-receive").read_text(encoding="utf-8") == (
        hooks.hook_script("pre-receive", Path(sys.executable))
    )


def test_en_quiz_altered_seules_les_lectures_passent(space: Space, english: None) -> None:
    def alter(ctx: OpContext) -> int:
        ctx.set_rest_state("quiz_altered")
        return 0

    space.engine.submit(Operation("quiz_test", alter)).result(WAIT)
    assert space.run("git status").code == 0
    assert space.run("git log --oneline").code == 0
    for line in ("git add .", "git commit -m x", "git branch feature", "git stash", "git push"):
        with pytest.raises(OperationRefused) as refused:
            space.start(line)
        assert "état modifié par le quiz" in refused.value.reason_text
    # Une ligne refusée par la garde s'affiche toujours (aucune écriture).
    assert space.run("git status ; ls").streams == ["refused"]


def test_aucune_commande_n_attend_une_saisie(space: Space, english: None) -> None:
    for line in (
        "git log",
        "git branch",
        "git show HEAD",
        "git diff",
        "git commit --allow-empty",
        "git tag -a v9",
        "git merge --abort",
        "git rebase --continue",
    ):
        started = time.monotonic()
        result = space.run(line)
        assert result.code is not None, line
        assert time.monotonic() - started < WAIT, line


def test_ctrl_c_arrete_l_arbre_et_supprime_l_index_lock(
    space: Space, tmp_path: Path, english: None
) -> None:
    pid_file = space.install_hold_hook(tmp_path)
    op, future = space.start("git commit --allow-empty -m x")
    space.wait_output(op.op_id, "retenu")
    lock = space.layout.repo / ".git" / "index.lock"
    assert lock.exists()
    pid = int(pid_file.read_text())
    assert alive(pid)
    assert space.engine.interrupt() is True  # intention `interrupt`, hors file
    future.result(WAIT)
    result = Result(op.op_id, None, [e for e in space.events if e.op_id == op.op_id])
    assert result.text("app") == "Commande interrompue."
    exit_event = next(e for e in result.events if e.kind == Kind.OP_EXIT)
    assert exit_event.payload["code"] == terminal.EXIT_INTERRUPTED
    assert wait_dead(pid), "le processus du hook a survécu à Ctrl+C"
    assert not lock.exists()
    # Après l'arrêt, l'espace répond de nouveau : la relecture de l'état a eu lieu.
    assert any(e.kind == Kind.STATE_PROJECTED and e.op_id == op.op_id for e in space.events)
    assert space.engine.interrupt() is False  # rien en cours
    (space.layout.hooks / "pre-commit").unlink()
    assert space.run("git commit --allow-empty -m y").code == 0


def test_delai_depasse_arrete_l_arbre(tmp_path: Path, git_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", terminal_timeout_s=2.0)
    space = Space(settings, git_path)
    try:
        pid_file = space.install_hold_hook(tmp_path)
        result = space.run("git commit --allow-empty -m x")
        assert result.code == terminal.EXIT_TIMEOUT
        assert result.text("app") == "La commande a dépassé 2 s : elle a été arrêtée."
        assert not (space.layout.repo / ".git" / "index.lock").exists()
        if pid_file.exists():
            assert wait_dead(int(pid_file.read_text()))
    finally:
        space.manager.close()


def test_la_mise_en_veille_interrompt_la_commande(
    space: Space, tmp_path: Path, english: None
) -> None:
    pid_file = space.install_hold_hook(tmp_path)
    op, future = space.start("git commit --allow-empty -m x")
    space.wait_output(op.op_id, "retenu")
    pid = int(pid_file.read_text())
    space.manager.sleep(WS)  # la veille n'attend pas 120 s : l'arbre est arrêté
    assert future.done()
    assert wait_dead(pid)
    assert not (space.layout.repo / ".git" / "index.lock").exists()


def test_la_sortie_arrive_au_fil_de_l_eau(space: Space, tmp_path: Path, english: None) -> None:
    """Le premier morceau est publié alors que la commande tourne encore."""
    space.install_hold_hook(tmp_path)
    op, future = space.start("git commit --allow-empty -m x")
    space.wait_output(op.op_id, "retenu")
    assert not future.done()
    assert not any(e.kind == Kind.OP_EXIT and e.op_id == op.op_id for e in space.events)
    space.engine.interrupt()
    future.result(WAIT)


def test_intention_enregistree_une_seule_fois() -> None:
    from wavedevsecops.engine import INTENTS

    terminal.register_intents()
    terminal.register_intents()
    assert INTENTS["terminal_line"].model is TerminalLine


def test_validation_de_l_intention(space: Space) -> None:
    from wavedevsecops.engine import InvalidIntent, build_operation

    terminal.register_intents()
    with pytest.raises(InvalidIntent):
        build_operation(space.engine, "terminal_line", {"line": "x" * 5000})
    with pytest.raises(InvalidIntent):
        build_operation(space.engine, "terminal_line", {})


@pytest.fixture
def server(tmp_path: Path, git_path: Path) -> Iterator[cli.Instance]:
    settings = Settings(data_dir=tmp_path / "data")
    prepare_workspace(load_scenario(FREE, settings), "llm", settings=settings, git_path=git_path)
    inst = cli.start_instance(settings)
    try:
        yield inst
    finally:
        inst.stop()


def test_intentions_terminal_line_et_interrupt_par_http(
    server: cli.Instance, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(gitio._LANGUAGES, git_path, gitio.GitLanguage("en"))
    conn = http.client.HTTPConnection(cli.HOST, server.port, timeout=WAIT)
    conn.request("GET", f"/?t={server.token}")
    reply = conn.getresponse()
    reply.read()
    conn.close()
    cookie = {"Cookie": reply.getheader("Set-Cookie", "").split(";")[0]}
    path = f"/api/ws/{WS}"
    stream = Stream(server, cookie)
    try:
        line = {"line": "git status"}
        status, body = _call(server, "POST", f"{path}/terminal_line", cookie, line)
        assert status == 202
        seen = stream.until("op_exit", body["op_id"])
        texts = [e["payload"]["text"] for e in seen if e["kind"] == "terminal_output"]
        assert "On branch main" in "".join(texts)
        status, body = _call(server, "POST", f"{path}/interrupt", cookie, {})
        assert (status, body["interrupted"]) == (202, False)  # rien en cours
        piped = {"line": "git status | cat"}
        status, body = _call(server, "POST", f"{path}/terminal_line", cookie, piped)
        assert status == 202
        seen = stream.until("op_exit", body["op_id"])
        streams = [e["payload"]["stream"] for e in seen if e["kind"] == "terminal_output"]
        assert streams == ["refused"]
        status, _ = _call(server, "POST", f"{path}/terminal_line", cookie, {})
        assert status == 422
    finally:
        stream.close()
