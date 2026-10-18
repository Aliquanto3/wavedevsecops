"""Le stock : des articles, leur quantité et un seuil d'alerte."""

from __future__ import annotations

from dataclasses import dataclass


class StockError(ValueError):
    """Opération impossible sur le stock (article inconnu, quantité invalide)."""


@dataclass
class Article:
    name: str
    quantity: int = 0
    threshold: int = 0
    """En dessous de ce seuil, l'article est à recommander."""


class Stock:
    def __init__(self) -> None:
        self._articles: dict[str, Article] = {}

    def add(self, name: str, quantity: int, threshold: int | None = None) -> Article:
        """Ajoute `quantity` à l'article, qu'il crée au besoin."""
        if quantity <= 0:
            raise StockError("La quantité ajoutée doit être positive.")
        article = self._articles.setdefault(name, Article(name))
        article.quantity += quantity
        if threshold is not None:
            article.threshold = threshold
        return article

    def remove(self, name: str, quantity: int) -> Article:
        """Retire `quantity` de l'article ; refuse d'aller sous zéro."""
        if quantity <= 0:
            raise StockError("La quantité retirée doit être positive.")
        article = self._get(name)
        if quantity > article.quantity:
            raise StockError(f"Il ne reste que {article.quantity} « {name} » en stock.")
        article.quantity -= quantity
        return article

    def quantity(self, name: str) -> int:
        return self._get(name).quantity

    def below_threshold(self) -> list[str]:
        """Noms des articles à recommander, par ordre alphabétique."""
        return sorted(a.name for a in self._articles.values() if a.quantity < a.threshold)

    def _get(self, name: str) -> Article:
        try:
            return self._articles[name]
        except KeyError:
            raise StockError(f"L'article « {name} » n'existe pas.") from None
