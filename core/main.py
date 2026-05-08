from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from core.exchange import AdvancedCryptoExchange
from core.database import MarketDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CoreAPI")

app = FastAPI(title="Alpha Quant Engine")

exchange_client = AdvancedCryptoExchange()
db_client = MarketDatabase()

@app.on_event("startup")
async def startup_event():
    # Если база не подключится — Питон упадет, и это ПРАВИЛЬНО.
    # Нам нужно знать об ошибке сразу, а не гадать, почему не пишутся данные.
    await db_client.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await exchange_client.close()
    await db_client.close()

@app.get("/health")
async def health_check():
    return {"status": "online", "db": "connected" if db_client.pool else "offline"}

@app.get("/api/v1/alpha")
async def get_market_alpha(background_tasks: BackgroundTasks, symbol: str = Query("BTC/USDT")):
    data = await exchange_client.get_alpha_snapshot(symbol)
    background_tasks.add_task(db_client.save_alpha_snapshot, data)
    return {"status": "success", "data": data}

@app.get("/api/v1/screener")
async def get_market_screener(limit: int = Query(5)):
    data = await exchange_client.get_hot_tickers(limit=limit)
    return {"status": "success", "data": data}
