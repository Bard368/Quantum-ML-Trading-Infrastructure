<div align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/English-d9d9d9?style=for-the-badge" alt="English"></a>
  <a href="README.ua.md"><img src="https://img.shields.io/badge/Українська-1f8fff?style=for-the-badge" alt="Українська"></a>
</div>

# Quantum ML Trading Infrastructure

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API_Gateway-009688?style=flat-square&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/TimescaleDB-Time--Series-336791?style=flat-square&logo=postgresql&logoColor=white)
![Data Science](https://img.shields.io/badge/Pandas_%7C_NumPy-Analytics-150458?style=flat-square&logo=pandas&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-Machine_Learning-F37626?style=flat-square&logo=xgboost&logoColor=white)

> **Високонавантажений Data-конвеєр** для потокової обробки мікроструктури крипторинку, генерації патернів Smart Money Concepts (SMC) та підготовки датасетів для машинного навчання.

---

## 🏗️ Огляд архітектури

Проєкт являє собою відмовостійку інфраструктуру для збору сирих тікових даних та глибини стакану (Orderbook) у реальному часі, з подальшою трансформацією в інституційні метрики.

Система спроектована для вирішення головної проблеми ML в алготрейдингу — залежності моделей від запізнілих індикаторів та відсутності якісних даних лімітного тиску. Інфраструктура повністю ізольована, розгортається через Docker та працює в автономному режимі 24/7.

## ⚙️ Технологічний стек та компоненти

* **API Gateway (FastAPI):** Швидкий та асинхронний REST API для взаємодії з ядром. Використання `BackgroundTasks` для неблокуючого збереження снапшотів ринку в базу даних.
* **Quantum Exchange Engine (HFT):** Просунутий асинхронний конектор (на базі `ccxt` та `aiohttp`), що розраховує HFT-метрики «на льоту»:
  * Оцінка проковзування (**Slippage**) для великих ордерів.
  * Детекція спуфінгу (**Spoofing**) та фейкових лімітних стін.
  * Міжбіржовий арбітраж (Binance vs Bybit).
* **Data Ingestion (Збір даних):** Асинхронний парсинг WebSocket-потоків біржі (угоди та глибина стакану) з використанням `asyncio`.
* **Storage (Зберігання):** `PostgreSQL` з розширенням `TimescaleDB`. Оптимізований запис та агрегація величезних масивів часових рядів (Time-series data).
* **Analytics Engine (Рушій аналітики):** Динамічний розрахунок метрик мікроструктури засобами `Pandas` та `NumPy` без сторонніх ML-бібліотек:
  * *Volume Spread Analysis (VSA)* — детекція абсорбції об'ємів великим капіталом.
  * *Cumulative Volume Delta (CVD)* — приховане накопичення та розподіл.
  * *Smart Money Concepts (SMC)* — імбаланси (FVG), зняття пулів ліквідності (Sweeps), дистанція до VWAP.
* **ML Environment (Середовище дослідження):** Інтегроване середовище Jupyter для бектестування стратегій на базі `XGBoost`. Включає алгоритми захисту від перенавчання (Purging/Embargo спліт) та систему розрахунку динамічного таргету на основі волатильності активу.

---

## 📂 Структура проєкту

```text
├── core/
│   ├── analytics.py          # Рушій генерації ML-фіч (SMC, VSA, CVD, OBI)
│   ├── database.py           # Асинхронний клієнт для PostgreSQL/TimescaleDB
│   ├── exchange.py           # HFT-конектор (Оцінка мікроструктури та спуфінгу)
│   ├── main.py               # API Gateway (FastAPI) з Background Tasks
│   └── stream_parser.py      # Асинхронний збирач WebSocket-потоків
├── research/
│   └── backtest_engine.ipynb # Середовище навчання XGBoost та бектестування
├── .gitignore                # Виключення для Git (секрети, БД, кеш)
├── README.md                 # Опис проєкту та архітектури
├── docker-compose.yml        # Оркестрація мікросервісів інфраструктури
└── requirements.txt          # Залежності Python
