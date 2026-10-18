"""Story 2.8 : enregistrer un fichier (`save_file`), l'ouvrir ailleurs (`open_external`), lire un
diff projeté et les lectures de la vue Code, sur un vrai git et par la file d'opérations."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from test_terminal import WAIT, Space
from test_workspace_api import WS, _call, cookie, instance  # noqa: F401 - fixtures pytest

from wavedevsecops import terminal, wsfs
from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError, parse_element_id
from wavedevsecops.engine import OperationRefused, build_operation, code_intents
from wavedevsecops.gitio import Git
from wavedevsecops.projections.diff import DiffTargetError, parse_diff, read_diff


@pytest.fixture
def space(tmp_path: Path, git_path: Path) -> Iterator[Space]:
    terminal.AFTER_COMMAND_HOOKS.clear()
    code_intents.register_intents()
    s = Space(Settings(data_dir=tmp_path / "data"), git_path)
    s.identify()
    try:
        yield s
    finally:
        s.manager.close()


def _git(space: Space, git_path: Path) -> Git:
    return Git.for_workspace(git_path, space.layout.root, space.settings)


def _status(space: Space, git_path: Path) -> str:
    return _git(space, git_path).internal("status", "--porcelain", cwd=space.layout.repo)


def _save(space: Space, path: str, content: str, base: str | None = None):
    if base is None:
        base = code_intents.content_hash(wsfs.read_bytes(space.layout.repo, path))
    op = build_operation(
        space.engine, "save_file", {"path": path, "content": content, "base_hash": base}
    )
    return op, space.engine.submit(op).result(WAIT)


def _commit(space: Space, path: str, text: str) -> None:
    space.write(path, text)
    assert space.run(f"git add '{path}'").code == 0
    assert space.run(f"git commit -m 'ajout {path}'").code == 0


# --- save_file -------------------------------------------------------------------------------


def test_enregistrer_ecrit_en_lf_et_git_status_voit_le_changement(
    space: Space, git_path: Path
) -> None:
    _commit(space, "a.txt", "un\n")
    _, outcome = _save(space, "a.txt", "deux\r\ntrois\r\n")
    assert outcome.code == 0
    assert (space.layout.repo / "a.txt").read_bytes() == b"deux\ntrois\n"
    assert _status(space, git_path).strip() == "M a.txt"


def test_enregistrer_un_nouveau_fichier_avec_une_empreinte_vide(
    space: Space, git_path: Path
) -> None:
    _, outcome = _save(space, "nouveau.txt", "bonjour\n", base="")
    assert outcome.code == 0
    assert "?? nouveau.txt" in _status(space, git_path)


def test_une_empreinte_perimee_est_refusee_avant_la_file(space: Space) -> None:
    _commit(space, "a.txt", "un\n")
    stale = code_intents.content_hash(b"un\n")
    space.write("a.txt", "modifie ailleurs\n")
    with pytest.raises(OperationRefused) as refused:
        _save(space, "a.txt", "ma version\n", base=stale)
    assert "a changé sur le disque" in refused.value.reason_text
    assert (space.layout.repo / "a.txt").read_text(encoding="utf-8") == "modifie ailleurs\n"


def test_le_disque_qui_bouge_entre_la_reception_et_la_file_est_revu_dans_la_file(
    space: Space,
) -> None:
    _commit(space, "a.txt", "un\n")
    op = build_operation(
        space.engine,
        "save_file",
        {
            "path": "a.txt",
            "content": "ma version\n",
            "base_hash": code_intents.content_hash(b"un\n"),
        },
    )
    space.write("a.txt", "ailleurs\n")  # avant que la file ne prenne l'opération
    outcome = space.engine.submit(op).result(WAIT)
    assert outcome.code == code_intents.EXIT_REFUSED
    assert (space.layout.repo / "a.txt").read_text(encoding="utf-8") == "ailleurs\n"


def test_un_fichier_existant_ne_s_enregistre_pas_avec_une_empreinte_vide(space: Space) -> None:
    _commit(space, "a.txt", "un\n")
    with pytest.raises(OperationRefused):
        _save(space, "a.txt", "x\n", base="")


@pytest.mark.parametrize("path", ["../dehors.txt", ".git/config", "/etc/passwd", "a/../../b"])
def test_un_chemin_hors_du_depot_est_refuse(space: Space, path: str) -> None:
    with pytest.raises(AppError):
        _save(space, path, "x\n", base="")


def test_un_dossier_parent_absent_est_refuse(space: Space) -> None:
    with pytest.raises(AppError):
        _save(space, "absent/f.txt", "x\n", base="")


def test_un_dossier_n_est_pas_un_fichier(space: Space) -> None:
    (space.layout.repo / "dossier").mkdir()
    with pytest.raises(AppError):
        _save(space, "dossier", "x\n", base="")


def test_une_empreinte_qui_n_est_pas_hexadecimale_est_invalide(space: Space) -> None:
    with pytest.raises(OperationRefused):
        build_operation(
            space.engine, "save_file", {"path": "a.txt", "content": "", "base_hash": "../x"}
        )


# --- open_external ---------------------------------------------------------------------------


def test_ouvrir_dans_mon_editeur_resout_le_chemin_par_wsfs(
    space: Space, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[Path] = []
    monkeypatch.setattr(code_intents, "OPENER", opened.append)
    _commit(space, "a.txt", "un\n")
    op = build_operation(space.engine, "open_external", {"path": "a.txt"})
    assert space.engine.submit(op).result(WAIT).code == 0
    assert opened == [(space.layout.repo / "a.txt").resolve()]


def test_ouvrir_dans_mon_editeur_refuse_un_chemin_hors_du_depot(
    space: Space, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[Path] = []
    monkeypatch.setattr(code_intents, "OPENER", opened.append)
    for path in ("../x", ".git/config", "absent.txt"):
        with pytest.raises(AppError):
            build_operation(space.engine, "open_external", {"path": path})
    assert opened == []


def test_le_systeme_qui_n_ouvre_pas_le_fichier_le_dit(
    space: Space, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_path: Path) -> None:
        raise OSError("pas d'application associée")

    monkeypatch.setattr(code_intents, "OPENER", broken)
    _commit(space, "a.txt", "un\n")
    op = build_operation(space.engine, "open_external", {"path": "a.txt"})
    assert space.engine.submit(op).result(WAIT).code == code_intents.EXIT_REFUSED


# --- diff projeté ----------------------------------------------------------------------------


def test_diff_de_l_arbre_de_travail(space: Space, git_path: Path) -> None:
    _commit(space, "a.txt", "un\ndeux\ntrois\n")
    space.write("a.txt", "un\nDEUX\ntrois\nquatre\n")
    view = read_diff(_git(space, git_path), space.layout.repo, "worktree")
    assert view.target == "worktree"
    assert view.target_text == "Arbre de travail (depuis HEAD)"
    [file] = view.files
    assert (file.path, file.status, file.added, file.removed) == ("a.txt", "modified", 2, 1)
    assert file.summary_text == "modifié · +2 −1"
    assert file.element_id == "path:worktree:a.txt"
    lines = [line for hunk in file.hunks for line in hunk.lines]
    assert [(line.kind, line.text) for line in lines] == [
        ("context", "un"),
        ("removed", "deux"),
        ("added", "DEUX"),
        ("context", "trois"),
        ("added", "quatre"),
    ]
    removed = lines[1]
    assert removed.element_id == "diffline:worktree:a.txt:old:2"
    assert removed.old_no == 2 and removed.new_no is None
    assert lines[2].element_id == "diffline:worktree:a.txt:new:2"
    assert removed.a11y_name_text == "Ligne supprimée 2 : deux"
    assert lines[4].a11y_name_text == "Ligne ajoutée 4 : quatre"
    assert "1 ligne supprimée" in file.a11y_name_text
    assert "2 lignes ajoutées" in file.a11y_name_text


def test_tous_les_element_id_du_diff_suivent_la_grammaire_et_sont_uniques(
    space: Space, git_path: Path
) -> None:
    _commit(space, "a b.txt", "x\ny\n")
    space.write("a b.txt", "x\nz\n")
    view = read_diff(_git(space, git_path), space.layout.repo, "worktree")
    ids = [f.element_id for f in view.files] + [
        line.element_id for f in view.files for h in f.hunks for line in h.lines
    ]
    assert len(ids) == len(set(ids)) == 4
    for value in ids:
        parse_element_id(value)
    assert view.files[0].path == "a b.txt"


def test_diff_d_un_commit_et_d_un_premier_commit(space: Space, git_path: Path) -> None:
    git = _git(space, git_path)
    repo = space.layout.repo
    _commit(space, "b.txt", "un\n")
    sha1 = git.internal("rev-parse", "HEAD", cwd=repo).strip()
    space.write("b.txt", "un\ndeux\n")
    assert space.run("git commit -a -m deux").code == 0
    sha2 = git.internal("rev-parse", "HEAD", cwd=repo).strip()
    second = read_diff(git, repo, sha2[:10])
    assert second.target == sha2
    assert second.target_text == f"Commit {sha2[:7]}"
    assert second.files[0].element_id == "path:head:b.txt"
    assert second.files[0].hunks[0].lines[-1].element_id == f"diffline:{sha2}:b.txt:new:2"
    root = read_diff(git, repo, sha1)
    assert root.files[0].status == "new"
    assert root.files[0].summary_text == "nouveau fichier · +1 −0"


def test_diff_vide_et_cible_inconnue(space: Space, git_path: Path) -> None:
    git = _git(space, git_path)
    view = read_diff(git, space.layout.repo, "worktree")
    assert view.files == [] and "Aucun changement" in view.empty_text
    for bad in ("--output=x", "0" * 40, "zzzzzzz"):
        with pytest.raises(DiffTargetError):
            read_diff(git, space.layout.repo, bad)


def test_renommage_suppression_et_binaire(space: Space, git_path: Path) -> None:
    repo = space.layout.repo
    _commit(space, "ancien.txt", "a\nb\nc\nd\ne\nf\n")
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02")
    assert space.run("git add blob.bin").code == 0
    assert space.run("git commit -m binaire").code == 0
    assert space.run("git mv ancien.txt nouveau.txt").code == 0
    (repo / "blob.bin").write_bytes(b"\x00\x09\x09")
    view = read_diff(_git(space, git_path), repo, "worktree")
    by_path = {f.path: f for f in view.files}
    assert by_path["nouveau.txt"].status == "renamed"
    assert by_path["nouveau.txt"].old_path == "ancien.txt"
    assert by_path["nouveau.txt"].summary_text == "renommé depuis ancien.txt · +0 −0"
    assert by_path["blob.bin"].status == "binary"
    assert by_path["blob.bin"].summary_text == "fichier binaire"
    assert by_path["blob.bin"].hunks == []


def test_les_marqueurs_de_conflit_sont_signales() -> None:
    text = (
        "diff --git a/f.txt b/f.txt\n--- a/f.txt\n+++ b/f.txt\n@@ -1,1 +1,5 @@\n"
        "+<<<<<<< HEAD\n+nous\n+=======\n+eux\n+>>>>>>> feature\n"
    )
    [file] = parse_diff(text, "worktree").files
    flags = [line.conflict for line in file.hunks[0].lines]
    assert flags == [True, False, True, False, True]


def test_un_diff_trop_long_est_coupe_et_le_dit(monkeypatch: pytest.MonkeyPatch) -> None:
    from wavedevsecops.projections import diff

    monkeypatch.setattr(diff, "MAX_LINES", 3)
    body = "".join(f"+l{i}\n" for i in range(10))
    text = f"diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -0,0 +1,10 @@\n{body}"
    view = parse_diff(text, "worktree")
    assert view.truncated and "coupé" in view.truncated_text
    assert sum(len(h.lines) for f in view.files for h in f.hunks) == 3


# --- lectures HTTP ---------------------------------------------------------------------------


def test_lectures_de_la_vue_code(tmp_path, instance, cookie) -> None:  # noqa: F811, ANN001
    root = tmp_path / "data" / "workspaces" / "llm" / "bac-a-sable-libre.A" / "repo"
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "m.py").write_bytes("café = 1\r\n".encode())
    (root / "blob.bin").write_bytes(b"\x00\xff\x00")
    (root / ".venv").mkdir(exist_ok=True)
    (root / ".venv" / "x.txt").write_text("x", encoding="utf-8")
    base = f"/api/ws/{WS}/code"

    status, tree = _call(instance, "GET", f"{base}/tree", cookie)
    assert status == 200
    assert "src/m.py" in tree["files"] and "blob.bin" in tree["files"]
    assert not any(p.startswith((".git/", ".venv/")) for p in tree["files"])

    status, file = _call(instance, "GET", f"{base}/file?path=src/m.py", cookie)
    assert status == 200 and file["editable"]
    assert file["content"] == "café = 1\n"  # LF, même si le disque porte CRLF
    assert file["hash"] == code_intents.content_hash("café = 1\r\n".encode())

    status, blob = _call(instance, "GET", f"{base}/file?path=blob.bin", cookie)
    assert status == 200 and not blob["editable"] and "n'est pas du texte" in blob["note_text"]

    for bad in ("absent.txt", "../x", ".git/config"):
        status, body = _call(instance, "GET", f"{base}/file?path={bad}", cookie)
        assert status == 404 and body["reason_text"]

    status, diff = _call(instance, "GET", f"{base}/diff", cookie)
    assert status == 200 and diff["target"] == "worktree"
    status, body = _call(instance, "GET", f"{base}/diff?target=nimportequoi", cookie)
    assert status == 404 and "introuvable" in body["reason_text"]


def test_enregistrer_par_http_puis_conflit(tmp_path, instance, cookie) -> None:  # noqa: F811, ANN001
    root = tmp_path / "data" / "workspaces" / "llm" / "bac-a-sable-libre.A" / "repo"
    (root / "n.txt").write_text("un\n", encoding="utf-8")
    base = f"/api/ws/{WS}"
    _, file = _call(instance, "GET", f"{base}/code/file?path=n.txt", cookie)
    body = {"path": "n.txt", "content": "deux\n", "base_hash": file["hash"]}
    status, accepted = _call(instance, "POST", f"{base}/save_file", cookie, body)
    assert status == 202 and accepted["op_id"]
    deadline = __import__("time").monotonic() + WAIT
    while (root / "n.txt").read_text(encoding="utf-8") != "deux\n":
        assert __import__("time").monotonic() < deadline
        __import__("time").sleep(0.05)
    # La même empreinte ne correspond plus au disque : refus 409, texte en français.
    status, refused = _call(instance, "POST", f"{base}/save_file", cookie, body)
    assert status == 409 and "a changé sur le disque" in refused["reason_text"]
    status, _ = _call(instance, "POST", f"{base}/save_file", cookie, {"path": "n.txt"})
    assert status == 422
