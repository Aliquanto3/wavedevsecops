"""Commandes de fichiers du terminal (Story 2.5) : garde, exécution et confinement."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_terminal import Space, settings, space  # noqa: F401  (fixtures)

from wavedevsecops import wsfs
from wavedevsecops.config import Settings
from wavedevsecops.terminal import files
from wavedevsecops.terminal.allowlist import get_allowlist
from wavedevsecops.terminal.parse import FileCommand, Refused, parse_line

ALLOW = get_allowlist(Settings())


def sh(root: Path, line: str) -> files.FileResult:
    """Exécute une ligne de fichiers dans `root`, comme le terminal."""
    command = parse_line(line, ALLOW)
    assert isinstance(command, FileCommand), line
    return files.execute(root, command, ALLOW)


def text(result: files.FileResult, stream: str | None = None) -> str:
    return "".join(t for t, s in result.lines if stream in (None, s))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text("SECRET-GIT", encoding="utf-8")
    return repo


def symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError, NotImplementedError:
        pytest.skip("liens symboliques non disponibles sur ce poste")


# --- garde -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "read"),
    [
        ("ls", True),
        ("ls -a src", True),
        ("cat a.txt b.txt", True),
        ("echo bonjour", True),
        ("echo bonjour > a.txt", False),
        ("echo 'a > b' >> a.txt", False),
        ("touch a", False),
        ("mkdir -p a/b", False),
        ("rm -rf build", False),
        ("mv a b", False),
        ("cp -r a b", False),
        ("pwd", True),
        ("clear", True),
    ],
)
def test_lignes_de_fichiers_admises(line: str, read: bool) -> None:
    command = parse_line(line, ALLOW)
    assert isinstance(command, FileCommand)
    assert command.read is read


@pytest.mark.parametrize(
    ("line", "needle"),
    [
        ("ls > f", "redirection"),
        ("cat a > f", "redirection"),
        ("echo a > f > g", "redirection"),
        ("echo a > f b", "redirection"),
        ("echo a >", "fichier"),
        ("> f", ">"),
        ("ls -l", "-l"),
        ("rm -x a", "-x"),
        ("rm", "au moins"),
        ("mv a", "au moins"),
        ("ls a b", "trop"),
        ("pwd x", "trop"),
        ("rm a | cat", "|"),
        ("cat $HOME/x", "$HOME"),
        ("chmod 777 a", "n'est pas une commande"),
        ("sed -i s/a/b/ f", "n'est pas une commande"),
    ],
)
def test_lignes_de_fichiers_refusees(line: str, needle: str) -> None:
    with pytest.raises(Refused) as info:
        parse_line(line, ALLOW)
    assert needle in info.value.text
    assert "Commandes de fichiers acceptées" in info.value.text


def test_la_liste_citee_contient_les_commandes_de_fichiers() -> None:
    cited = ALLOW.accepted()
    for name in ("ls", "cat", "echo", "touch", "mkdir", "rm", "mv", "cp", "pwd", "clear"):
        assert name in ALLOW.files and name in cited


def test_echo_prend_les_tirets_pour_du_texte() -> None:
    command = parse_line("echo -n bonjour", ALLOW)
    assert isinstance(command, FileCommand)
    assert command.args == ("-n", "bonjour") and not command.options


def test_git_garde_ses_refus_de_redirection() -> None:
    with pytest.raises(Refused):
        parse_line("git status > f", ALLOW)


# --- exécution -------------------------------------------------------------------------------


def test_echo_ecrit_en_lf_sans_bom_puis_ajoute(root: Path) -> None:
    assert sh(root, "echo première ligne > a.txt").code == 0
    assert sh(root, 'echo "deuxième" >> a.txt').code == 0
    assert (root / "a.txt").read_bytes() == "première ligne\ndeuxième\n".encode()
    assert sh(root, "echo remplacé > a.txt").code == 0
    assert (root / "a.txt").read_bytes() == b"remplac\xc3\xa9\n"
    assert not (root / "a.txt").read_bytes().startswith(b"\xef\xbb\xbf")


def test_cat_lit_et_signale_l_absent(root: Path) -> None:
    sh(root, "echo salut > a.txt")
    assert text(sh(root, "cat a.txt")) == "salut\n"
    missing = sh(root, "cat a.txt absent.txt")
    assert missing.code == 1 and "n'existe pas" in text(missing, "app")
    sh(root, "mkdir d")
    assert "dossier" in text(sh(root, "cat d"), "app")


def test_ls_trie_marque_les_dossiers_et_cache_les_points(root: Path) -> None:
    sh(root, "mkdir src")
    sh(root, "touch b.txt A.txt .env")
    assert text(sh(root, "ls")) == "A.txt\nb.txt\nsrc/\n"
    assert text(sh(root, "ls -a")) == ".env\nA.txt\nb.txt\nsrc/\n"
    assert text(sh(root, "ls b.txt")) == "b.txt\n"
    assert sh(root, "ls absent").code == 1


def test_touch_mkdir_pwd(root: Path) -> None:
    assert sh(root, "mkdir a").code == 0
    assert sh(root, "mkdir a").code == 1
    assert sh(root, "mkdir x/y").code == 1
    assert sh(root, "mkdir -p x/y/z").code == 0 and (root / "x/y/z").is_dir()
    assert sh(root, "mkdir -p x/y").code == 0
    assert sh(root, "touch x/y/f.txt").code == 0 and (root / "x/y/f.txt").read_bytes() == b""
    assert text(sh(root, "pwd")) == "/repo\n"
    assert sh(root, "clear").lines == []


def test_rm_mv_cp_de_base(root: Path) -> None:
    sh(root, "echo un > a.txt")
    assert sh(root, "cp a.txt b.txt").code == 0
    assert (root / "b.txt").read_text(encoding="utf-8") == "un\n"
    assert sh(root, "mkdir d").code == 0
    assert sh(root, "mv b.txt d").code == 0 and (root / "d/b.txt").is_file()
    assert sh(root, "mv a.txt c.txt").code == 0 and not (root / "a.txt").exists()
    assert sh(root, "rm d").code == 1 and "-r" in text(sh(root, "rm d"), "app")
    assert sh(root, "rm -r d").code == 0 and not (root / "d").exists()
    assert sh(root, "rm nope").code == 1
    assert sh(root, "rm -f nope").code == 0
    assert sh(root, "cp d2 e").code == 1
    sh(root, "mkdir -p s/t")
    sh(root, "touch s/t/f")
    assert sh(root, "cp s s2").code == 1  # dossier sans -r
    assert sh(root, "cp -r s s2").code == 0 and (root / "s2/t/f").is_file()
    assert sh(root, "cp -r s s/t/dedans").code == 1  # copie dans lui-même
    assert sh(root, "mv s s/t").code == 1  # déplacement dans lui-même


def test_globs_dans_rm_mv_cp_seulement(root: Path) -> None:
    sh(root, "touch a.log b.log c.txt .hidden.log")
    sh(root, "mkdir logs")
    assert sh(root, "cp *.log logs").code == 0
    assert sorted(p.name for p in (root / "logs").iterdir()) == ["a.log", "b.log"]
    assert sh(root, "mv ?.log logs/").code == 0
    assert not (root / "a.log").exists()
    sh(root, "touch a.log b.log")
    assert sh(root, "rm *.log").code == 0
    assert not (root / "a.log").exists() and (root / ".hidden.log").exists()
    assert sh(root, "rm *.nope").code == 1
    assert "aucun fichier" in text(sh(root, "rm *.nope"), "app")
    assert sh(root, "rm -f *.nope").code == 0
    # Aucune autre commande ne développe de glob : `cat *.txt` cherche un fichier du même nom.
    assert "n'existe pas" in text(sh(root, "cat *.txt"), "app")
    assert (root / "c.txt").exists()
    # Plusieurs sources : la destination doit être un dossier.
    sh(root, "touch x1 x2")
    assert "dossier existant" in text(sh(root, "mv x* c.txt"), "app")


def test_glob_dans_des_sous_dossiers_et_jamais_git(root: Path) -> None:
    sh(root, "mkdir -p src/a src/b")
    sh(root, "touch src/a/f.py src/b/g.py src/b/h.txt")
    assert wsfs.expand_glob(root, "src/*/*.py") == ["src/a/f.py", "src/b/g.py"]
    assert wsfs.expand_glob(root, "*") == ["src"]
    assert wsfs.expand_glob(root, ".*") == []  # `.git` n'est jamais pris
    assert sh(root, "rm -rf *").code == 0
    assert (root / ".git" / "config").read_text(encoding="utf-8") == "SECRET-GIT"


# --- confinement -----------------------------------------------------------------------------


OUTSIDE_LINES = [
    "cat ../secret.txt",
    "ls ..",
    "ls ../..",
    "echo x > ../out.txt",
    "echo x >> ../out.txt",
    "touch ../out.txt",
    "mkdir ../d",
    "rm ../secret.txt",
    "rm -rf ../dossier",
    "mv ../secret.txt .",
    "mv a ../out.txt",
    "cp ../secret.txt a",
    "cp a ../out.txt",
    "cat /etc/passwd",
    "echo x > /tmp/out.txt",
    "rm -rf /",
    "cp a /tmp/x",
    "cat C:/Windows/win.ini",
    "cat C:\\Windows\\win.ini",
    "cat \\\\serveur\\partage\\f",
    "cat D:secret",
    "cat .git/config",
    "echo x > .git/config",
    "echo x >> .git/hooks/pre-commit",
    "rm -rf .git",
    "rm .git/config",
    "mv .git x",
    "mv a .git/x",
    "cp -r .git x",
    "cp a .git/x",
    "ls .git",
    "touch .git/x",
    "mkdir .git/x",
    "cat .GIT/config",
    "cat .git./config",
    "cat GIT~1/config",
    "rm -rf sub/../../x",
]


@pytest.mark.parametrize("line", OUTSIDE_LINES)
def test_aucune_commande_ne_sort_du_bac_a_sable(tmp_path: Path, line: str) -> None:
    root = tmp_path / "repo"
    (root / ".git" / "hooks").mkdir(parents=True)
    (root / ".git" / "config").write_text("SECRET-GIT", encoding="utf-8")
    (root / "a").write_text("a", encoding="utf-8")
    (root / "sub").mkdir()
    (tmp_path / "secret.txt").write_text("CONTENU-INTERDIT", encoding="utf-8")
    (tmp_path / "dossier").mkdir()
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    result = sh(root, line)
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert result.code == 2, (line, result.lines)
    assert "refusé" in text(result, "refused")
    assert "CONTENU-INTERDIT" not in text(result)
    assert "SECRET-GIT" not in text(result)
    assert before == after
    assert (tmp_path / "secret.txt").read_text(encoding="utf-8") == "CONTENU-INTERDIT"
    assert (root / ".git" / "config").read_text(encoding="utf-8") == "SECRET-GIT"


@pytest.mark.parametrize("name", ["NUL", "con.txt", "COM1", "lpt1.log", "aux", "prn.x", "a.", "b "])
def test_noms_reserves_de_windows_refuses_partout(root: Path, name: str) -> None:
    for line in (f"touch '{name}'", f"cat '{name}'", f"echo x > '{name}'", f"rm '{name}'"):
        assert sh(root, line).code == 2, line


def test_lien_symbolique_sortant_n_est_ni_lu_ni_suivi(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "dehors"
    outside.mkdir()
    (outside / "secret.txt").write_text("CONTENU-INTERDIT", encoding="utf-8")
    symlink_or_skip(root / "lien", outside)
    symlink_or_skip(root / "fichier-lien", outside / "secret.txt")
    # `ls lien` ne montre que le nom du lien, sans lister sa cible.
    assert text(sh(root, "ls lien")) == "lien\n"
    for line in (
        "cat lien/secret.txt",
        "echo x > lien/n.txt",
        "touch lien/n.txt",
        "mkdir lien/d",
        "cat fichier-lien",
        "cp fichier-lien copie",
        "echo x > fichier-lien",
        "echo x >> fichier-lien",
        "cp -r lien copie",
    ):
        result = sh(root, line)
        assert result.code != 0, line
        assert "CONTENU-INTERDIT" not in text(result)
    assert sorted(p.name for p in outside.iterdir()) == ["secret.txt"]
    assert (outside / "secret.txt").read_text(encoding="utf-8") == "CONTENU-INTERDIT"
    # rm et mv agissent sur le lien lui-même, jamais sur sa cible.
    assert sh(root, "mv fichier-lien renomme").code == 0
    assert (root / "renomme").is_symlink()
    assert sh(root, "rm renomme lien").code == 0
    assert not (root / "lien").is_symlink() and not os.path.lexists(root / "lien")
    assert (outside / "secret.txt").read_text(encoding="utf-8") == "CONTENU-INTERDIT"


def test_rm_r_ne_suit_pas_un_lien_dans_un_dossier(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "d").mkdir(parents=True)
    outside = tmp_path / "dehors"
    outside.mkdir()
    (outside / "x.txt").write_text("CONTENU-INTERDIT", encoding="utf-8")
    symlink_or_skip(root / "d" / "lien", outside)
    assert sh(root, "rm -r d").code == 0
    assert (outside / "x.txt").read_text(encoding="utf-8") == "CONTENU-INTERDIT"


@pytest.mark.skipif(os.name != "nt", reason="jonctions propres à Windows")
def test_jonction_windows_traitee_comme_un_lien(tmp_path: Path) -> None:
    import _winapi  # type: ignore[import-not-found]  # noqa: PLC0415

    root = tmp_path / "repo"
    (root / "d").mkdir(parents=True)
    outside = tmp_path / "dehors"
    outside.mkdir()
    (outside / "secret.txt").write_text("CONTENU-INTERDIT", encoding="utf-8")
    # Une jonction ne demande aucun droit d'administrateur, contrairement à un lien.
    _winapi.CreateJunction(str(outside), str(root / "j"))
    _winapi.CreateJunction(str(outside), str(root / "d" / "j"))
    assert wsfs.kind_of(root, "j") == "symlink"
    assert text(sh(root, "ls")) == "d/\nj\n"
    for line in ("cp -r j copie", "cp -r d copie", "cat j/secret.txt", "cat d/j/secret.txt"):
        result = sh(root, line)
        assert result.code != 0, line
        assert "CONTENU-INTERDIT" not in text(result)
    assert not os.path.lexists(root / "copie")
    assert sh(root, "rm j").code == 0 and not os.path.lexists(root / "j")
    assert sh(root, "rm -r d").code == 0
    assert (outside / "secret.txt").read_text(encoding="utf-8") == "CONTENU-INTERDIT"


def test_cp_r_garde_un_lien_sortant_comme_lien(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "d").mkdir(parents=True)
    outside = tmp_path / "dehors"
    outside.mkdir()
    (outside / "secret.txt").write_text("CONTENU-INTERDIT", encoding="utf-8")
    symlink_or_skip(root / "d" / "lien", outside / "secret.txt")
    assert sh(root, "cp -r d e").code == 0
    assert (root / "e" / "lien").is_symlink()  # copié comme lien, jamais par son contenu
    result = sh(root, "cat e/lien")
    assert result.code != 0 and "CONTENU-INTERDIT" not in text(result)


def test_cp_r_ne_copie_pas_un_git_imbrique(root: Path) -> None:
    (root / "sub" / ".git").mkdir(parents=True)
    (root / "sub" / "a.txt").write_text("a", encoding="utf-8")
    assert sh(root, "cp -r sub copie").code == 0
    assert (root / "copie" / "a.txt").exists() and not (root / "copie" / ".git").exists()


def test_ecriture_sans_dossier_parent_refusee(root: Path) -> None:
    for line in ("echo x > a/b.txt", "echo x >> a/b.txt", "touch a/b.txt"):
        result = sh(root, line)
        assert result.code == 1 and "n'existe pas" in text(result), line
    assert not (root / "a").exists()


def test_cat_tronque_un_gros_fichier(root: Path) -> None:
    (root / "gros.txt").write_bytes(b"x" * (wsfs.READ_LIMIT + 10))
    result = sh(root, "cat gros.txt")
    assert result.code == 0
    assert len(text(result, "stdout")) == wsfs.READ_LIMIT
    assert "Kio" in text(result, "app")
    assert wsfs.read_text(root, "gros.txt", limit=4) == ("xxxx", True)


@pytest.mark.parametrize("name", ["CONIN$", "conout$.txt", "COM¹", "a|b", 'a"b', "a<b", "a\tb"])
def test_noms_non_portables_refuses_a_l_ecriture(root: Path, name: str) -> None:
    assert sh(root, f"touch '{name}'").code == 2
    assert sh(root, f"echo x > '{name}'").code == 2
    assert list(root.iterdir()) == [root / ".git"]


def test_lien_vers_git_refuse(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "config").write_text("SECRET-GIT", encoding="utf-8")
    symlink_or_skip(root / "g", root / ".git")
    result = sh(root, "cat g/config")
    assert result.code == 2 and "SECRET-GIT" not in text(result)
    assert sh(root, "echo x > g/config").code == 2
    assert (root / ".git" / "config").read_text(encoding="utf-8") == "SECRET-GIT"


# --- par la file d'opérations ----------------------------------------------------------------


@pytest.mark.slow
def test_commandes_de_fichiers_par_le_terminal(space: Space) -> None:  # noqa: F811
    assert space.run("echo bonjour > note.txt").code == 0
    assert (space.layout.repo / "note.txt").read_bytes() == b"bonjour\n"
    result = space.run("cat note.txt")
    assert result.code == 0 and result.text("stdout") == "bonjour\n"
    status = space.run("git status --short")
    assert "note.txt" in status.text("stdout")
    assert space.run("rm note.txt").code == 0
    assert not (space.layout.repo / "note.txt").exists()


@pytest.mark.slow
def test_refus_de_chemin_et_code_de_sortie_par_le_terminal(space: Space) -> None:  # noqa: F811
    refused = space.run("cat ../x")
    assert refused.code == 2 and refused.streams == ["refused"]
    failed = space.run("cat absent.txt")
    assert failed.code == 1 and failed.streams == ["app", "exit"]
    assert "Code de sortie : 1" in failed.text("exit")
