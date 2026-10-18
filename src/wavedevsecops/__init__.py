"""WaveDevSecOps : apprendre git, GitHub, la CI/CD et le DevSecOps, hors ligne."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("wavedevsecops")
except PackageNotFoundError:  # pragma: no cover - paquet non installé
    __version__ = "0.0.0"
