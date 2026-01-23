PYTHON ?= .venv/bin/python
PIP ?= $(PYTHON) -m pip
RUFF ?= $(PYTHON) -m ruff
PYTEST ?= $(PYTHON) -m pytest

.PHONY: install lint format test api

install:
	$(PIP) install -r requirements-dev.txt

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

test:
	$(PYTEST)

api:
	cd services/prediction-service-python && $(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
