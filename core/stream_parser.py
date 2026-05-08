import asyncio
import json
import logging
import websockets
from websockets.exceptions import ConnectionClosedError
from core.database import MarketDatabase
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DataStreamer")

class BybitDataStreamer:
    def __init__(self, symbols: list):
        # Превращаем 'BTC/USDT:USDT' в 'BTCUSDT' для API Bybit
        self.raw_symbols = symbols
        self.ws_symbols = [s.split('/')[0] + s.split('/')[1].split(':')[0] for s in symbols]
        self.ws_url = "wss://stream.bybit.com/v5/public/linear"

        self.db = MarketDatabase()

        # Локальное хранилище стаканов и буфер сделок
        self.local_orderbooks = {sym: {'bids': {}, 'asks': {}} for sym in self.ws_symbols}
        self.trade_buffer = []

    async def start(self):
        await self.db.connect()
        logger.info("Подключение к БД установлено. Запуск потока Bybit...")

        # Запускаем фоновый сброс данных в БД
        asyncio.create_task(self.db_flusher())

        while True:
            try:
                # ping_interval поддерживает соединение живым
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self.ws = ws
                    await self.subscribe()

                    async for message in ws:
                        await self.process_message(json.loads(message))

            except (ConnectionClosedError, Exception) as e:
                logger.error(f"Разрыв WS соединения: {e}. Переподключение через 5 сек...")
                await asyncio.sleep(5)

    async def subscribe(self):
        topics = []
        for sym in self.ws_symbols:
            topics.append(f"publicTrade.{sym}")
            topics.append(f"orderbook.50.{sym}") # Подписка на стакан 50 уровней

        req = {
            "op": "subscribe",
            "args": topics
        }
        await self.ws.send(json.dumps(req))
        logger.info(f"Успешная подписка на {len(self.ws_symbols)} монет(ы). Потоки активированы.")

    async def process_message(self, msg: dict):
        if 'topic' not in msg: return

        topic = msg['topic']
        data = msg.get('data', [])

        # 1. ОБРАБОТКА СДЕЛОК (TRADES)
        if topic.startswith('publicTrade'):
            symbol = topic.split('.')[1]
            orig_symbol = next(s for s in self.raw_symbols if s.startswith(symbol[:-4]))

            for trade in data:
                side = trade.get('S') # 'Buy' или 'Sell'
                price = float(trade.get('p'))
                amount = float(trade.get('v'))
                ts_ms = int(trade.get('T'))
                dt = datetime.fromtimestamp(ts_ms / 1000.0)

                # Добавляем в оперативную память (буфер), а не сразу в БД
                self.trade_buffer.append((dt, orig_symbol, side, price, amount))

        # 2. ОБРАБОТКА СТАКАНА (ORDERBOOK)
        elif topic.startswith('orderbook'):
            symbol = topic.split('.')[2]
            type_ = msg.get('type') # 'snapshot' (полный снимок) или 'delta' (изменения)

            book = self.local_orderbooks[symbol]

            if type_ == 'snapshot':
                book['bids'] = {float(p): float(v) for p, v in data.get('b', [])}
                book['asks'] = {float(p): float(v) for p, v in data.get('a', [])}
            elif type_ == 'delta':
                # Обновляем Bids
                for p, v in data.get('b', []):
                    if float(v) == 0: book['bids'].pop(float(p), None)
                    else: book['bids'][float(p)] = float(v)
                # Обновляем Asks
                for p, v in data.get('a', []):
                    if float(v) == 0: book['asks'].pop(float(p), None)
                    else: book['asks'][float(p)] = float(v)

    async def db_flusher(self):
        """Фоновый процесс: раз в секунду сбрасывает буферы в БД (Защита от перегрузки)"""
        while True:
            await asyncio.sleep(1.0) # Частота сохранения (1 секунда)

            # --- СБРОС СДЕЛОК ---
            if self.trade_buffer and self.db.pool:
                trades_to_save = self.trade_buffer[:]
                self.trade_buffer.clear()
                try:
                    async with self.db.pool.acquire() as conn:
                        # Массовая вставка (executemany) - в 100 раз быстрее обычного INSERT
                        await conn.executemany("""
                            INSERT INTO ws_trades (time, symbol, side, price, amount)
                            VALUES ($1, $2, $3, $4, $5)
                        """, trades_to_save)
                except Exception as e:
                    logger.error(f"Ошибка массового сохранения сделок: {e}")

            # --- СБРОС СТАКАНОВ ---
            for sym, book in self.local_orderbooks.items():
                orig_symbol = next((s for s in self.raw_symbols if s.startswith(sym[:-4])), None)
                if not orig_symbol: continue

                # Берем топ-20 уровней из локального стакана
                bids = sorted([[p, v] for p, v in book['bids'].items()], key=lambda x: x[0], reverse=True)[:20]
                asks = sorted([[p, v] for p, v in book['asks'].items()], key=lambda x: x[0])[:20]

                if bids and asks:
                    asyncio.create_task(self.db.save_ob_snapshot(orig_symbol, bids, asks))

if __name__ == "__main__":
    # Расширенный список для агрессивного сбора данных (14 монет)
    TRACKED_SYMBOLS = [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "SOL/USDT:USDT",
        "DOGE/USDT:USDT",
        "XRP/USDT:USDT",
        "BNB/USDT:USDT",
        "ADA/USDT:USDT",
        "AVAX/USDT:USDT",
        "LINK/USDT:USDT",
        "DOT/USDT:USDT",
        "LTC/USDT:USDT",
        "ATOM/USDT:USDT",
        "UNI/USDT:USDT",
        "NEAR/USDT:USDT"
    ]

    logger.info("Инициализация Streamer Engine...")
    streamer = BybitDataStreamer(TRACKED_SYMBOLS)

    try:
        asyncio.run(streamer.start())
    except KeyboardInterrupt:
        logger.info("Стример остановлен вручную.")
