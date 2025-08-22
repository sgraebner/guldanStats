.PHONY: install dev run lint fmt test pre-commit

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

dev:
	. .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt && pre-commit install

run:
	. .venv/bin/activate && python -m src.main

lint:
	. .venv/bin/activate && ruff check .

fmt:
	. .venv/bin/activate && ruff check --fix . && black .

test:
	. .venv/bin/activate && pytest -q
