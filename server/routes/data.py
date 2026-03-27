import time
import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.titan_state import TitanState
from server.titan_db import TitanDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["data"])


@router.get("/api/live-prices")
async def get_live_prices():
    from server.api import paper_trader, grid_engine

    live = TitanState.market_snapshot.get('_live_prices', {})
    ts = TitanState.market_snapshot.get('_live_price_ts', 0)
    age = round(time.time() - ts, 1) if ts > 0 else -1
    pos_symbols = list(paper_trader.positions.keys()) if paper_trader.positions else []
    pos_prices = {}
    for pid in pos_symbols:
        pos = paper_trader.positions.get(pid, {})
        sym = pos.get('symbol', '')
        if sym and sym in live:
            entry = pos.get('entry_price', 0)
            cur = live[sym]
            direction = pos.get('direction', 'long')
            if direction == 'long':
                pnl_pct = (cur - entry) / entry * 100 if entry > 0 else 0
            else:
                pnl_pct = (entry - cur) / entry * 100 if entry > 0 else 0
            pos_prices[sym] = {
                "price": cur,
                "entry": entry,
                "pnl_pct": round(pnl_pct, 3),
                "direction": direction,
                "tp": pos.get('tp_price', 0),
                "sl": pos.get('sl_price', 0),
                "trailing": pos.get('trailing_activated', False),
            }
    return {
        "count": len(live),
        "age_sec": age,
        "btc": live.get('BTC', 0),
        "eth": live.get('ETH', 0),
        "positions": pos_prices,
        "monitor_active": True,
        "refresh_interval": 5,
    }


@router.get("/api/external")
async def get_external_data():
    from server.api import external_data
    return external_data.get_status()


@router.post("/api/external/refresh")
async def refresh_external_data():
    from server.api import external_data
    try:
        refreshed = await external_data.refresh_all()
        return {"status": "ok", "refreshed": refreshed}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/kline/{symbol}")
async def get_kline_data(symbol: str, timeframe: str = "4h", limit: int = 200):
    from server.api import commander
    try:
        sym = symbol.upper()
        if not sym.endswith("/USDT"):
            sym = f"{sym}/USDT"
        tf = timeframe if timeframe in ("1m", "5m", "15m", "1h", "4h", "1d", "1w") else "4h"
        lim = min(max(limit, 50), 500)
        ohlcv = await commander.exchange.fetch_ohlcv(sym, tf, limit=lim)
        candles = []
        for row in ohlcv:
            candles.append({
                "time": int(row[0] / 1000),
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            })
        return {"symbol": sym, "timeframe": tf, "candles": candles}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/external-data/coinglass")
async def get_coinglass_data():
    from server.api import external_data
    try:
        snap = external_data.get_snapshot()
        return snap.get("coinglass", {"status": "not_available"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/external-data/news")
async def get_news_data():
    from server.api import external_data
    try:
        snap = external_data.get_snapshot()
        return snap.get("news", {"status": "not_available"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/external-data/onchain")
async def get_onchain_data():
    from server.api import external_data
    try:
        snap = external_data.get_snapshot()
        return {
            "onchain": snap.get("onchain", {}),
            "glassnode": snap.get("glassnode", {}),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/external-data/all")
async def get_all_external_data():
    from server.api import external_data
    try:
        return external_data.get_status()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/global-market")
async def get_global_market():
    try:
        from server.titan_external_data import get_global_market_data
        import asyncio
        data = await asyncio.get_event_loop().run_in_executor(None, get_global_market_data)
        return data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/memory-bank")
async def get_memory_bank():
    from server.api import external_data
    try:
        mb = external_data.memory_bank
        return mb.get_status()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/memory-bank/trades")
async def get_memory_bank_trades():
    from server.api import external_data
    try:
        mb = external_data.memory_bank
        symbol = None
        regime = None
        return {"trades": mb.get_similar_trades(symbol=symbol, regime=regime, limit=50)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/memory-bank/performance")
async def get_memory_bank_performance():
    from server.api import external_data
    try:
        mb = external_data.memory_bank
        return {"trend": mb.get_performance_trend(days=30)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/memory-bank/stats")
async def get_memory_bank_stats(days: int = 30):
    from server.api import external_data
    try:
        mb = external_data.memory_bank
        return mb.get_advanced_stats(days=days if days > 0 else None)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/memory-bank/analyze")
async def analyze_memory_bank():
    from server.api import external_data
    try:
        mb = external_data.memory_bank
        result = await mb.ai_analyze()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/memory-bank/auto-rules")
async def generate_auto_rules():
    from server.api import external_data
    try:
        mb = external_data.memory_bank
        result = mb.generate_auto_rules()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/db/trades")
async def db_get_trades(strategy: str = None, symbol: str = None, result: str = None, limit: int = 100, offset: int = 0):
    return TitanDB.query_trades(strategy=strategy, symbol=symbol, result=result, limit=limit, offset=offset)


@router.get("/api/db/strategy-stats")
async def db_strategy_stats():
    return TitanDB.get_strategy_stats()


@router.get("/api/db/asset-stats")
async def db_asset_stats(limit: int = 20):
    return TitanDB.get_asset_stats(limit=limit)


@router.get("/api/db/signals")
async def db_get_signals(limit: int = 50):
    return TitanDB.get_recent_signals(limit=limit)


@router.get("/api/db/equity-curve")
async def db_equity_curve(hours: int = 72):
    return TitanDB.get_equity_curve(hours=hours)


@router.get("/api/db/summary")
async def db_summary():
    return TitanDB.get_dashboard_summary()
