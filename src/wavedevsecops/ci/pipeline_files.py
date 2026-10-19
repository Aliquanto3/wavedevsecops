"""Les trois écritures du pipeline, lues sur le SHA de tête (AD-10, story 7.6).

Le gabarit porte `.github/workflows/ci.yml`, `Jenkinsfile` et `.gitlab-ci.yml`. Chaque tâche de
`content/pipeline.yaml` y est encadrée par deux commentaires, `wds:job <job_id>` puis `wds:end`.
`ci` en tire les plages de lignes de chaque tâche, sur le contenu du fichier au SHA de tête de la
PR : les lignes ne sont jamais codées en dur. Une balise absente, mal fermée ou en double donne un
constat non bloquant (`Finding`), jamais une exception. Ces fichiers ne s'exécutent pas : ce
module ne fait que les lire (`git cat-file`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from wavedevsecops.ci import Pipeline
from wavedevsecops.contracts.github import Finding
from wavedevsecops.gitio import Git
from wavedevsecops.wsfs import Layout

JOB_MARK = re.compile(r"^\s*(?:#|//)\s*wds:job\s+(?P<job_id>[A-Za-z0-9_]+)\s*$")
END_MARK = re.compile(r"^\s*(?:#|//)\s*wds:end\s*$")
# Une balise est un commentaire (`#` ou `//`) qui ne contient qu'elle, seul sur sa ligne : la phrase
# d'en-tête d'un fichier qui cite « wds:job » n'en est pas une.

MARK_MISSING_RULE = "pipeline_mark_missing"
FILE_MISSING_RULE = "pipeline_file_missing"
MARK_BROKEN_RULE = "pipeline_mark_broken"
INFO = "info"
MAX_BYTES = 200_000
"""Taille au-delà de laquelle un fichier de pipeline n'est pas lu (le gabarit en fait 2 Ko)."""


@dataclass(frozen=True)
class PipelineFile:
    """Une des trois écritures du pipeline."""

    tab_id: str
    label_text: str
    path: str


PIPELINE_FILES = (
    PipelineFile("github", "GitHub Actions", ".github/workflows/ci.yml"),
    PipelineFile("jenkins", "Jenkins", "Jenkinsfile"),
    PipelineFile("gitlab", "GitLab CI", ".gitlab-ci.yml"),
)
"""Onglets de `pipeline-tabs`, dans l'ordre de l'UX : GitHub Actions | Jenkins | GitLab CI."""


@dataclass(frozen=True)
class JobRange:
    """Lignes d'une tâche, numérotées à partir de 1, balises exclues."""

    first: int
    last: int

    @property
    def text(self) -> str:
        return (
            f"ligne {self.first}"
            if self.first == self.last
            else f"lignes {self.first} à {self.last}"
        )


@dataclass
class FileLines:
    """Contenu d'un fichier de pipeline au SHA de tête et plages de ses tâches."""

    file: PipelineFile
    content: str = ""
    available: bool = False
    ranges: dict[str, JobRange] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


def _finding(file: PipelineFile, rule: str, message: str, line: int | None = None) -> Finding:
    return Finding(rule_id=rule, severity=INFO, message_text=message, path=file.path, line=line)


def job_ranges(file: PipelineFile, content: str, job_ids: list[str]) -> FileLines:
    """Plages des tâches `job_ids` dans `content`. Aucune exception : un problème de balise
    devient un constat non bloquant et la tâche concernée n'a pas de plage."""
    result = FileLines(file, content=content, available=True)
    open_job: str | None = None
    opened_at = 0
    seen: set[str] = set()
    for number, line in enumerate(content.splitlines(), start=1):
        start = JOB_MARK.search(line)
        if start is not None:
            if open_job is not None:
                result.findings.append(
                    _finding(
                        file,
                        MARK_BROKEN_RULE,
                        f"La tâche « {open_job} » n'est pas fermée par « wds:end » avant "
                        f"« {start['job_id']} » (ligne {number}).",
                        opened_at,
                    )
                )
            open_job, opened_at = start["job_id"], number
            continue
        if END_MARK.search(line) is None:
            continue
        if open_job is None:
            result.findings.append(
                _finding(file, MARK_BROKEN_RULE, "Un « wds:end » ne ferme aucune tâche.", number)
            )
            continue
        if open_job in seen:
            result.findings.append(
                _finding(
                    file,
                    MARK_BROKEN_RULE,
                    f"La tâche « {open_job} » est encadrée plusieurs fois : la première plage "
                    "est gardée.",
                    opened_at,
                )
            )
        elif number - opened_at > 1:
            result.ranges[open_job] = JobRange(opened_at + 1, number - 1)
            seen.add(open_job)
        else:
            result.findings.append(
                _finding(file, MARK_BROKEN_RULE, f"La tâche « {open_job} » est vide.", opened_at)
            )
        open_job = None
    if open_job is not None:
        result.findings.append(
            _finding(
                file,
                MARK_BROKEN_RULE,
                f"La tâche « {open_job} » n'est jamais fermée par « wds:end ».",
                opened_at,
            )
        )
    for job_id in job_ids:
        if job_id not in result.ranges:
            result.findings.append(
                _finding(
                    file,
                    MARK_MISSING_RULE,
                    f"La tâche « {job_id} » n'est pas encadrée par « wds:job {job_id} » et "
                    "« wds:end » : ses lignes ne peuvent pas être surlignées.",
                )
            )
    return result


def _read(git: Git, layout: Layout, sha: str, path: str) -> str | None:
    """Contenu texte de `path` au commit `sha` dans `origin.git` ; `None` s'il est absent,
    illisible ou trop gros. Lecture seule : rien n'est extrait ni exécuté."""
    if not layout.origin.is_dir():
        return None
    try:
        result = git.run("cat-file", "blob", f"{sha}:{path}", cwd=layout.origin)
    except OSError:
        return None
    if not result.ok or len(result.stdout) > MAX_BYTES or "\0" in result.stdout:
        return None
    return result.stdout.replace("\r\n", "\n").replace("\r", "\n")


def read_pipeline_files(
    git: Git, layout: Layout, head_sha: str, pipeline: Pipeline
) -> list[FileLines]:
    """Les trois écritures au SHA de tête, avec la plage de chaque tâche de `pipeline`."""
    job_ids = pipeline.job_ids
    found = []
    for file in PIPELINE_FILES:
        content = _read(git, layout, head_sha, file.path)
        if content is None:
            missing = FileLines(file)
            missing.findings.append(
                _finding(
                    file,
                    FILE_MISSING_RULE,
                    f"« {file.path} » est absent du commit {head_sha[:7]} : rien à surligner "
                    "dans cet onglet.",
                )
            )
            found.append(missing)
        else:
            found.append(job_ranges(file, content, job_ids))
    return found
