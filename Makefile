PYTHON := .venv/bin/python
export PYTHONPATH := $(CURDIR)/backend

.PHONY: frontend build test export-data analyze validate
frontend:
	npm --prefix frontend run dev
build:
	npm --prefix frontend run build
test:
	$(PYTHON) -m unittest discover -s backend/tests -v
export-data:
	$(PYTHON) -m src.export_demo
analyze:
	$(PYTHON) backend/run_analysis.py --skip-preprocessing
validate:
	$(PYTHON) -m src.adjacent_frame

.PHONY: backend dev
backend:
	$(PYTHON) -m uvicorn monitor.api:app --host 127.0.0.1 --port 8000
dev:
	$(PYTHON) backend/dev.py
