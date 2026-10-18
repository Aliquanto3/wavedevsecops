"""CI, story 7.1 : après une installation réelle, la chaîne fonctionne réseau coupé.

Lancé avec le Python de l'application installée (`<data>/app/.venv`), `WDS_DATA_DIR` posé.
Copie le gabarit sans IA dans un espace jetable, crée `cache/venv/` par `uv sync --offline
--frozen` depuis le `uv-cache` préchargé, puis résout et lance les outils par le registre.
Sous Linux, la CI le lance dans un espace de noms sans réseau (`unshare -n`).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from wavedevsecops import toolrun
from wavedevsecops.config import Settings, project_root
from wavedevsecops.diagnostic import run_diagnostic

CHAIN = ("ruff", "pytest", "pytest-cov", "coverage", "diff-cover", "bandit", "pip-audit")


def main() -> int:
    settings = Settings.from_env()
    data = settings.resolved_data_dir()
    assert (data / "uv-cache" / "python").is_dir(), "interpréteur géré absent de uv-cache"
    workspace = Path(tempfile.mkdtemp(prefix="wds-espace-"))
    repo = workspace / "repo"
    shutil.copytree(project_root() / "content" / "exercise" / "no_ai", repo)
    venv = toolrun.venv_dir(workspace)
    synced = toolrun.sync_environment(repo, venv, settings)
    print(synced.stdout, synced.stderr, synced.error or "", sep="\n")
    assert synced.ok, "uv sync --offline --frozen a échoué"
    for tool_id in (*CHAIN, "pre-commit"):
        status = toolrun.resolve(tool_id, settings, venv=venv)
        print(f"{tool_id} : {status.state} {status.version}")
        assert status.ok, status.reason
    gitleaks = toolrun.resolve("gitleaks", settings)
    print(f"gitleaks : {gitleaks.state} {gitleaks.version} ({gitleaks.path})")
    assert gitleaks.ok and gitleaks.source == "provisioned", gitleaks.reason
    for argv in (["ruff", "check", "."], ["pytest", "-q"]):
        ran = toolrun.run_tool(
            argv[0], argv[1:], cwd=repo, settings=settings, venv=venv, timeout=300
        )
        print(ran.stdout, ran.stderr, ran.error or "", sep="\n")
        assert ran.ok, f"{argv[0]} a échoué"
    # Diagnostic de l'application installée : outils de la chaîne prêts (uv sync, groupe chain).
    checks = {c.check_id: c for c in run_diagnostic(settings, environ={})}
    for tool_id in (*CHAIN, "pre-commit", "gitleaks"):
        check = checks[f"tool.{tool_id}"]
        assert check.status == "ok", f"{tool_id} : {check.detail_text}"
    shutil.rmtree(workspace, ignore_errors=True)
    print("Chaîne hors ligne vérifiée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
