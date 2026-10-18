"""`python -m inventory "<question>"` : pose une question à l'assistant du stock."""

from __future__ import annotations

import sys

from inventory.assistant import ask
from inventory.llm_config import load_config
from inventory.stock import Stock


def main(argv: list[str] | None = None) -> int:
    question = " ".join(sys.argv[1:] if argv is None else argv).strip()
    if not question:
        print('Usage : python -m inventory "<question>"')
        return 2
    stock = Stock()
    stock.add("vis", 2, threshold=5)
    stock.add("colle", 9, threshold=3)
    print(ask(question, load_config(), stock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
