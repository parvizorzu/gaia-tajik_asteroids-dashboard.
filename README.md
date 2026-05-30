# ☄️ Gaia DR3 · Обсерватория астероидов Таджикистана

Интерактивный Streamlit-дашборд для анализа **16 именных астероидов**, связанных
с научным наследием Центральной Азии. Данные — ESA **Gaia DR3** SSO-каталог.

> **Данные получены из Gaia DR3 (ESA/Gaia/DPAC)**  
> Лицензия: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

---

## 📁 Структура проекта

```
gaia_asteroids/
├── app.py                  ← Streamlit-дашборд (точка входа)
├── data_loader.py          ← ETL: Gaia TAP → DuckDB
├── ddl.py                  ← Схема DuckDB: таблицы, вью, индексы
├── requirements.txt        ← Зависимости Python
├── Makefile                ← Команды разработчика
├── .gitignore
├── .streamlit/
│   └── config.toml         ← Тема и настройки сервера
├── queries/
│   ├── 01_orbital_elements.sql
│   └── 02_07_queries.sql
└── tests/
    └── test_smoke.py       ← Дымовые тесты (pytest)
```

---

## 🚀 Быстрый старт

### Вариант A — через `make` (рекомендуется)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/ВАШ_АККАУНТ/gaia-tajik-asteroids-dashboard.git
cd gaia-tajik-asteroids-dashboard

# 2. Создать окружение и установить зависимости
make install

# 3. Активировать окружение
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# 4. Сгенерировать данные (синтетика, без интернета)
make etl-synthetic
# или реальные данные из Gaia TAP (нужен интернет):
# make etl

# 5. Запустить дашборд
make run
```

Откроется браузер на `http://localhost:8501`

### Вариант Б — вручную

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python data_loader.py --no-real-data   # синтетика
streamlit run app.py
```

---

## 🧪 Тестирование

```bash
# Установить dev-зависимости
make install-dev

# Запустить дымовые тесты
make test

# С отчётом покрытия
make test-cov
```

Тесты проверяют:
- Все 16 астероидов загружены в БД
- SQL-вью возвращают данные без ошибок
- **Регрессионный тест бага `color_by`** — защита от повторения ошибки
  с `inclination` vs `i_deg` в `v_phase_space`
- Физические ограничения данных (e ∈ [0,1), a > 0, i ∈ [0°,180°])
- Идемпотентность схемы БД

---

## 📋 Все команды `make`

| Команда | Описание |
|---|---|
| `make install` | Создать venv, установить зависимости |
| `make install-dev` | То же + pytest, ruff |
| `make etl` | Загрузить данные из Gaia TAP (интернет) |
| `make etl-synthetic` | Синтетические данные (офлайн) |
| `make db-init` | Пересоздать схему DuckDB |
| `make run` | Запустить дашборд на порту 8501 |
| `make run-port` | Запустить на порту 8502 |
| `make test` | Дымовые тесты |
| `make test-cov` | Тесты + покрытие |
| `make lint` | Проверить стиль кода (ruff) |
| `make fmt` | Автоформатирование (ruff) |
| `make clean` | Удалить кэш, БД, temp-файлы |
| `make clean-all` | Удалить всё включая venv |

---

## ☁️ Деплой на Streamlit Community Cloud

1. Сделай форк / запушь репозиторий на GitHub
2. Зайди на [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Укажи репозиторий и `app.py` как главный файл
4. Нажми **Deploy** — через ~3 мин получишь публичный URL

> **Примечание:** на Streamlit Cloud Gaia TAP недоступен.  
> Приложение автоматически использует синтетические данные.  
> Для реальных данных запусти `make etl` локально и закоммить папку `data/`.

---

## 🗃️ ETL-пайплайн

```
ESA Gaia TAP+
(astroquery.gaia)
      │
      ▼  ADQL-запросы
┌─────────────────┐   ┌──────────────────────┐
│ sso_source      │   │ sso_observation      │
│ (орб. элементы) │   │ (фотометрия транзит.)│
└────────┬────────┘   └──────────┬───────────┘
         │  очистка + валидация  │
         ▼                       ▼
      DuckDB: таблицы → вью → индексы
```

При недоступности TAP автоматически генерируются физически корректные
синтетические данные на основе реальных орбит MPC.

---

## 📖 Цитирование

```
Gaia Collaboration, Vallenari, A., et al. (2023).
Gaia Data Release 3. A&A, 674, A1.
DOI: 10.1051/0004-6361/202243940

Gaia Collaboration, Tanga, P., et al. (2023).
Gaia DR3. The Solar System survey. A&A, 674, A12.
DOI: 10.1051/0004-6361/202244220
```
