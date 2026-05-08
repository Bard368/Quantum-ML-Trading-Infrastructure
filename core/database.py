import os
import asyncpg
import logging
import json
from datetime import datetime

logger = logging.getLogger("DatabaseEngine")

class MarketDatabase:
    def __init__(self):
        self.user = os.getenv('POSTGRES_USER', 'admin')
        self.password = os.getenv('POSTGRES_PASSWORD', 'supersecretpassword')
        self.db_name = os.getenv('POSTGRES_DB', 'trading_bot')
        self.host = "trading_db_pro"
        self.dsn = f"postgresql://{self.user}:{self.password}@{self.host}:5432/{self.db_name}"
        self.pool = None

    async def connect(self):
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(self.dsn, timeout=15)
                logger.info(f"База данных {self.db_name} подключена!")
                await self._init_db()
            except Exception as e:
                logger.error(f"КРИТИЧЕСКАЯ ОШИБКА БД: {e}")
                raise e

    async def _init_db(self):
        """Инициализация структуры Diamond V5.1 + ML Dataset"""
        async with self.pool.acquire() as conn:
            # 1. Таблица для ежеминутных агрегированных фичей (твои 36 индикаторов)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS alpha_features (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    price NUMERIC,
                    score NUMERIC,
                    verdict TEXT,
                    regime TEXT,
                    cvd_usd NUMERIC,
                    oi_usd NUMERIC,
                    funding_pct NUMERIC,
                    extra_factors JSONB,
                    PRIMARY KEY (time, symbol)
                );
            """)

            # --- ТАБЛИЦЫ ДЛЯ ВЕБСОКЕТА (ML DATASET) ---

            # 2. Сырые сделки (Тики - Append Only, без Primary Key для скорости)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ws_trades (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price NUMERIC NOT NULL,
                    amount NUMERIC NOT NULL
                );
            """)

            # 3. Слепки стакана (Слежение за ликвидностью и спуфингом)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ws_orderbook (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    bids JSONB NOT NULL,
                    asks JSONB NOT NULL
                );
            """)

            # Превращаем их в гипертаблицы TimescaleDB для бешеной скорости записи и аналитики
            try:
                await conn.execute("SELECT create_hypertable('alpha_features', 'time', if_not_exists => TRUE);")
                await conn.execute("SELECT create_hypertable('ws_trades', 'time', if_not_exists => TRUE);")
                await conn.execute("SELECT create_hypertable('ws_orderbook', 'time', if_not_exists => TRUE);")
            except:
                pass

    async def save_alpha_snapshot(self, data: dict):
        """Сохранение 'бриллиантового' снимка рынка (раз в минуту)"""
        if not self.pool: return

        try:
            async with self.pool.acquire() as conn:
                raw = data.get('raw_metrics', {})
                decision = data.get('decision', {})

                await conn.execute("""
                    INSERT INTO alpha_features (
                        time, symbol, price, score, verdict, regime,
                        cvd_usd, oi_usd, funding_pct, extra_factors
                    ) VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (time, symbol) DO NOTHING
                """,
                data['symbol'],
                raw.get('mark_price', 0),
                decision.get('score', 0),
                decision.get('verdict', 'NEUTRAL'),
                decision.get('regime', 'NORMAL'),
                raw.get('cvd_usd', 0),
                raw.get('oi_usd', 0),
                raw.get('funding_pct', 0),
                json.dumps(data))
        except Exception as e:
            logger.error(f"Ошибка при сохранении снимка Alpha: {e}")

    # ==========================================
    # МЕТОДЫ ДЛЯ HFT ВЕБСОКЕТА
    # ==========================================

    async def save_trade(self, symbol: str, side: str, price: float, amount: float, trade_time_ms: int = None):
        """Супербыстрое сохранение каждого тика сделки из ленты"""
        if not self.pool: return
        try:
            # Если биржа передала точное время сделки (в мс), используем его, иначе текущее
            dt = datetime.fromtimestamp(trade_time_ms / 1000.0) if trade_time_ms else datetime.now()

            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ws_trades (time, symbol, side, price, amount)
                    VALUES ($1, $2, $3, $4, $5)
                """, dt, symbol, side, price, amount)
        except Exception as e:
            logger.error(f"Ошибка сохранения тика сделки: {e}")

    async def save_ob_snapshot(self, symbol: str, bids: list, asks: list):
        """Сохранение глубокого слепка стакана для поиска спуфинга"""
        if not self.pool: return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ws_orderbook (time, symbol, bids, asks)
                    VALUES (NOW(), $1, $2, $3)
                """, symbol, json.dumps(bids), json.dumps(asks))
        except Exception as e:
            logger.error(f"Ошибка сохранения стакана: {e}")

    async def close(self):
        if self.pool: await self.pool.close()
