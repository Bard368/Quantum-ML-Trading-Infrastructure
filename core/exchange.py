import asyncio
import os
import aiohttp
import ccxt.async_support as ccxt
import logging
import math
import statistics
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("QuantumEngine")

class AdvancedCryptoExchange:
    def __init__(self):
        self.api_key = os.getenv('API_KEY', '')
        self.secret = os.getenv('API_SECRET', '')

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        connector = aiohttp.TCPConnector(keepalive_timeout=120, limit=200)
       
        self.session = aiohttp.ClientSession(connector=connector, headers=headers)

        self.exchange = ccxt.bybit({
            'apiKey': self.api_key,
            'secret': self.secret,
            'enableRateLimit': True,
            'timeout': 30000,
            'options': {'defaultType': 'swap'},
            'session': self.session
        })
        self.cache = {}

    async def close(self):
        if self.exchange:
            await self.exchange.close()
            await self.session.close()

    async def _fetch_with_retry(self, fetch_func, *args, **kwargs) -> Any:
        """Профессиональный ретри-механизм с логированием сбоев"""
        for attempt in range(3):
            try:
                return await fetch_func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка запроса (попытка {attempt + 1}/3): {e}")
                await asyncio.sleep(1)
        logger.error(f"❌ Критический сбой: не удалось выполнить {fetch_func.__name__} после 3 попыток.")
        return None

    # ==========================================
    # БЛОК 2: ПРОФЕССИОНАЛЬНАЯ АКТИВНОСТЬ (Tape & Volume)
    # ==========================================
    def _aggregate_trades(self, trades: list) -> list:
        if not trades: return []
        aggregated = []
        current_trade = trades[0].copy()
        if 'cost' not in current_trade: current_trade['cost'] = current_trade['amount'] * current_trade['price']

        for i in range(1, len(trades)):
            if trades[i]['timestamp'] == current_trade['timestamp'] and trades[i]['side'] == current_trade['side']:
                current_trade['amount'] += trades[i]['amount']
                current_trade['cost'] += (trades[i]['amount'] * trades[i]['price'])
            else:
                aggregated.append(current_trade)
                current_trade = trades[i].copy()
                if 'cost' not in current_trade: current_trade['cost'] = current_trade['amount'] * current_trade['price']
        aggregated.append(current_trade)
        return aggregated

    def _calculate_vwap_metrics(self, trades: list) -> Dict[str, Any]:
        if not trades: return {"vwap_dist_pct": 0, "vwap_z_score": 0, "is_price_stable": True}
        total_volume = sum(t['amount'] for t in trades)
        total_cost = sum(t['amount'] * t['price'] for t in trades)
        vwap = total_cost / total_volume if total_volume > 0 else trades[0]['price']
        prices = [t['price'] for t in trades]
        stdev = statistics.stdev(prices) if len(prices) > 1 else 0.001
        current_price = trades[0]['price']
        vwap_dist = (current_price - vwap) / vwap * 100
        z_score = (current_price - vwap) / stdev if stdev > 0 else 0
        return {
            "vwap_dist_pct": round(vwap_dist, 3),
            "vwap_z_score": round(z_score, 2),
            "is_price_stable": abs(z_score) < 1.0
        }

    def _analyze_volume_concentration(self, trades: list) -> Dict[str, Any]:
        if not trades: return {"whale_concentration": 0, "is_retail_driven": True}
        costs = sorted([t['amount'] * t['price'] for t in trades], reverse=True)
        total_value = sum(costs)
        top_5_value = sum(costs[:5])
        concentration = (top_5_value / total_value) if total_value > 0 else 0
        return {
            "whale_concentration": round(concentration, 2),
            "is_retail_driven": concentration < 0.2
        }

    def _get_momentum_v2(self, symbol: str, current_oi: float, current_funding: float) -> Dict[str, Any]:
        """Расчет ускорения рынка (завязан на системный timestamp)"""
        now = time.time()
        prev = self.cache.get(f"{symbol}_mom")
        oi_v, f_accel = 0.0, 0.0
        
        if prev:
            dt = now - prev['time']
            if dt > 1:
                oi_v = ((current_oi - prev['oi']) / dt) * 60
                f_accel = ((current_funding - prev['funding']) / dt) * 3600
                
        self.cache[f"{symbol}_mom"] = {'oi': current_oi, 'funding': current_funding, 'time': now}
        return {"oi_velocity_min": round(oi_v, 2), "funding_accel_hour": round(f_accel, 6)}

    # ==========================================
    # БЛОК 3: ULTRA-MICROSTRUCTURE
    # ==========================================
    def _calculate_micro_price(self, order_book: dict) -> float:
        bids, asks = order_book.get('bids', []), order_book.get('asks', [])
        if not bids or not asks: return 0.0
        p_bid, v_bid = bids[0][0], bids[0][1]
        p_ask, v_ask = asks[0][0], asks[0][1]
        return round((p_ask * v_bid + p_bid * v_ask) / (v_bid + v_ask), 4)

    def _detect_liquidity_magnets(self, order_book: dict) -> Dict[str, Any]:
        bids, asks = order_book.get('bids', []), order_book.get('asks', [])
        mid = (bids[0][0] + asks[0][0]) / 2 if (bids and asks) else 0
        def find_clusters(levels):
            if not levels: return []
            clusters = []
            avg_vol = sum(v for p, v in levels[:50]) / 50 if len(levels) > 0 else 1
            for p, v in levels[:100]:
                if v > avg_vol * 8:
                    clusters.append({"price": p, "power": round(v/avg_vol, 1)})
            return clusters
        b_m, s_m = find_clusters(bids), find_clusters(asks)
        return {
            "buy_magnets": b_m,
            "sell_magnets": s_m,
            "nearest_magnet_dist": round(abs(s_m[0]['price'] - mid)/mid*100, 2) if s_m else 0
        }

    def _analyze_book_convexity(self, levels: list) -> float:
        if len(levels) < 20: return 0.0
        v_near = sum(v for p, v in levels[:10])
        v_far = sum(v for p, v in levels[10:20])
        return round(v_far / v_near, 2) if v_near > 0 else 1.0

    def _calculate_book_delta(self, symbol: str, current_book: dict) -> Dict[str, Any]:
        prev_key = f"{symbol}_last_book_delta"
        prev = self.cache.get(prev_key)
        res = {"bid_liquidity_change": 0.0, "ask_liquidity_change": 0.0, "spoofing_detected": False}
        if prev and current_book.get('bids') and current_book.get('asks'):
            c_b_v = sum(v for p, v in current_book['bids'][:50])
            p_b_v = sum(v for p, v in prev['bids'][:50])
            c_a_v = sum(v for p, v in current_book['asks'][:50])
            p_a_v = sum(v for p, v in prev['asks'][:50])
            res["bid_liquidity_change"] = round(c_b_v - p_b_v, 2)
            res["ask_liquidity_change"] = round(c_a_v - p_a_v, 2)
            if abs(res["bid_liquidity_change"]) / (p_b_v + 1) > 0.3: res["spoofing_detected"] = True
        self.cache[prev_key] = current_book
        return res

    def _calculate_absorption_ratio(self, cvd: float, book_delta: dict) -> float:
        ask_change = book_delta.get("ask_liquidity_change", 0)
        if cvd > 0 and ask_change > 0: return round(ask_change / (cvd + 1), 4)
        return 0.0

    def _calculate_toxic_flow_index(self, spread_bps: float, vol_oi_ratio: float, intensity: float) -> float:
        return round((spread_bps * 0.4) + (vol_oi_ratio * 1000 * 0.3) + (intensity * 0.3), 2)

    def _estimate_slippage(self, levels: list, size_usd: float) -> float:
        curr_sz, weighted_cost = 0, 0
        for p, v in levels:
            lvl_usd = p * v
            if curr_sz + lvl_usd >= size_usd:
                weighted_cost += (size_usd - curr_sz) * p
                curr_sz = size_usd
                break
            weighted_cost += lvl_usd * p
            curr_sz += lvl_usd
        return round(abs((weighted_cost / size_usd) - levels[0][0]) / levels[0][0] * 100, 4) if size_usd > 0 and curr_sz >= size_usd else 0.5

    # ==========================================
    # БЛОК 4: QUANTUM DECISION ENGINE (Diamond V5.2)
    # ==========================================
    def _get_decision(self, sig: dict, micro: dict, raw: dict) -> Dict[str, Any]:
        """
        Quantum Decision Engine V5.2.
        Интегрирует режим рынка, дивергенции, арбитраж и спуфинг-трекер.
        """
        regime = "NORMAL"
        if sig['rvol'] < 0.35: regime = "DEAD_MARKET"
        elif sig['rvol'] > 2.2 and abs(sig['vwap_z']) > 1.3: regime = "IMPULSE"
        elif sig.get('adr_pct', 0) > 5.0: regime = "HIGH_VOLATILITY"

        price_dir = 1 if sig['vwap_z'] > 0.7 else (-1 if sig['vwap_z'] < -0.7 else 0)
        cvd_dir = 1 if raw['cvd_usd'] > 0 else -1

        div_type = None
        div_score = 0
        if price_dir == 1 and cvd_dir == -1:
            div_type = "BEARISH_DIVERGENCE"
            div_score = -0.9
        elif price_dir == -1 and cvd_dir == 1:
            div_type = "BULLISH_DIVERGENCE"
            div_score = 0.9

        fuel = max(min((sig['oi_v_min'] / (raw['oi_usd'] * 0.001 + 1)), 1.0), -1.0)
        barrier = (micro['imb'] * 0.4) + ((micro['micro_p'] - raw['mark_price']) / (raw['mark_price'] * 0.0001 + 1) * 0.6)

        sentiment_score = 0
        if sig.get('ls_ratio', 1) > 1.5 and price_dir == -1: sentiment_score = -0.5
        if sig.get('ls_ratio', 1) < 0.7 and price_dir == 1: sentiment_score = 0.5

        # ARBITRAGE & SPOOFING FILTER
        arb_score = 0
        if sig.get('cross_exchange_premium', 0) < -0.08: arb_score = 0.4 # Bybit дешевле Binance
        elif sig.get('cross_exchange_premium', 0) > 0.08: arb_score = -0.4 # Bybit дороже Binance

        spoof_score = 0
        if sig.get('imb_trend', 0) > 1.0 and price_dir == -1: spoof_score = -0.3 # Давят плитами снизу, но бьют вниз

        # ИСПРАВЛЕНО: Динамические веса в зависимости от режима рынка
        if regime == "IMPULSE":
            raw_final = (fuel * 0.4) + (barrier * 0.1) + (div_score * 0.2) + (sentiment_score * 0.1) + (arb_score * 0.1) + (spoof_score * 0.1)
        else:
            raw_final = (fuel * 0.25) + (barrier * 0.2) + (div_score * 0.2) + (sentiment_score * 0.15) + (arb_score * 0.15) + (spoof_score * 0.05)

        safety = 1.0
        if regime == "DEAD_MARKET": safety = 0.1
        if sig['toxic'] > 20: safety *= 0.5
        if micro['slip'] > 0.12: safety *= 0.7
        if micro.get('spoofing'): safety *= 0.8

        final_score = math.tanh(raw_final) * 100 * safety

        verdict = "NEUTRAL"
        if regime == "DEAD_MARKET": verdict = "WAIT_FOR_VOLUME"
        else:
            if final_score > 65: verdict = "STRONG_BUY"
            elif final_score > 30: verdict = "BUY"
            elif final_score < -65: verdict = "STRONG_SELL"
            elif final_score < -30: verdict = "SELL"

        reasons = []
        if div_type: reasons.append(div_type)
        if sig.get('ls_ratio', 1) > 1.8: reasons.append("Extreme Long Sentiment")
        if sig.get('tick_aggression', 0) > 0.3: reasons.append("Aggressive Buyer Ticks")
        if sig.get('vol_squeeze', 1) < 0.6: reasons.append("Volatility Squeeze")
        if abs(arb_score) > 0: reasons.append("Binance Arbitrage Gap")
        if spoof_score < 0: reasons.append("Detected Spoofing (Fake Bids)")

        return {
            "score": round(final_score, 1),
            "verdict": verdict,
            "regime": regime,
            "reasons": reasons,
            "confidence": round(safety * 100, 0)
        }

    # --- ИНТЕГРАЦИЯ: GET_ALPHA_SNAPSHOT ---
    # --- ИНТЕГРАЦИЯ: GET_ALPHA_SNAPSHOT ---
    async def get_alpha_snapshot(self, symbol: str) -> Dict[str, Any]:
        if not symbol.endswith(':USDT'): symbol = f"{symbol}:USDT"

        tasks = [
            self._fetch_with_retry(self.exchange.fetch_order_book, symbol, limit=500),
            self._fetch_with_retry(self.exchange.fetch_trades, symbol, limit=1000),
            self._fetch_with_retry(self.exchange.fetch_ohlcv, symbol, '1h', limit=24),
            self._fetch_with_retry(self.exchange.fetch_ohlcv, symbol, '1d', limit=14),
            self._fetch_with_retry(self.exchange.fetch_ticker, "BTC/USDT:USDT")
        ]

        raw_s = symbol.split(':')[0].replace('/', '')

        urls = [
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={raw_s}",
            f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={raw_s}&period=5min&limit=1",
            f"https://api.binance.com/api/v3/ticker/price?symbol={raw_s}"
        ]

        v5_results = []
        for url in urls:
            try:
                async with self.session.get(url, timeout=10) as resp:
                    v5_results.append((await resp.json()).get('result', await resp.json()) if resp.status == 200 else {})
            except Exception as e:
                logger.warning(f"Ошибка прямого запроса {url}: {e}")
                v5_results.append({})

        raw_v5 = v5_results[0].get('list', [{}])[0] if v5_results[0].get('list') else {}
        ls_v5 = v5_results[1].get('list', [{}])[0] if v5_results[1].get('list') else {}
        binance_res = v5_results[2]

        res = await asyncio.gather(*tasks, return_exceptions=True)
        
        # БРОНЯ ОТ ПАДЕНИЙ: Если пришла ошибка, подставляем пустые "заглушки"
        ob = res[0] if isinstance(res[0], dict) and 'bids' in res[0] and len(res[0]['bids']) > 0 else {'bids': [[0,0]], 'asks': [[0,0]]}
        tr = res[1] if isinstance(res[1], list) else []
        oh_1h = res[2] if isinstance(res[2], list) else []
        oh_1d = res[3] if isinstance(res[3], list) else []
        btc_t = res[4] if isinstance(res[4], dict) else {}

        mark = float(raw_v5.get('markPrice', 0))
        oi = float(raw_v5.get('openInterestValue', 0)) or (float(raw_v5.get('openInterest', 0)) * mark)
        fund = float(raw_v5.get('fundingRate', 0))
        ls_ratio = float(ls_v5.get('buyRatio', 1.0)) / float(ls_v5.get('sellRatio', 1.0)) if ls_v5.get('sellRatio') else 1.0

        b_price_str = binance_res.get('price')
        binance_price = float(b_price_str) if b_price_str else mark
        cross_exchange_premium = round((mark - binance_price) / binance_price * 100, 4) if binance_price > 0 else 0

        agg_tr = self._aggregate_trades(tr)
        vwap_m = self._calculate_vwap_metrics(agg_tr)
        conc_m = self._analyze_volume_concentration(agg_tr)
        mom_v2 = self._get_momentum_v2(symbol, oi, fund)

        b_ticks = len([t for t in agg_tr if t['side'] == 'buy'])
        s_ticks = len([t for t in agg_tr if t['side'] == 'sell'])
        tick_aggression = round((b_ticks - s_ticks) / (b_ticks + s_ticks), 3) if (b_ticks + s_ticks) > 0 else 0

        micro_p = self._calculate_micro_price(ob)
        magnets = self._detect_liquidity_magnets(ob)
        convexity = self._analyze_book_convexity(ob.get('asks', []))
        b_delta = self._calculate_book_delta(symbol, ob)

        cvd = sum(t['amount']*t['price'] if t['side']=='buy' else -t['amount']*t['price'] for t in agg_tr)
        abs_ratio = self._calculate_absorption_ratio(cvd, b_delta)

        # Перешли на time.time() для скорости HFT
        now = time.time()

        # 1. ПУНКТ: CVD Velocity
        cvd_v_min = 0.0
        prev_cvd_data = self.cache.get(f"{symbol}_cvd_hist")
        if prev_cvd_data:
            dt_cvd = now - prev_cvd_data['t']
            if dt_cvd > 0:
                cvd_v_min = round(((cvd - prev_cvd_data['cvd']) / dt_cvd) * 60, 2)
        self.cache[f"{symbol}_cvd_hist"] = {'cvd': cvd, 't': now}

        # 2. ПУНКТ: OI/Price Divergence
        oi_price_div = "NEUTRAL"
        short_liq_usd = 0.0
        long_liq_usd = 0.0
        
        prev_m = self.cache.get(f"{symbol}_m")
        if prev_m:
            p_change = mark - prev_m.get('price', mark)
            o_change = oi - prev_m.get('oi', oi)
            
            if p_change < 0 and o_change > 0: oi_price_div = "AGGRESSIVE_SHORTING"
            elif p_change > 0 and o_change > 0: oi_price_div = "AGGRESSIVE_LONGING"
            
            if o_change < 0:
                if p_change > 0: short_liq_usd = abs(o_change) 
                elif p_change < 0: long_liq_usd = abs(o_change) 
                
        self.cache[f"{symbol}_m"] = {'oi': oi, 'price': mark, 't': now}

        # 2.5 ПУНКТ: Трекер спуфинга (безопасный доступ к стакану)
        current_imb = 1.0
        if len(ob['bids']) > 0 and len(ob['asks']) > 0:
            ask_vol = sum(p*v for p,v in ob['asks'][:50])
            if ask_vol > 0:
                current_imb = round(sum(p*v for p,v in ob['bids'][:50]) / ask_vol, 2)

        imb_history = self.cache.get(f"{symbol}_imb_hist", [])
        imb_history.append({"imb": current_imb, "t": now})
        # Храним только последние 300 секунд (5 минут)
        imb_history = [x for x in imb_history if (now - x['t']) < 300]
        self.cache[f"{symbol}_imb_hist"] = imb_history
        
        avg_5m_imb = statistics.mean([x['imb'] for x in imb_history]) if imb_history else current_imb
        imb_trend = round(current_imb - avg_5m_imb, 2)

        # 3. ПУНКТ: Volatility Squeeze
        vol_squeeze = 1.0
        if oh_1h and len(oh_1h) >= 20:
            recent_ranges = [(h-l)/l*100 for _,o,h,l,c,v in oh_1h if l > 0]
            if recent_ranges:
                avg_vol = statistics.mean(recent_ranges)
                vol_squeeze = round(recent_ranges[-1] / avg_vol, 2) if avg_vol > 0 else 1.0

        # 4. ПУНКТ: Relative BTC Strength
        sol_24h = float(raw_v5.get('price24hPcnt', 0)) * 100
        btc_24h = btc_t.get('percentage', 0) if btc_t else 0
        rel_strength = round(sol_24h - btc_24h, 2)

        # Сборка сигналов с защитой от пустых списков
        signals = {
            "rvol": round(oh_1h[-1][5] / statistics.mean([c[5] for c in oh_1h[:-1]]), 2) if len(oh_1h)>1 else 1,
            "vwap_z": vwap_m['vwap_z_score'],
            "oi_v_min": mom_v2['oi_velocity_min'],
            "cvd_v_min": cvd_v_min,
            "oi_price_div": oi_price_div,
            "ls_ratio": round(ls_ratio, 2),
            "tick_aggression": tick_aggression,
            "vol_squeeze": vol_squeeze,
            "cross_exchange_premium": cross_exchange_premium,
            "imb_trend": imb_trend,
            "short_liq_proxy_usd": round(short_liq_usd, 2),
            "long_liq_proxy_usd": round(long_liq_usd, 2),
            "toxic": round((vwap_m['vwap_z_score']**2) + (oh_1h[-1][5] / statistics.mean([c[5] for c in oh_1h[:-1]]) * 3), 2) if len(oh_1h)>1 else 0,
            "adr_pct": round(statistics.mean([(h-l)/l*100 for _,o,h,l,c,v in oh_1d[:-1]]), 2) if len(oh_1d)>1 else 0
        }

        micro = {
            "micro_p": micro_p,
            "imb": current_imb,
            "slip": self._estimate_slippage(ob.get('asks', []), 100000),
            "spoofing": b_delta['spoofing_detected'] or abs(imb_trend) > 1.5,
            "abs_ratio": abs_ratio,
            "convexity": convexity,
            "magnets_dist_pct": magnets.get('nearest_magnet_dist', 0),
            "magnets_count": len(magnets.get('sell_magnets', [])) + len(magnets.get('buy_magnets', [])),
            "mark_price": mark
        }

        decision = self._get_decision(signals, micro, {"cvd_usd": cvd, "oi_usd": oi, "mark_price": mark})

        return {
            "timestamp": self.exchange.milliseconds() if hasattr(self.exchange, 'milliseconds') else int(time.time() * 1000),
            "symbol": symbol,
            "decision": decision,
            "intelligence": {
                "signals": signals,
                "microstructure": micro,
                "btc_corr_pct": round(btc_t.get('percentage', 0) if btc_t else 0, 2),
                "relative_btc_strength": rel_strength,
                "whale_concentration": conc_m['whale_concentration']
            },
            "raw_metrics": {
                "cvd_usd": round(cvd, 2),
                "oi_usd": round(oi, 2),
                "funding_pct": round(fund * 100, 4),
                "mark_price": mark
            }
        }

    async def get_hot_tickers(self, limit: int = 5) -> List[Dict]:
        tickers = await self._fetch_with_retry(self.exchange.fetch_tickers)
        if not tickers: return []
        hot = []
        for s, d in tickers.items():
            if s.endswith(':USDT') and not s.startswith(('BTC', 'ETH')):
                v, c = d.get('quoteVolume', 0), d.get('percentage', 0)
                if v > 30_000_000: hot.append({"symbol": s, "vol": v, "change": c, "score": v * (abs(c)**1.5)})
        return sorted(hot, key=lambda x: x['score'], reverse=True)[:limit]
