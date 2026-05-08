<div align="right">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/English-d9d9d9?style=for-the-badge"></a>
  <a href="README.ru.md"><img alt="Русский" src="https://img.shields.io/badge/Русский-1f8fff?style=for-the-badge"></a>
</div>
# Quantum ML Trading Infrastructure

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API_Gateway-009688?style=flat-square&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/TimescaleDB-Time--Series-336791?style=flat-square&logo=postgresql&logoColor=white)
![Data Science](https://img.shields.io/badge/Pandas_%7C_NumPy-Analytics-150458?style=flat-square&logo=pandas&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-Machine_Learning-F37626?style=flat-square&logo=xgboost&logoColor=white)

> **Высоконагруженный Data-конвейер** для потоковой обработки микроструктуры крипторынка, генерации паттернов Smart Money Concepts (SMC) и подготовки датасетов для машинного обучения.

---

## 🏗️ Обзор архитектуры

Проект представляет собой отказоустойчивую инфраструктуру для сбора сырых тиковых данных и глубины стакана (Orderbook) в реальном времени, с последующей трансформацией в институциональные метрики. 

Система спроектирована для решения главной проблемы ML в алготрейдинге — зависимости моделей от запаздывающих индикаторов и отсутствия качественных данных лимитного давления. Инфраструктура полностью изолирована, разворачивается через Docker и работает в автономном режиме 24/7.

## ⚙️ Технологический стек и компоненты

* **API Gateway (FastAPI)** Быстрый и асинхронный REST API для взаимодействия с ядром. Использование `BackgroundTasks` для неблокирующего сохранения снапшотов рынка в базу данных.
* **Quantum Exchange Engine (HFT)** Продвинутый асинхронный коннектор (на базе `ccxt` и `aiohttp`), рассчитывающий HFT-метрики на лету:
  * Оценка проскальзывания (Slippage) для крупных ордеров.
  * Детекция спуфинга (Spoofing) и фейковых лимитных стен.
  * Межбиржевой арбитраж (Binance vs Bybit).
* **Data Ingestion (Сбор данных)** Асинхронный парсинг WebSocket-потоков биржи (тиковые сделки и стакан ордеров) с использованием `asyncio`.
* **Storage (Хранение)** `PostgreSQL` с расширением `TimescaleDB`. Оптимизированная запись и агрегация огромных массивов временных рядов (Time-series data).
* **Analytics Engine (Движок аналитики)** Динамический расчет метрик микроструктуры средствами `Pandas` и `NumPy` без сторонних ML-библиотек:
  * *Volume Spread Analysis (VSA)* — детекция абсорбции объемов крупным капиталом.
  * *Cumulative Volume Delta (CVD)* — скрытое накопление и распределение.
  * *Smart Money Concepts (SMC)* — имбалансы (FVG), снятие пулов ликвидности (Sweeps), дистанция до VWAP.
* **ML Environment (Среда исследования)** Интегрированная среда Jupyter для бэктестирования стратегий на базе `XGBoost`. Включает алгоритмы защиты от переобучения (Purging/Embargo сплит) и систему расчета динамического таргета на основе волатильности актива.

---

## 📂 Структура проекта

```text
├── core/
│   ├── analytics.py          # Движок генерации ML-фичей (SMC, VSA, CVD)
│   ├── database.py           # Асинхронный клиент для PostgreSQL/TimescaleDB
│   ├── exchange.py           # HFT-коннектор (Оценка микроструктуры)
│   ├── main.py               # API Gateway (FastAPI) с Background Tasks
│   └── stream_parser.py      # Асинхронный сборщик WebSocket-потоков
├── research/
│   └── backtest_engine.ipynb # Среда обучения XGBoost и бэктестирования
├── .gitignore                # Исключения для Git (секреты, БД, кэш)
├── README.md                 # Описание проекта и архитектуры
├── docker-compose.yml        # Оркестрация микросервисов инфраструктуры
└── requirements.txt          # Зависимости Python
🚀 Быстрый старт (Deploy)
Инфраструктура полностью контейнеризирована. Для запуска всех микросервисов (API, WebSockets, TimescaleDB, Redis) выполните:

Bash
# 1. Клонирование репозитория
git clone [https://github.com/ВашЮзернейм/Quantum-ML-Trading-Infrastructure.git](https://github.com/ВашЮзернейм/Quantum-ML-Trading-Infrastructure.git)
cd Quantum-ML-Trading-Infrastructure

# 2. Настройка переменных окружения (добавьте свои ключи)
cp .env.example .env

# 3. Сборка и запуск контейнеров в фоновом режиме
docker compose up -d --build
