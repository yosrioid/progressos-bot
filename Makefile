.PHONY: install run test lint format typecheck check

install:
	python -m pip install -e ".[dev]"

run:
	python -m progressos_bot.main

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src

check: lint typecheck test

