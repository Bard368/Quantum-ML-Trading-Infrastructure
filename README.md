<div align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/English-1f8fff?style=for-the-badge" alt="English"></a>
  <a href="README.ua.md"><img src="https://img.shields.io/badge/Українська-d9d9d9?style=for-the-badge" alt="Українська"></a>
</div>

# Quantum ML Trading Infrastructure

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API_Gateway-009688?style=flat-square&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/TimescaleDB-Time--Series-336791?style=flat-square&logo=postgresql&logoColor=white)
![Data Science](https://img.shields.io/badge/Pandas_%7C_NumPy-Analytics-150458?style=flat-square&logo=pandas&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-Machine_Learning-F37626?style=flat-square&logo=xgboost&logoColor=white)

> **High-performance data pipeline** for real-time crypto market microstructure processing, Smart Money Concepts (SMC) pattern generation, and ML-ready dataset engineering.

---

## 🏗️ Architecture Overview

This project provides a robust infrastructure for collecting raw tick-by-tick data and L2 Orderbook depth in real-time, transforming them into institutional-grade metrics. 

The system is engineered to solve the primary challenge of ML in algorithmic trading: the reliance on lagging indicators and the lack of high-fidelity limit order pressure data. The infrastructure is fully containerized, deployed via Docker, and operates autonomously 24/7.

---

## ⚙️ Technical Stack & Components

* **API Gateway (FastAPI):** High-speed asynchronous REST API for core interaction. Utilizes `BackgroundTasks` for non-blocking market snapshot persistence to the database.
* **Quantum Exchange Engine (HFT):** Advanced asynchronous connector calculating on-the-fly HFT metrics:
    * **Slippage Estimation:** Real-time impact analysis for large orders.
    * **Spoofing Detection:** Identification of fake limit walls and orderbook manipulation.
    * **Cross-Exchange Premium:** Real-time spread arbitrage (Binance vs. Bybit).
* **Data Ingestion:** Asynchronous parsing of WebSocket streams (trades and orderbook depth) using `asyncio`.
* **Storage:** `PostgreSQL` with `TimescaleDB` extension. Optimized for high-throughput time-series data.
* **Analytics Engine:** Dynamic microstructure calculation using `Pandas` and `NumPy`:
    * **VSA & CVD:** Volume absorption and hidden accumulation/distribution detection.
    * **SMC Patterns:** Real-time detection of Fair Value Gaps (FVG), Liquidity Sweeps, and VWAP deviations.
* **ML Environment:** Integrated Jupyter environment for strategy backtesting using `XGBoost` with Purging/Embargo data splitting.

---

## 📂 Project Structure

```text
├── core/
│   ├── analytics.py          # Feature engineering (SMC, VSA, CVD, OBI)
│   ├── database.py           # TimescaleDB client
│   ├── exchange.py           # HFT connector (Microstructure & Spoofing)
│   ├── main.py               # FastAPI Gateway
│   └── stream_parser.py      # WebSocket ingestion worker
├── research/
│   └── backtest_engine.ipynb # XGBoost training & backtesting
├── .gitignore                # Secrets and DB exclusions
├── README.md                 # Documentation
├── docker-compose.yml        # Infrastructure orchestration
└── requirements.txt          # Python dependencies
🚀 Getting Started
Bash
# 1. Clone the repository
git clone [https://github.com/YOUR_USERNAME/Quantum-ML-Trading-Infrastructure.git](https://github.com/YOUR_USERNAME/Quantum-ML-Trading-Infrastructure.git)
cd Quantum-ML-Trading-Infrastructure

# 2. Configure Environment Variables
cp .env.example .env

# 3. Build and Launch Containers
docker compose up -d --build
