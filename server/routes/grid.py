from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from server.titan_state import TitanState
from server.titan_grid import grid_engine
from server.titan_db import TitanDB

router = APIRouter(prefix="", tags=["grid"])


class GridWorkshopRequest(BaseModel):
    symbol: str
    budget: float = 500
    grid_count: int = 10
    range_pct: float = 0


@router.get("/api/grid")
async def get_grid_status():
    return grid_engine.get_status()


@router.post("/api/grid/close/{symbol}")
async def close_grid(symbol: str):
    live_prices = TitanState.market_snapshot.get("_live_prices", {})
    current_price = live_prices.get(symbol, 0)
    if current_price <= 0:
        cruise = TitanState.market_snapshot.get("cruise", [])
        for item in cruise:
            if item["symbol"] == symbol:
                current_price = item["price"]
                break
    if current_price <= 0:
        return {"status": "error", "message": "无法获取当前价格"}
    result = grid_engine.close_grid(symbol, current_price)
    if result:
        TitanState.add_log("action", f"🕸️ 手动关闭网格: {symbol} PnL=${result.get('grid_pnl',0):.2f}")
        try:
            import uuid
            from datetime import datetime
            grid_mode = result.get("spacing_mode", "arithmetic")
            grid_pnl_usd = result.get("grid_pnl", 0)
            grid_capital = result.get("capital_used", 0) or result.get("allocation", 1)
            grid_pnl_pct = round((grid_pnl_usd / grid_capital * 100) if grid_capital > 0 else 0, 2)
            created_str = result.get("created_at", "")
            try:
                grid_open_time = datetime.fromisoformat(created_str) if created_str else datetime.now()
            except Exception:
                grid_open_time = datetime.now()
            TitanDB.save_trade({
                "id": uuid.uuid4().hex[:8], "symbol": symbol, "direction": "grid",
                "strategy_type": f"grid_{grid_mode}", "entry_price": result.get("entry_price", 0),
                "exit_price": current_price, "position_value": grid_capital,
                "pnl_pct": grid_pnl_pct, "pnl_value": round(grid_pnl_usd, 2),
                "result": "win" if grid_pnl_usd > 0 else "loss",
                "reason": "manual_close", "signal_score": 0, "ml_confidence": 0,
                "ai_verdict": "", "mtf_alignment": 0,
                "open_time": grid_open_time.isoformat() if hasattr(grid_open_time, 'isoformat') else str(grid_open_time),
                "close_time": datetime.now().isoformat(),
                "hold_hours": round((datetime.now() - grid_open_time).total_seconds() / 3600, 1),
                "regime": "unknown", "is_grid_trade": True, "spacing_mode": grid_mode,
            })
        except Exception:
            pass
        return {"status": "ok", "grid": result}
    return {"status": "error", "message": "网格不存在"}


@router.post("/api/grid/mutate")
async def mutate_grid_params():
    mutations = grid_engine.mutate_params()
    TitanState.add_log("system", f"🕸️ 网格参数变异完成")
    return {"status": "ok", "mutations": mutations, "new_params": grid_engine.params}


@router.post("/api/grid/workshop")
async def grid_workshop(req: GridWorkshopRequest):
    cruise = TitanState.market_snapshot.get("cruise", [])
    signal = None
    for item in cruise:
        if item["symbol"] == req.symbol:
            signal = item
            break

    if not signal:
        return {"status": "error", "message": "币种不在扫描列表中"}

    price = signal.get("price", 0)
    report = signal.get("report", {}) or {}
    atr = report.get("atr", price * 0.02)
    if atr == 0:
        atr = price * 0.02
    adx = report.get("adx", 20)
    rsi = report.get("rsi", 50)
    ml_pred = signal.get("ml", {}) or {}
    score = signal.get("score", 0)
    atr_pct = (atr / price * 100) if price > 0 else 2.0

    if req.range_pct > 0:
        range_pct = req.range_pct
    elif adx < 20:
        range_pct = atr_pct * 3.0
    elif adx < 25:
        range_pct = atr_pct * 2.5
    else:
        range_pct = atr_pct * 4.0

    range_pct = max(2.0, min(range_pct, 30.0))
    upper = round(price * (1 + range_pct / 100), 8)
    lower = round(price * (1 - range_pct / 100), 8)

    grid_count = max(3, min(req.grid_count, 50))
    step = (upper - lower) / (grid_count - 1) if grid_count > 1 else (upper - lower)
    grids = []
    per_grid_amount = req.budget / grid_count
    for i in range(grid_count):
        grid_price = round(lower + step * i, 8)
        side = "buy" if grid_price < price else "sell"
        grids.append({
            "level": i + 1,
            "price": grid_price,
            "side": side,
            "amount": round(per_grid_amount, 2),
            "distance_pct": round((grid_price - price) / price * 100, 2),
        })

    profit_per_grid = step / price * 100
    total_profit_potential = profit_per_grid * (grid_count - 1)
    buy_count = sum(1 for g in grids if g["side"] == "buy")
    sell_count = grid_count - buy_count

    suitability = "suitable"
    suit_reasons = []
    if adx >= 30:
        suitability = "poor"
        suit_reasons.append(f"ADX={adx:.0f}趋势过强，网格容易单边套牢")
    elif adx >= 25:
        suitability = "moderate"
        suit_reasons.append(f"ADX={adx:.0f}偏强，注意突破风险")
    else:
        suit_reasons.append(f"ADX={adx:.0f}震荡环境，适合网格")

    if atr_pct > 6:
        suitability = "poor"
        suit_reasons.append(f"波动率{atr_pct:.1f}%过大")
    elif atr_pct < 0.5:
        suitability = "moderate"
        suit_reasons.append(f"波动率{atr_pct:.1f}%太低收益有限")

    return {
        "status": "ok",
        "symbol": req.symbol,
        "price": price,
        "upper": upper,
        "lower": lower,
        "range_pct": round(range_pct, 2),
        "grid_count": grid_count,
        "step_price": round(step, 8),
        "step_pct": round(profit_per_grid, 3),
        "budget": req.budget,
        "per_grid_amount": round(per_grid_amount, 2),
        "grids": grids,
        "profit_per_grid_pct": round(profit_per_grid, 3),
        "total_profit_potential_pct": round(total_profit_potential, 2),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "suitability": suitability,
        "suitability_reasons": suit_reasons,
        "market_info": {
            "adx": round(adx, 1),
            "rsi": round(rsi, 1),
            "atr_pct": round(atr_pct, 2),
            "score": score,
            "ml_label": ml_pred.get("label", ""),
        },
    }

@router.post("/api/grid/workshop/deploy")
async def grid_workshop_deploy(req: GridWorkshopRequest):
    workshop_result = await grid_workshop(req)
    if workshop_result.get("status") != "ok":
        return workshop_result

    symbol = req.symbol
    price = workshop_result["price"]
    upper = workshop_result["upper"]
    lower = workshop_result["lower"]

    existing = grid_engine.active_grids.get(symbol)
    if existing:
        return {"status": "error", "message": f"{symbol}已有活跃网格，请先关闭"}

    try:
        grid = grid_engine.generate_grid(
            symbol=symbol,
            price=price,
            atr=price * float(workshop_result["range_pct"]) / 100 / 3,
        )
        grid_engine.activate_grid(symbol, grid)
        TitanState.add_log("action", f"🕸️ 手动部署网格: {symbol} ${req.budget} {req.grid_count}格 范围±{float(workshop_result['range_pct']):.1f}%")
        return {
            "status": "ok",
            "message": f"网格部署成功: {symbol}",
            "grid": grid_engine.active_grids.get(symbol, {}),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/db/grid-history")
async def db_grid_history(limit: int = 50):
    return TitanDB.get_grid_history(limit=limit)
