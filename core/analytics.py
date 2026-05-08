import os
import json
import asyncio
import asyncpg
import pandas as pd
import numpy as np
import logging
import time
from datetime import datetime, timezone, timedelta

# --- Инициализация Bybit для Фандинга ---
try:
    from pybit.unified_trading import HTTP
except ImportError:
    HTTP = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QuantumAnalytics")

class QuantumAnalytics:
    def __init__(self):
        self.user = os.getenv('POSTGRES_USER', 'admin')
        self.password = os.getenv('POSTGRES_PASSWORD', 'supersecretpassword')
        self.db_name = os.getenv('POSTGRES_DB', 'trading_bot')
        self.host = "trading_db_pro"
        self.dsn = f"postgresql://{self.user}:{self.password}@{self.host}:5432/{self.db_name}"
        self.pool = None
        self.session = HTTP(testnet=False) if HTTP else None

    async def connect(self):
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=3)
                logger.info("✅ Подключение к БД установлено.")
            except Exception as e:
                logger.error(f"❌ Ошибка подключения: {e}")
                raise e

    async def close(self):
        if self.pool: await self.pool.close()

    async def fetch_external_context(self, symbol: str):
        if not self.session: return {'funding_rate': 0.0, 'open_interest': 0.0}
        try:
            clean_sym = symbol.split(":")[0].replace("/", "")
            resp = await asyncio.to_thread(self.session.get_tickers, category="linear", symbol=clean_sym)
            ticker = resp['result']['list'][0]
            return {
                'funding_rate': float(ticker.get('fundingRate', 0)),
                'open_interest': float(ticker.get('openInterest', 0))
            }
        except Exception as e:
            return {'funding_rate': 0.0, 'open_interest': 0.0}

    async def get_market_dataframe(self, symbol: str, timeframe_minutes: int = 15, lookback_hours: int = 48) -> pd.DataFrame:
        if not self.pool: return pd.DataFrame()
        query = """
            WITH candle_data AS (
                SELECT time_bucket($1::interval, time) AS timestamp,
                first(price, time) AS open, max(price) AS high, min(price) AS low, last(price, time) AS close,
                sum(amount) AS volume, sum(CASE WHEN side = 'Buy' THEN amount ELSE 0 END) as buy_vol,
                sum(CASE WHEN side = 'Sell' THEN amount ELSE 0 END) as sell_vol
                FROM ws_trades WHERE symbol = $2 AND time >= NOW() - $3::interval GROUP BY timestamp
            ),
            ob_metrics AS (
                SELECT time_bucket($1::interval, time) AS timestamp,
                AVG(CAST(asks->0->>0 AS NUMERIC) - CAST(bids->0->>0 AS NUMERIC)) as spread,
                COALESCE(STDDEV_SAMP(CAST(asks->0->>0 AS NUMERIC) - CAST(bids->0->>0 AS NUMERIC)), 0) as spread_vol,
                AVG((SELECT sum(CAST(val->>1 AS NUMERIC)) FROM jsonb_array_elements(bids) WITH ORDINALITY AS t(val, i) WHERE i <= 5) /
                    NULLIF((SELECT sum(CAST(val->>1 AS NUMERIC)) FROM jsonb_array_elements(bids) WITH ORDINALITY AS t(val, i) WHERE i <= 5) +
                           (SELECT sum(CAST(val->>1 AS NUMERIC)) FROM jsonb_array_elements(asks) WITH ORDINALITY AS t(val, i) WHERE i <= 5), 0)) as obi_5,
                AVG((SELECT sum(CAST(val->>1 AS NUMERIC)) FROM jsonb_array_elements(bids) AS t(val)) /
                    NULLIF((SELECT sum(CAST(val->>1 AS NUMERIC)) FROM jsonb_array_elements(bids) AS t(val)) +
                           (SELECT sum(CAST(val->>1 AS NUMERIC)) FROM jsonb_array_elements(asks) AS t(val)), 0)) as obi_20
                FROM ws_orderbook WHERE symbol = $2 AND time >= NOW() - $3::interval GROUP BY timestamp
            )
            SELECT c.*, COALESCE(o.spread, 0) as spread, COALESCE(o.spread_vol, 0) as spread_vol,
                   COALESCE(o.obi_5, 0.5) as obi_5, COALESCE(o.obi_20, 0.5) as obi_20
            FROM candle_data c LEFT JOIN ob_metrics o ON c.timestamp = o.timestamp ORDER BY c.timestamp ASC;
        """
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch(query, timedelta(minutes=timeframe_minutes), symbol, timedelta(hours=lookback_hours))
            if not records: return pd.DataFrame()
            cols = ['timestamp','open','high','low','close','volume','buy_vol','sell_vol','spread', 'spread_vol', 'obi_5','obi_20']
            df = pd.DataFrame(records, columns=cols)
            df[cols[1:]] = df[cols[1:]].apply(pd.to_numeric, errors='coerce')
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e: return pd.DataFrame()

    def generate_ml_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 5: return pd.DataFrame()

        returns = np.log(df['close'] / df['close'].shift(1))
        df['rvol'] = df['volume'] / (df['volume'].rolling(50, min_periods=1).mean() + 1e-9)

        # Свой Боллинджер
        basis = df['close'].rolling(window=20, min_periods=1).mean()
        dev = df['close'].rolling(window=20, min_periods=1).std()
        upper_bb = basis + 2 * dev
        lower_bb = basis - 2 * dev
        df['bb_width'] = (upper_bb - lower_bb) / (basis + 1e-9) * 100

        candle_range = df['high'] - df['low'] + 1e-9
        df['liq_pressure'] = df['obi_5'] / (df['spread'] + 1e-7)
        df['vol_delta_pct'] = (df['buy_vol'] - df['sell_vol']) / (df['volume'] + 1e-9) * 100
        df['cvd_session'] = df['vol_delta_pct'].rolling(24, min_periods=1).sum()

        df['fvg_bull'] = np.where(df['low'] > df['high'].shift(2), (df['low'] - df['high'].shift(2)) / df['close'] * 100, 0.0)
        df['fvg_bear'] = np.where(df['high'] < df['low'].shift(2), (df['high'] - df['low'].shift(2)) / df['close'] * 100, 0.0)

        min_24 = df['low'].rolling(24, min_periods=1).min().shift(1)
        max_24 = df['high'].rolling(24, min_periods=1).max().shift(1)
        df['sweep_bull'] = np.where((df['low'] < min_24) & (df['close'] > min_24), 1.0, 0.0)
        df['sweep_bear'] = np.where((df['high'] > max_24) & (df['close'] < max_24), 1.0, 0.0)

        typ_price = (df['high'] + df['low'] + df['close']) / 3
        rolling_vwap = (typ_price * df['volume']).rolling(96, min_periods=1).sum() / (df['volume'].rolling(96, min_periods=1).sum() + 1e-9)
        df['vwap_dist'] = (df['close'] - rolling_vwap) / (rolling_vwap + 1e-9) * 100

        high_vol = df['volume'] > df['volume'].rolling(20, min_periods=1).mean()
        df['rejection_bear'] = np.where(high_vol, (df['high'] - df[['open', 'close']].max(axis=1)) / candle_range, 0.0)
        df['rejection_bull'] = np.where(high_vol, (df[['open', 'close']].min(axis=1) - df['low']) / candle_range, 0.0)

        # --- НОВЫЕ ИНСТИТУЦИОНАЛЬНЫЕ ФИЧИ ---
        high_24h = df['high'].rolling(96, min_periods=1).max()
        low_24h = df['low'].rolling(96, min_periods=1).min()
        df['dist_to_24h_high'] = (high_24h - df['close']) / (df['close'] + 1e-9) * 100
        df['dist_to_24h_low'] = (df['close'] - low_24h) / (df['close'] + 1e-9) * 100

        df['vsa_absorption'] = np.where(
            df['volume'] > df['volume'].rolling(20, min_periods=1).mean(),
            df['volume'] / (candle_range * df['close'] + 1e-9),
            0.0
        )

        prev_close = df['close'].shift(1)
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - prev_close).abs()
        tr3 = (df['low'] - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr_pct'] = true_range.rolling(14, min_periods=1).mean() / (df['close'] + 1e-9) * 100

        ema_20 = df['close'].ewm(span=20, adjust=False, min_periods=1).mean()
        df['ema_dist_20'] = (df['close'] - ema_20) / (ema_20 + 1e-9) * 100
        # ------------------------------------

        if 'open_interest' in df.columns:
            df['oi_change_pct'] = df['open_interest'].pct_change().fillna(0) * 100
        else:
            df['oi_change_pct'] = 0.0

        ema_200 = df['close'].ewm(span=200, adjust=False, min_periods=1).mean()
        df['ema_dist_200'] = (df['close'] - ema_200) / (ema_200 + 1e-9) * 100

        df['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
        df['is_ny_open'] = df.index.hour.isin([13, 14, 15, 16]).astype(float)
        df['is_lon_open'] = df.index.hour.isin([7, 8, 9, 10]).astype(float)

        protected = [
            'close', 'hour_sin', 'hour_cos', 'is_ny_open', 'is_lon_open',
            'funding_rate', 'open_interest', 'oi_change_pct',
            'sweep_bull', 'sweep_bear', 'fvg_bull', 'fvg_bear',
            'rejection_bear', 'rejection_bull', 'vwap_dist', 'cvd_session',
            'dist_to_24h_high', 'dist_to_24h_low', 'vsa_absorption', 'atr_pct', 'ema_dist_20'
        ]

        z_dict = {}
        for col in df.columns:
            if col not in protected and df[col].dtype in [np.float64, np.float32]:
                z_dict[f"{col}_z"] = (df[col] - df[col].rolling(30, min_periods=1).mean()) / (df[col].rolling(30, min_periods=1).std() + 1e-9)

        df_final = pd.concat([df[protected], pd.DataFrame(z_dict, index=df.index)], axis=1)
        df_final.replace([np.inf, -np.inf], np.nan, inplace=True)
        df_final['target_class'] = 0

        return df_final.fillna(0)

    async def init_ml_table(self):
        if not self.pool: return
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ml_dataset (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    price NUMERIC NOT NULL,
                    features JSONB NOT NULL,
                    PRIMARY KEY (time, symbol)
                );
            """)
            try: await conn.execute("SELECT create_hypertable('ml_dataset', 'time', if_not_exists => TRUE);")
            except: pass

    async def save_ml_dataset(self, symbol: str, df: pd.DataFrame):
        if not self.pool or df.empty: return
        try:
            records = []
            for t, row in df.iterrows():
                p_val = float(row['close'])
                feat_dict = {k: (None if pd.isna(v) else v) for k, v in row.items() if k != 'close'}
                records.append((t, symbol, p_val, json.dumps(feat_dict)))

            async with self.pool.acquire() as conn:
                await conn.executemany("""
                    INSERT INTO ml_dataset (time, symbol, price, features)
                    VALUES ($1, $2, $3, $4::jsonb)
                    ON CONFLICT (time, symbol)
                    DO UPDATE SET features = EXCLUDED.features, price = EXCLUDED.price
                """, records)
        except Exception as e: logger.error(f"Ошибка сохранения {symbol}: {e}")

    async def update_pipeline(self, symbol: str):
        try:
            df_market = await self.get_market_dataframe(symbol, timeframe_minutes=15, lookback_hours=72)
            if df_market.empty: return

            ext = await self.fetch_external_context(symbol)
            df_market['funding_rate'] = ext['funding_rate']
            df_market['open_interest'] = ext['open_interest']

            df_features = self.generate_ml_features(df_market)

            if not df_features.empty:
                await self.save_ml_dataset(symbol, df_features)
                logger.info(f"💎 {symbol}: Датасет обновлен. Строк: {len(df_features)}")
        except Exception as e: logger.error(f"Сбой пайплайна {symbol}: {e}")

async def main():
    analytics = QuantumAnalytics()
    try:
        await analytics.connect()
        await analytics.init_ml_table()
        symbols = [
            "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "DOGE/USDT:USDT",
            "XRP/USDT:USDT", "BNB/USDT:USDT", "ADA/USDT:USDT", "AVAX/USDT:USDT",
            "LINK/USDT:USDT", "DOT/USDT:USDT", "LTC/USDT:USDT", "ATOM/USDT:USDT",
            "UNI/USDT:USDT", "NEAR/USDT:USDT"
        ]

        logger.info("🟢 Квантовый конвейер запущен.")
        while True:
            start_loop = time.time()
            await asyncio.gather(*[analytics.update_pipeline(sym) for sym in symbols])
            elapsed = time.time() - start_loop
            sleep_time = max(10, 60 - elapsed)
            await asyncio.sleep(sleep_time)

    except Exception as e: logger.critical(f"Критический сбой: {e}")
    finally: await analytics.close()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
