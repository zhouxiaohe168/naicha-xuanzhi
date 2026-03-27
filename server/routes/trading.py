import uuid
import time
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from server.titan_state import CONFIG, TitanState, get_coin_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["trading"])

MAX_POSITIONS = 8


class OrderRequest(BaseModel):
    sym: str
    entry: str
    tp: Optional[str] = ""
    sl: Optional[str] = ""
    amount: str


class TradePreviewRequest(BaseModel):
    symbol: str
    direction: str = "long"


class TradeConfirmRequest(BaseModel):
    symbol: str
    direction: str = "long"
    amount: float = 0
    tp_price: float = 0
    sl_price: float = 0
    entry_price: float = 0


@router.post("/api/order")
async def add_order(order: OrderRequest):
    from server.api import positions, save_positions
    new_pos = {
        "id": str(uuid.uuid4())[:8],
        "sym": order.sym.upper(),
        "entry": order.entry,
        "tp": order.tp or "",
        "sl": order.sl or "",
        "amount": order.amount,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    positions.append(new_pos)
    save_positions()
    TitanState.add_log("action", f"新增持仓: {new_pos['sym']} @ ${new_pos['entry']}")
    return {"status": "ok", "position": new_pos}


@router.delete("/api/order/{order_id}")
async def remove_order(order_id: str):
    from server.api import positions, save_positions
    import server.api as _api
    removed = [p for p in positions if p["id"] == order_id]
    _api.positions = [p for p in positions if p["id"] != order_id]
    save_positions()
    if removed:
        TitanState.add_log("action", f"移除持仓: {removed[0]['sym']}")
    return {"status": "ok"}


@router.post("/api/trade/preview")
async def trade_preview(req: TradePreviewRequest):
    """AI研判 - 5层决策引擎综合评估"""
    from server.api import paper_trader, grid_engine, order_engine, constitution, synapse, signal_quality, risk_budget, capital_sizer, dispatcher
    from server.titan_ml import adaptive_weights

    cruise = TitanState.market_snapshot.get("cruise", [])
    signal = None
    for item in cruise:
        if item["symbol"] == req.symbol:
            signal = item
            break

    empty_resp = {
        "verdict": "SKIP", "verdict_text": "🔴 不建议买入",
        "symbol": req.symbol, "direction": req.direction,
        "price": 0, "tp_price": 0, "sl_price": 0,
        "recommended_amount": 0, "risk_amount": 0, "risk_reward": 0,
        "signal_score": 0, "ml_confidence": 0, "fng": 0,
        "regime": "未知",
        "reasons": ["❌ 该币种不在当前扫描列表中，请等待扫描完成后再试"],
        "portfolio": paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
        "ai_insight": "", "recommended_operation": "",
        "operation_scores": {"做多": 0, "做空": 0, "网格": 0},
        "operation_confidence": 0, "adx": 0, "rsi": 0, "atr_pct": 0,
        "ml_label": "", "decision_chain": [], "risk_grade": {},
        "partial_tp_plan": {}, "entry_strategy": {},
        "ai_risk_review": {},
    }
    if not signal:
        return empty_resp

    score = signal.get("score", 0)
    ml_pred = signal.get("ml", {}) or {}
    ml_conf = ml_pred.get("confidence", 0)
    regime = signal.get("regime", {})
    price = signal.get("price", 0)
    report = signal.get("report", {}) or {}
    atr = report.get("atr", price * 0.02) if report else price * 0.02
    if atr == 0:
        atr = price * 0.02

    fng = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
    adx = report.get("adx", 20)
    rsi = report.get("rsi", 50)
    ml_label = ml_pred.get("label", "")
    regime_type = regime.get("type", "unknown") if isinstance(regime, dict) else str(regime) if regime else "unknown"
    atr_pct = (atr / price * 100) if price > 0 else 2.0

    regime_map = {
        "trending": "trending", "trend": "trending", "强趋势": "trending", "趋势": "trending",
        "ranging": "ranging", "range": "ranging", "震荡": "ranging", "横盘": "ranging",
        "volatile": "volatile", "高波动": "volatile",
        "mixed": "mixed", "混合": "mixed",
    }
    regime_key = regime_map.get(dispatcher.current_regime, "mixed")

    order_ctx = {
        "symbol": req.symbol,
        "price": price,
        "direction": req.direction,
        "atr": atr,
        "regime": regime_key,
        "adx": adx,
        "rsi": rsi,
        "signal_score": score,
        "ml_prediction": ml_pred,
        "fng": fng,
        "atr_1h": report.get("atr_1h", 0),
        "atr_daily": report.get("atr_daily", 0),
    }
    order_result = order_engine.compute_order(order_ctx)

    tp_price = order_result["tp_price"]
    sl_price = order_result["sl_price"]
    risk_reward = order_result["risk_reward"]

    risk_check = {"passed": True, "issues": []}
    try:
        c_status = constitution.get_status()
        if c_status.get("permanent_breaker"):
            risk_check["passed"] = False
            risk_check["issues"].append("永久熔断已激活")
        if c_status.get("daily_breaker"):
            risk_check["passed"] = False
            risk_check["issues"].append("单日熔断冷却中")
    except Exception:
        pass

    pt_equity = paper_trader.get_equity(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
    total_exposure = paper_trader.get_total_exposure()

    sq_conditions = signal_quality.extract_conditions(report, dispatcher.current_regime) if report else []
    sq_eval = signal_quality.evaluate_signal(sq_conditions, req.symbol, dispatcher.current_regime, score)
    sq_score_val = sq_eval.get("quality_score", score) / 100.0

    synapse_ok, _ = synapse.should_trade(
        req.symbol,
        dispatcher.get_strategy_for_signal(signal) if signal else "trend",
        dispatcher.current_regime
    )
    synapse_conf = 1.0 if synapse_ok else 0.5

    aw_status = adaptive_weights.get_adaptive_weights()
    total_trades_pt = paper_trader.total_wins + paper_trader.total_losses
    win_rate_pt = paper_trader.total_wins / max(total_trades_pt, 1)

    sizing_ctx = {
        "equity": pt_equity, "signal_score": score, "ml_confidence": ml_conf,
        "atr": atr, "price": price, "regime": dispatcher.current_regime,
        "strategy": dispatcher.get_strategy_for_signal(signal) if signal else "trend",
        "fng": fng,
        "win_rate": win_rate_pt if total_trades_pt >= 5 else 0.45,
        "payoff_ratio": risk_reward,
        "consecutive_wins": paper_trader.consecutive_wins,
        "consecutive_losses": paper_trader.consecutive_losses,
        "total_exposure": total_exposure,
        "available_budget": pt_equity * 0.6 - total_exposure,
        "signal_quality_score": sq_score_val,
        "synapse_confidence": synapse_conf,
        "adaptive_w_ml": aw_status.get("w_ml", 0.35),
        "drawdown_pct": risk_budget.total_drawdown * 100,
        "coin_tier": get_coin_tier(req.symbol),
    }
    sizing_result = capital_sizer.calculate_position(sizing_ctx)
    rec_amount = sizing_result["amount"]
    rec_msg = sizing_result["message"]

    sl_distance_pct = abs(sl_price - price) / price if price > 0 else 0.02
    can_open, open_reason = constitution.can_open_position(
        pt_equity, rec_amount, total_exposure, sl_distance_pct)

    risk_amount = round(rec_amount * sl_distance_pct, 2)

    reasons = []
    verdict = "BUY"

    if len(paper_trader.positions) >= MAX_POSITIONS:
        verdict = "SKIP"
        reasons.append(f"❌ 持仓已达上限{MAX_POSITIONS}笔,等待平仓后再开新仓")
    if not can_open:
        verdict = "SKIP"
        reasons.append(f"❌ 宪法审查: {open_reason}")
    if not risk_check["passed"]:
        verdict = "SKIP"
        for issue in risk_check["issues"]:
            reasons.append(f"❌ 风控: {issue}")

    synapse_ok, synapse_reason = synapse.should_trade(
        req.symbol, dispatcher.get_strategy_for_signal(signal), dispatcher.current_regime)
    if not synapse_ok:
        verdict = "SKIP"
        reasons.append(f"❌ 协同学习: {synapse_reason}")

    quality_score = sq_eval.get("quality_score", score)

    if score < 70:
        verdict = "SKIP"
        reasons.append(f"❌ 信号评分{score}分过低(<70)")
    elif score < 80:
        if verdict != "SKIP":
            verdict = "CAUTION"
        reasons.append(f"⚠️ 信号评分{score}分偏低(<80)")
    else:
        reasons.append(f"✅ 信号评分{score}分达标")

    if quality_score != score:
        adj_txt = f"{'↑' if quality_score > score else '↓'}{abs(quality_score - score):.0f}"
        reasons.append(f"🔬 信号质量校准: {score}→{quality_score:.0f} ({adj_txt})")

    ml_conf_pct = ml_conf if ml_conf > 1 else ml_conf * 100
    meta_trade = ml_pred.get("meta_trade", True)
    if not meta_trade:
        if verdict != "SKIP":
            verdict = "CAUTION"
        reasons.append(f"⚠️ Meta-Labeler不建议此交易(置信{ml_pred.get('meta_confidence', 0):.0f}%)")
    if ml_conf_pct >= 65:
        reasons.append(f"✅ ML置信度{ml_conf_pct:.0f}%强")
    elif ml_conf_pct >= 50:
        reasons.append(f"⚠️ ML置信度{ml_conf_pct:.0f}%中等")
    else:
        if verdict != "SKIP":
            verdict = "CAUTION"
        reasons.append(f"⚠️ ML置信度{ml_conf_pct:.0f}%偏低")

    ml_probs = ml_pred.get("probabilities", {})
    if ml_probs:
        prob_up = ml_probs.get("涨", 0)
        prob_down = ml_probs.get("跌", 0)
        prob_flat = ml_probs.get("横盘", 0)
        dir_prob = prob_up if req.direction == "long" else prob_down
        reasons.append(f"📈 ML概率分布: 涨{prob_up:.0f}%/跌{prob_down:.0f}%/盘{prob_flat:.0f}% → 方向概率{dir_prob:.0f}%")

    if fng <= 15:
        if req.direction == "long":
            if verdict != "SKIP":
                verdict = "CAUTION"
            reasons.append(f"⚠️ 极度恐惧(FNG={fng})做多需谨慎")
        else:
            reasons.append(f"✅ 极度恐惧(FNG={fng})适合做空")
    elif fng >= 80:
        if req.direction == "long":
            if verdict != "SKIP":
                verdict = "CAUTION"
            reasons.append(f"⚠️ 极度贪婪(FNG={fng})做多风险高")

    if rec_amount <= 0:
        verdict = "SKIP"
        reasons.append(f"❌ {rec_msg}")

    if paper_trader.consecutive_losses >= 2:
        reasons.append(f"⚠️ 连续亏损{paper_trader.consecutive_losses}笔，仓位已缩减")

    risk_grade = order_result.get("risk_grade", {})
    grade = risk_grade.get("grade", "C")
    if grade == "F":
        verdict = "SKIP"
        reasons.append(f"❌ 风险评级F级(极高风险): {risk_grade.get('summary', '')}")
    elif grade == "D":
        if verdict != "SKIP":
            verdict = "CAUTION"
        reasons.append(f"⚠️ 风险评级D级: {risk_grade.get('summary', '')}")
    elif grade in ("A", "B"):
        reasons.append(f"✅ 风险评级{grade}级: {risk_grade.get('summary', '')}")
    else:
        reasons.append(f"📊 风险评级{grade}级: {risk_grade.get('summary', '')}")

    op_scores = {"做多": 0, "做空": 0, "网格": 0}
    if adx > 25:
        if ml_label in ("看涨", "bullish", "up") or rsi < 65:
            op_scores["做多"] += 30
        if ml_label in ("看跌", "bearish", "down") or rsi > 35:
            op_scores["做空"] += 30
    elif adx < 20:
        op_scores["网格"] += 40
    else:
        op_scores["做多"] += 10
        op_scores["做空"] += 10
        op_scores["网格"] += 15

    if regime_key == "trending":
        op_scores["做多" if score >= 50 else "做空"] += 20
    elif regime_key == "ranging":
        op_scores["网格"] += 25
    elif regime_key == "volatile":
        op_scores["网格"] += 15
        op_scores["做空"] += 10

    if score >= 70:
        op_scores["做多" if req.direction == "long" else "做空"] += 25
    elif score >= 60:
        op_scores["做多" if req.direction == "long" else "做空"] += 15

    if ml_conf_pct >= 65:
        if ml_label in ("看涨", "bullish", "up"):
            op_scores["做多"] += 20
        elif ml_label in ("看跌", "bearish", "down"):
            op_scores["做空"] += 20

    if atr_pct < 1.5:
        op_scores["网格"] += 15
    elif atr_pct > 4.0:
        op_scores["做空"] += 10

    if fng <= 20:
        op_scores["做空"] += 15
        op_scores["做多"] -= 10
    elif fng >= 75:
        op_scores["做空"] += 10
        op_scores["做多"] -= 5
    elif 40 <= fng <= 60:
        op_scores["网格"] += 10

    recommended_op = max(op_scores, key=lambda k: op_scores.get(k, 0))
    op_total = sum(max(0, v) for v in op_scores.values()) or 1
    op_confidence = max(0, op_scores[recommended_op]) / op_total * 100

    reasons.append(f"📊 操作建议: {recommended_op}(置信{op_confidence:.0f}%) ADX={adx:.0f} RSI={rsi:.0f}")

    ai_risk_review = {}
    if verdict != "SKIP":
        try:
            from server.titan_llm_client import chat_json
            from server.titan_prompt_library import RISK_REVIEW_PROMPT
            review_prompt = f"""请对以下交易计划进行最终审查。

## 交易计划
- 币种: {req.symbol}
- 方向: {'做多' if req.direction == 'long' else '做空'}
- 入场价: {price}
- 止盈价: {tp_price} (距离{order_result['tp_distance_pct']}%)
- 止损价: {sl_price} (距离{order_result['sl_distance_pct']}%)
- 盈亏比: {risk_reward}:1
- 建议金额: ${rec_amount:.2f}
- 风险金额: ${risk_amount:.2f}

## 市场环境
- 市场状态: {regime_key} (ADX={adx:.0f})
- RSI: {rsi:.0f}
- 恐贪指数: {fng}
- 波动率(ATR%): {atr_pct:.2f}%
- ML预测: {ml_label} 置信度{ml_conf_pct:.0f}%
- ML概率: 涨{ml_probs.get('涨', 0):.0f}%/跌{ml_probs.get('跌', 0):.0f}%/盘{ml_probs.get('横盘', 0):.0f}%
- 信号评分: {score}分
- 风险评级: {grade}

## 账户状态
- 总资产: ${pt_equity:.2f}
- 当前敞口: ${total_exposure:.2f}
- 连胜/连亏: {paper_trader.consecutive_wins}/{paper_trader.consecutive_losses}"""
            ai_risk_review = chat_json(
                module="api_signal_analysis",
                messages=[
                    {"role": "system", "content": RISK_REVIEW_PROMPT},
                    {"role": "user", "content": review_prompt},
                ],
                max_tokens=800,
            )
            if ai_risk_review:
                adj = ai_risk_review.get("allowed_adjustments", {})
                tp_adj = adj.get("tp_adjust_pct", 0)
                sl_adj = adj.get("sl_adjust_pct", 0)
                amt_adj = adj.get("amount_adjust_pct", 0)

                tp_adj = max(-15, min(15, tp_adj))
                sl_adj = max(-15, min(15, sl_adj))
                amt_adj = max(-15, min(15, amt_adj))

                if abs(tp_adj) >= 3 or abs(sl_adj) >= 3:
                    tp_distance = abs(tp_price - price)
                    sl_distance = abs(sl_price - price)
                    tp_distance *= (1 + tp_adj / 100)
                    sl_distance *= (1 + sl_adj / 100)
                    if req.direction == "long":
                        tp_price = round(price + tp_distance, 8)
                        sl_price = round(price - sl_distance, 8)
                    else:
                        tp_price = round(price - tp_distance, 8)
                        sl_price = round(price + sl_distance, 8)
                    risk_reward = round(tp_distance / sl_distance, 2) if sl_distance > 0 else risk_reward

                if abs(amt_adj) >= 3:
                    rec_amount = round(rec_amount * (1 + amt_adj / 100), 2)
                    rec_amount = max(50, rec_amount)
                    risk_amount = round(rec_amount * sl_distance_pct, 2)

                approval = ai_risk_review.get("approval_score", 50)
                if approval < 30:
                    verdict = "SKIP"
                    reasons.append(f"❌ AI风控官否决(审批分{approval}): {ai_risk_review.get('suggestion', '')}")
                elif approval < 60:
                    if verdict != "SKIP":
                        verdict = "CAUTION"
                    reasons.append(f"⚠️ AI风控官谨慎(审批分{approval}): {ai_risk_review.get('suggestion', '')}")
                else:
                    reasons.append(f"✅ AI风控官批准(审批分{approval}): {ai_risk_review.get('suggestion', '')}")

                for pt in ai_risk_review.get("review_points", [])[:3]:
                    reasons.append(f"🛡️ {pt}")
        except Exception as e:
            logger.warning(f"AI风控官审查异常: {e}")
            ai_risk_review = {"error": str(e), "approval_score": 50, "approved": True}

    verdict_text = {
        "BUY": "🟢 建议买入",
        "CAUTION": "🟡 谨慎买入",
        "SKIP": "🔴 不建议买入",
    }.get(verdict, "🟡 谨慎")

    return {
        "verdict": verdict,
        "verdict_text": verdict_text,
        "symbol": req.symbol,
        "direction": req.direction,
        "price": price,
        "tp_price": tp_price,
        "sl_price": sl_price,
        "recommended_amount": rec_amount,
        "risk_amount": risk_amount,
        "risk_reward": risk_reward,
        "signal_score": score,
        "ml_confidence": round(ml_conf_pct, 1),
        "fng": fng,
        "regime": regime_key,
        "reasons": reasons,
        "portfolio": paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
        "ai_insight": signal.get("ai_insight", ""),
        "recommended_operation": recommended_op,
        "operation_scores": {k: round(max(0, v), 1) for k, v in op_scores.items()},
        "operation_confidence": round(op_confidence, 1),
        "adx": round(adx, 1),
        "rsi": round(rsi, 1),
        "atr_pct": round(atr_pct, 2),
        "ml_label": ml_label,
        "decision_chain": order_result.get("decision_chain", []),
        "risk_grade": risk_grade,
        "partial_tp_plan": order_result.get("partial_tp_plan", {}),
        "entry_strategy": order_result.get("entry_strategy", {}),
        "ai_risk_review": ai_risk_review,
        "ml_probabilities": ml_probs,
        "direction_prob": order_result.get("direction_prob", 0),
        "tp_distance_pct": order_result.get("tp_distance_pct", 0),
        "sl_distance_pct": order_result.get("sl_distance_pct", 0),
    }


@router.post("/api/trade/confirm")
async def trade_confirm(req: TradeConfirmRequest):
    """确认下单 - 模拟建仓"""
    from server.api import paper_trader, grid_engine, constitution, dispatcher
    
    cruise = TitanState.market_snapshot.get("cruise", [])
    signal = None
    for item in cruise:
        if item["symbol"] == req.symbol:
            signal = item
            break
    
    if not signal:
        return {"status": "error", "message": "该币种不在扫描列表中"}
    
    market_price = signal.get("price", 0)
    price = req.entry_price if req.entry_price > 0 else market_price
    if price <= 0:
        return {"status": "error", "message": "无法获取当前价格"}
    
    pt_equity = paper_trader.get_equity(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
    total_exposure = paper_trader.get_total_exposure()
    ml_pred = signal.get("ml", {})
    ml_conf = ml_pred.get("confidence", 0) if ml_pred else 0
    score = signal.get("score", 0)
    report = signal.get("report", {})
    atr = report.get("atr", price * 0.02) if report else price * 0.02
    
    sl_distance_pct = abs(req.sl_price - price) / price if price > 0 and req.sl_price > 0 else 0.02
    if len(paper_trader.positions) >= MAX_POSITIONS:
        return {"status": "error", "message": f"持仓已达上限{MAX_POSITIONS}笔,等待平仓后再开新仓"}
    can_open, reason = constitution.can_open_position(pt_equity, req.amount, total_exposure, sl_distance_pct)
    if not can_open:
        return {"status": "error", "message": f"宪法审查未通过: {reason}"}
    
    trade_strategy = dispatcher.get_strategy_for_signal(signal) if signal else "trend"
    pid = paper_trader.open_position(
        symbol=req.symbol,
        direction=req.direction,
        entry_price=price,
        tp_price=req.tp_price,
        sl_price=req.sl_price,
        position_value=req.amount,
        signal_score=score,
        ml_confidence=ml_conf,
        atr_value=atr,
        ai_verdict=f"Score:{score} ML:{ml_conf:.0f}%",
        mtf_alignment=0,
        strategy_type=trade_strategy,
    )
    
    TitanState.add_log("action", 
        f"🎯 模拟建仓: {req.symbol} {req.direction} @ ${price:.4f} 金额=${req.amount:.2f}")
    
    return {
        "status": "ok",
        "position_id": pid,
        "symbol": req.symbol,
        "direction": req.direction,
        "entry_price": price,
        "tp_price": req.tp_price,
        "sl_price": req.sl_price,
        "amount": req.amount,
    }


@router.post("/api/trade/close/{position_id}")
async def trade_close(position_id: str):
    """手动平仓"""
    from server.api import paper_trader, grid_engine, dispatcher, synapse, signal_quality, risk_budget
    from server.titan_ml import titan_critic
    from server.titan_agent import feedback_engine, governor
    from server.titan_agi import titan_agi
    from server.titan_attribution import attribution
    from server.titan_ai_reviewer import ai_reviewer

    if position_id not in paper_trader.positions:
        return {"status": "error", "message": "持仓不存在"}
    
    pos = paper_trader.positions[position_id]
    current_price = pos.get("current_price", pos["entry_price"])
    
    cruise = TitanState.market_snapshot.get("cruise", [])
    for item in cruise:
        if item["symbol"] == pos["symbol"]:
            current_price = item["price"]
            break
    
    result = paper_trader.close_position(position_id, current_price, "manual_close")
    if result:
        TitanState.add_log("action", 
            f"📊 手动平仓: {result['symbol']} PnL={result['pnl_pct']:+.2f}%")
        try:
            titan_agi.record_outcome(result['symbol'], result['pnl_pct'], result['pnl_pct'] > 0)
            attribution.record_trade({
                "symbol": result["symbol"],
                "direction": result.get("direction", "long"),
                "entry_price": result.get("entry_price", 0),
                "exit_price": result.get("exit_price", 0),
                "pnl_pct": result["pnl_pct"],
                "pnl_usd": result.get("pnl_value", 0),
                "strategy_type": "manual",
                "signal_score": result.get("signal_score", 0),
                "entry_time": result.get("open_time", ""),
                "exit_time": result.get("close_time", ""),
                "holding_hours": result.get("hold_hours", 0),
                "market_regime": dispatcher.current_regime,
            })
            titan_critic.record_trade({
                "sym": result["symbol"],
                "direction": result.get("direction", "long"),
                "entry": result.get("entry_price", 0),
                "exit": result.get("exit_price", 0),
                "pnl": result["pnl_pct"],
                "result": "win" if result["pnl_pct"] > 0 else "loss",
                "score": result.get("signal_score", 0),
                "rsi": 50,
                "adx": 20,
                "regime": dispatcher.current_regime,
                "bb_pos": 0.5,
                "vol_ratio": 1.0,
            })
            feedback_engine.record_prediction_outcome(
                result["symbol"],
                result.get("ml_label", "unknown"),
                "win" if result["pnl_pct"] > 0 else "loss",
                direction=result.get("direction", "long"),
            )
            governor.record_trade_result(result["pnl_pct"] > 0)
            close_strategy = result.get("strategy_type", "trend")
            synapse.broadcast_trade_result({
                "symbol": result["symbol"],
                "strategy_type": close_strategy,
                "pnl_pct": result["pnl_pct"],
                "market_regime": dispatcher.current_regime,
                "direction": result.get("direction", "long"),
                "signal_score": result.get("signal_score", 0),
                "holding_hours": result.get("hold_hours", 0),
            })
            risk_budget.release_capital(close_strategy, result.get("position_value", 0), result.get("pnl_value", 0))
            try:
                close_conditions = signal_quality.extract_conditions(result.get("report", {}), dispatcher.current_regime)
                signal_quality.record_outcome(close_conditions, result["pnl_pct"] > 0, result["pnl_pct"], result["symbol"], dispatcher.current_regime)
            except Exception:
                pass
            try:
                ai_reviewer.queue_trade_for_review({
                    "symbol": result["symbol"],
                    "direction": result.get("direction", "long"),
                    "strategy_type": close_strategy,
                    "pnl_pct": result["pnl_pct"],
                    "holding_hours": result.get("hold_hours", 0),
                    "market_regime": dispatcher.current_regime,
                    "signal_score": result.get("signal_score", 0),
                    "entry_price": result.get("entry_price", 0),
                    "exit_price": result.get("exit_price", 0),
                    "close_reason": "manual_close",
                })
            except Exception:
                pass
        except Exception:
            pass
        return {"status": "ok", "trade": result}
    return {"status": "error", "message": "平仓失败"}


@router.get("/api/paper/positions")
async def get_paper_positions():
    """获取模拟持仓列表"""
    from server.api import paper_trader, grid_engine, constitution

    snapshot = TitanState.market_snapshot
    live_prices = snapshot.get("_live_prices", {})
    cruise_prices = {item["symbol"]: item["price"] for item in snapshot.get("cruise", []) if item.get("price", 0) > 0}
    price_map = {**cruise_prices, **live_prices}

    return {
        "positions": paper_trader.get_positions_display(price_map),
        "portfolio": paper_trader.get_portfolio_summary(price_map, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
        "constitution": {
            **constitution.get_status(),
            "status": "HEALTHY",
        },
    }


@router.get("/api/paper/trades")
async def get_paper_trades():
    """获取模拟交易历史"""
    from server.api import paper_trader, grid_engine

    snapshot = TitanState.market_snapshot
    live_prices = snapshot.get("_live_prices", {})
    cruise_prices = {item["symbol"]: item["price"] for item in snapshot.get("cruise", []) if item.get("price", 0) > 0}
    price_map = {**cruise_prices, **live_prices}
    return {
        "trades": paper_trader.get_recent_trades(50),
        "summary": paper_trader.get_portfolio_summary(price_map, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
    }


@router.get("/api/trades/history")
async def get_trade_history():
    from server.api import paper_trader

    trades = paper_trader.get_recent_trades(50)
    positions = paper_trader.get_positions_display()
    return {
        "trades": trades,
        "positions": list(positions) if isinstance(positions, list) else positions,
        "total_trades": paper_trader.total_wins + paper_trader.total_losses,
        "total_wins": paper_trader.total_wins,
        "total_losses": paper_trader.total_losses,
        "win_rate": round(paper_trader.total_wins / max(1, paper_trader.total_wins + paper_trader.total_losses) * 100, 1),
        "consecutive_wins": paper_trader.consecutive_wins,
        "consecutive_losses": paper_trader.consecutive_losses,
    }
