.PHONY: test lint typecheck check run-cli

test:
	python -m pytest

lint:
	python -m ruff check src tests

typecheck:
	python -m mypy src

check: lint typecheck test

run-cli:
	python -m change_plate_next.interfaces.cli.main
