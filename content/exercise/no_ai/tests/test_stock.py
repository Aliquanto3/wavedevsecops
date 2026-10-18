import pytest

from inventory import Stock, StockError


def test_add_cumulates_quantities() -> None:
    stock = Stock()
    stock.add("vis", 10)
    stock.add("vis", 5)
    assert stock.quantity("vis") == 15


def test_remove_refuses_going_below_zero() -> None:
    stock = Stock()
    stock.add("vis", 3)
    with pytest.raises(StockError, match="Il ne reste que 3"):
        stock.remove("vis", 4)


def test_unknown_article() -> None:
    with pytest.raises(StockError, match="n'existe pas"):
        Stock().quantity("clou")


def test_invalid_quantity() -> None:
    with pytest.raises(StockError):
        Stock().add("vis", 0)


def test_below_threshold_is_sorted() -> None:
    stock = Stock()
    stock.add("vis", 2, threshold=5)
    stock.add("clous", 1, threshold=3)
    stock.add("colle", 9, threshold=3)
    assert stock.below_threshold() == ["clous", "vis"]
