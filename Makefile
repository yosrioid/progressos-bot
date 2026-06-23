PYTHON ?= python3

.PHONY: install run eval-parser test lint format typecheck check

install:
	$(PYTHON) -m pip install -e ".[dev]"

run:
	PYTHONPATH=src $(PYTHON) -m progressos_bot.main

eval-parser:
	PYTHONPATH=src $(PYTHON) -m progressos_bot.ai.evaluation_main tests/fixtures/parser_evaluation.json

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src

check: lint typecheck test
