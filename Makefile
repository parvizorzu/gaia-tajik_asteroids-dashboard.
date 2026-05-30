# ══════════════════════════════════════════════════════════════
# Makefile — Gaia DR3 Asteroid Dashboard
# Использование: make <цель>
# ══════════════════════════════════════════════════════════════

.DEFAULT_GOAL := help
PYTHON        := python3
VENV          := .venv
PIP           := $(VENV)/bin/pip
PYTEST        := $(VENV)/bin/pytest
STREAMLIT     := $(VENV)/bin/streamlit

# ──────────────────────────────────────────────────────────────
help:  ## Показать список команд
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ──────────────────────────────────────────────────────────────
install: ## Создать venv и установить зависимости
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✅  Окружение готово. Активируй: source $(VENV)/bin/activate"

install-dev: install  ## Установить + dev-зависимости (pytest, ruff)
	$(PIP) install pytest pytest-cov ruff

# ──────────────────────────────────────────────────────────────
etl: ## Загрузить данные из Gaia TAP (требует интернет)
	$(PYTHON) data_loader.py

etl-synthetic: ## Сгенерировать синтетические данные (без интернета)
	$(PYTHON) data_loader.py --no-real-data

db-init: ## Пересоздать схему DuckDB (без загрузки данных)
	$(PYTHON) ddl.py

# ──────────────────────────────────────────────────────────────
run: ## Запустить дашборд локально
	$(STREAMLIT) run app.py

run-port: ## Запустить на порту 8502
	$(STREAMLIT) run app.py --server.port 8502

# ──────────────────────────────────────────────────────────────
test: ## Запустить дымовые тесты
	$(PYTEST) tests/ -v

test-cov: ## Тесты с отчётом покрытия
	$(PYTEST) tests/ -v --cov=. --cov-report=term-missing

# ──────────────────────────────────────────────────────────────
lint: ## Проверить код (ruff)
	$(VENV)/bin/ruff check . --ignore E501

fmt: ## Автоформатировать код (ruff)
	$(VENV)/bin/ruff format .

# ──────────────────────────────────────────────────────────────
clean: ## Удалить кэш, БД и временные файлы
	rm -rf __pycache__ tests/__pycache__ .pytest_cache
	rm -f *.duckdb _test_smoke.duckdb
	rm -rf data/

clean-all: clean  ## Удалить всё включая venv
	rm -rf $(VENV)

.PHONY: help install install-dev etl etl-synthetic db-init run run-port \
        test test-cov lint fmt clean clean-all
