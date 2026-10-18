# ruff: noqa: E501
"""Découpeur POSIX et garde du terminal (AD-4) : métacaractères, liste blanche, options."""

from __future__ import annotations

from pathlib import Path

import pytest

from wavedevsecops.terminal.allowlist import Allowlist, get_allowlist, load_allowlist
from wavedevsecops.terminal.parse import Refused, parse_line, tokenize

ALLOWLIST = Path(__file__).resolve().parent.parent / "content" / "terminal-allowlist.yaml"


@pytest.fixture(scope="module")
def allow() -> Allowlist:
    return load_allowlist(ALLOWLIST)


def words(line: str, allow: Allowlist) -> list[str]:
    return [t.text for t in tokenize(line, allow)]


def test_decoupeur_posix(allow: Allowlist) -> None:
    assert words("git commit -m 'un  message'", allow) == ["git", "commit", "-m", "un  message"]
    assert words('git commit -m "a \\"b\\" c"', allow) == ["git", "commit", "-m", 'a "b" c']
    assert words("git add a\\ b.txt", allow) == ["git", "add", "a b.txt"]
    assert words("git commit -m ''", allow) == ["git", "commit", "-m", ""]
    assert words("git log --pretty=format:'%h %s'", allow) == ["git", "log", "--pretty=format:%h %s"]
    assert words("git log HEAD@{1} 'a|b' \"c;d\" 'x$y'", allow)[2:] == ["HEAD@{1}", "a|b", "c;d", "x$y"]
    # Un `$` seul ou en fin de mot n'est pas une expansion ; les globs restent tels quels.
    assert words("git add *.py 5$ '$'", allow) == ["git", "add", "*.py", "5$", "$"]
    assert words("   ", allow) == []


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("git status | cat", "|"),
        ("git status || true", "||"),
        ("git add . && git commit", "&&"),
        ("git status & ", "&"),
        ("git status; ls", ";"),
        ("git log $(whoami)", "$(…"),
        ("git log `whoami`", "`"),
        ("git log $HOME", "$HOME"),
        ('git log "$HOME"', "$HOME"),
        ('git log "`x`"', "`"),
        ("git log < fichier", "<"),
        ("git status\ngit log", "\n"),
        ("git log $'x'", "$'"),
    ],
)
def test_metacaracteres_refuses(allow: Allowlist, line: str, found: str) -> None:
    with pytest.raises(Refused) as refused:
        parse_line(line, allow)
    assert f"« {found} »" in refused.value.text or found == "\n"
    assert "Commandes git acceptées : add, commit" in refused.value.text


@pytest.mark.parametrize("line", ["git status >", "git log > out.txt", "git log >> out.txt", "> x"])
def test_redirection_refusee(allow: Allowlist, line: str) -> None:
    with pytest.raises(Refused) as refused:
        parse_line(line, allow)
    assert "n'est pas un shell" in refused.value.text


@pytest.mark.parametrize("line", ["git commit -m 'x", 'git commit -m "x', "git add a\\"])
def test_guillemet_non_ferme(allow: Allowlist, line: str) -> None:
    with pytest.raises(Refused) as refused:
        parse_line(line, allow)
    assert "guillemet" in refused.value.text


def test_cd_refuse_avec_explication(allow: Allowlist) -> None:
    with pytest.raises(Refused) as refused:
        parse_line("cd src", allow)
    assert "racine du dépôt" in refused.value.text
    assert "Commandes git acceptées" in refused.value.text


def test_commande_inconnue_et_git_nu(allow: Allowlist) -> None:
    with pytest.raises(Refused) as refused:
        parse_line("chmod 777 a", allow)
    assert "« chmod » n'est pas une commande" in refused.value.text
    with pytest.raises(Refused) as bare:
        parse_line("git", allow)
    assert "git status" in bare.value.text


@pytest.mark.parametrize(
    "line",
    [
        "git clone /tmp/x",
        "git frobnicate",
        "git help",
        "git submodule update",
        "git filter-branch",
        "git gc",
    ],
)
def test_sous_commande_hors_liste(allow: Allowlist, line: str) -> None:
    with pytest.raises(Refused) as refused:
        parse_line(line, allow)
    assert "n'est pas dans la liste" in refused.value.text
    assert ", ".join(allow.git) in refused.value.text


@pytest.mark.parametrize(
    "line",
    [
        "git -c core.editor=vim status",
        "git -C .. status",
        "git --git-dir=../.git status",
        "git --work-tree=. status",
        "git --exec-path status",
        "git --version",
    ],
)
def test_options_avant_la_sous_commande(allow: Allowlist, line: str) -> None:
    with pytest.raises(Refused) as refused:
        parse_line(line, allow)
    assert "avant la sous-commande" in refused.value.text or "interdite" in refused.value.text


@pytest.mark.parametrize(
    ("line", "option"),
    [
        ("git status -c", "-c"),
        ("git status -C", "-C"),
        ("git log --output=x", "--output"),
        ("git diff --output x", "--output"),
        ("git diff --no-index a b", "--no-index"),
        ("git diff --ext-diff", "--ext-diff"),
        ("git fetch --upload-pack=x origin", "--upload-pack"),
        ("git push --receive-pack=x origin", "--receive-pack"),
        ("git push --exec=x origin", "--exec"),
        ("git rebase --exec 'echo x'", "--exec"),
        ("git rebase -i HEAD~2", "-i"),
        ("git rebase -x 'echo'", "-x"),
        ("git add -i", "-i"),
        ("git add -p", "-p"),
        ("git checkout -p", "-p"),
        ("git commit -F msg.txt", "-F"),
        ("git commit -C HEAD", "-C"),
        ("git tag -a v1 -F msg.txt", "-F"),
        ("git commit --file=x", "--file"),
        ("git log --git-dir=x", "--git-dir"),
    ],
)
def test_options_interdites(allow: Allowlist, line: str, option: str) -> None:
    with pytest.raises(Refused) as refused:
        parse_line(line, allow)
    assert f"« {option} »" in refused.value.text
    assert "interdite" in refused.value.text


def test_option_absente_de_la_liste_cite_les_options_de_la_sous_commande(allow: Allowlist) -> None:
    with pytest.raises(Refused) as refused:
        parse_line("git status --bogus", allow)
    assert "n'est pas acceptée pour « git status »" in refused.value.text
    assert "Options acceptées pour « git status » : -s, --short" in refused.value.text


def test_une_abreviation_d_option_longue_n_est_pas_acceptee(allow: Allowlist) -> None:
    # git accepte `--out` pour `--output` : seule la forme exacte de la liste passe.
    with pytest.raises(Refused):
        parse_line("git log --out=x", allow)


@pytest.mark.parametrize(
    "line",
    [
        "git status",
        "git status -sb",
        "git status --porcelain=v2",
        "git status -uno",
        "git add .",
        "git add -A",
        "git add -- 'a b.txt'",
        "git commit -m 'msg'",
        "git commit -am 'msg'",
        "git commit --message=msg --amend",
        "git commit --amend --no-edit",
        "git log --oneline --graph --all",
        "git log -3",
        "git log -n 3 -p",
        "git log -n3",
        "git log --pretty=format:'%h %s' main..feature",
        "git diff --staged",
        "git diff -U5 HEAD~1",
        "git show HEAD",
        "git branch",
        "git branch -a -vv",
        "git branch -d feature",
        "git branch -u origin/main",
        "git switch -c feature",
        "git switch main",
        "git checkout -b feature",
        "git restore --staged a.txt",
        "git restore --source=HEAD~1 a.txt",
        "git reset --hard HEAD~1",
        "git revert HEAD --no-edit",
        "git merge --no-ff feature -m 'fusion'",
        "git merge --continue",
        "git rebase --continue",
        "git rebase main",
        "git stash",
        "git stash push -m 'travail'",
        "git stash pop",
        "git stash list",
        "git tag",
        "git tag v1",
        "git tag -a v1 -m 'version'",
        "git tag -d v1",
        "git push",
        "git push -u origin feature",
        "git pull --rebase origin main",
        "git fetch --all",
        "git remote -v",
        "git remote show origin",
        "git reflog",
        "git reflog -n 5",
        "git rm --cached a.txt",
        "git mv a.txt b.txt",
        "git config user.name",
        "git config --list",
        "git config user.name 'Ada'",
        "git config user.email ada@example.org",
        "git blame -L 1,5 a.txt",
        "git shortlog -sn",
        "git ls-files -s",
        "git rev-parse --abbrev-ref HEAD",
        "git cat-file -p HEAD",
    ],
)
def test_commandes_acceptees(allow: Allowlist, line: str) -> None:
    command = parse_line(line, allow)
    assert command is not None
    assert command.sub == line.split()[1]


@pytest.mark.parametrize(
    "line",
    [
        "git config core.editor vim",
        "git config alias.x '!sh'",
        "git config --global user.name x",
        "git config --system user.name x",
        "git remote add evil /tmp/x",
        "git remote set-url origin /tmp/x",
        "git remote remove origin",
        "git reflog expire --all",
        "git reflog delete HEAD@{0}",
        "git reflog write HEAD x y msg",
        "git stash frobnicate",
        "git switch --orphan x",
        "git push --repo=/tmp/x",
        "git branch --edit-description",
        "git log --exec-path",
    ],
)
def test_variantes_dangereuses_refusees(allow: Allowlist, line: str) -> None:
    with pytest.raises(Refused):
        parse_line(line, allow)


def test_classement_lecture_ecriture(allow: Allowlist) -> None:
    def read(line: str) -> bool:
        command = parse_line(line, allow)
        assert command is not None
        return command.read

    assert all(
        read(line)
        for line in (
            "git status",
            "git log --oneline",
            "git diff --staged",
            "git show HEAD",
            "git branch",
            "git branch -a",
            "git branch --show-current",
            "git tag",
            "git tag -l",
            "git stash list",
            "git stash show",
            "git remote -v",
            "git reflog",
            "git config user.name",
            "git config --list",
            "git ls-files",
            "git rev-parse HEAD",
            "git cat-file -p HEAD",
            "git blame a.txt",
            "git shortlog -s",
        )
    )
    assert not any(
        read(line)
        for line in (
            "git add .",
            "git commit -m x",
            "git branch feature",
            "git branch -d feature",
            "git tag v1",
            "git tag -d v1",
            "git stash",
            "git stash pop",
            "git config user.name Ada",
            "git switch main",
            "git reset --hard",
            "git push",
            "git fetch",
        )
    )


def test_message_manquant_et_remote_vise(allow: Allowlist) -> None:
    def missing(line: str) -> bool:
        command = parse_line(line, allow)
        assert command is not None
        return command.missing_message

    assert missing("git commit")
    assert missing("git commit -a")
    assert missing("git tag -a v1")
    assert not missing("git commit -m x")
    assert not missing("git commit -am x")
    assert not missing("git commit --amend")
    assert not missing("git commit --amend --no-edit")
    assert missing("git commit --no-edit")  # sans merge en cours, git refuse : on explique
    assert not missing("git commit --allow-empty-message")
    assert not missing("git tag -a v1 -m x")
    assert not missing("git tag v1")
    pushed = parse_line("git push -u origin feature", allow)
    assert pushed is not None
    assert pushed.remote_argument == "origin"
    assert pushed.touches_origin
    pulled = parse_line("git pull /tmp/depot", allow)
    assert pulled is not None
    assert pulled.remote_argument == "/tmp/depot"  # refusé à l'exécution : pas un remote
    assert parse_line("git fetch --all", allow).remote_argument is None  # type: ignore[union-attr]
    assert parse_line("git status", allow).touches_origin is False  # type: ignore[union-attr]
    shown = parse_line("git remote -v show origin /tmp/x", allow)
    assert shown is not None and shown.read
    assert shown.remote_names == ("origin", "/tmp/x")  # vérifiés à l'exécution
    assert parse_line("git remote", allow).remote_names == ()  # type: ignore[union-attr]


def test_le_fichier_unique_est_celui_du_depot() -> None:
    from wavedevsecops.config import Settings

    assert get_allowlist(Settings()).git.keys() == load_allowlist(ALLOWLIST).git.keys()


def test_chaque_sous_commande_de_la_regle_ad4_est_presente(allow: Allowlist) -> None:
    expected = {
        "add", "commit", "status", "log", "diff", "show", "branch", "switch", "checkout",
        "restore", "reset", "revert", "merge", "rebase", "stash", "tag", "push", "pull",
        "fetch", "remote", "reflog", "rm", "mv", "config", "blame", "shortlog", "ls-files",
        "rev-parse", "cat-file",
    }  # fmt: skip
    assert set(allow.git) == expected
    # Aucune option interdite n'est admise par défaut, hors `-c` de `switch` et les cas listés.
    for sub, spec in allow.git.items():
        for option in spec.options:
            if option in allow.forbidden_options:
                assert (sub, option) in {
                    ("switch", "-c"), ("ls-files", "-c"), ("log", "-p"), ("diff", "-p"), ("diff", "--patch"),
                    ("show", "-p"), ("show", "--patch"), ("log", "--patch"), ("cat-file", "-p"),
                }, (sub, option)  # fmt: skip
