import os
import json
import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from server.titan_state import CONFIG, TitanState, get_coin_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["ai_modules"])

MAX_POSITIONS = 8


@router.post("/api/adaptive/ai-optimize")
async def ai_optimize_adaptive_weights():
    from server.api import adaptive_weights, paper_trader
    aw_status = adaptive_weights.get_adaptive_weights()
    trades = paper_trader.get_recent_trades(30)

    if len(trades) < 5:
        return {"status": "insufficient_data", "message": "需要至少5笔交易数据才能AI优化"}

    trade_summary = []
    for t in trades[-20:]:
        trade_summary.append({
            "pnl_pct": t.get("pnl_pct", 0),
            "signal_score": t.get("signal_score", 0),
            "ml_confidence": t.get("ml_confidence", 0),
            "strategy_type": t.get("strategy_type", ""),
            "close_reason": t.get("close_reason", ""),
        })

    wins = sum(1 for t in trade_summary if t["pnl_pct"] > 0)
    losses = len(trade_summary) - wins
    avg_win = sum(t["pnl_pct"] for t in trade_summary if t["pnl_pct"] > 0) / max(1, wins)
    avg_loss = sum(t["pnl_pct"] for t in trade_summary if t["pnl_pct"] < 0) / max(1, losses)

    high_ml_trades = [t for t in trade_summary if t["ml_confidence"] > 60]
    ml_win_rate = sum(1 for t in high_ml_trades if t["pnl_pct"] > 0) / max(1, len(high_ml_trades)) if high_ml_trades else 0.5
    high_rule_trades = [t for t in trade_summary if t["signal_score"] >= 85]
    rule_win_rate = sum(1 for t in high_rule_trades if t["pnl_pct"] > 0) / max(1, len(high_rule_trades)) if high_rule_trades else 0.5

    try:
        from server.titan_llm_client import chat_json
        from server.titan_prompt_library import WEIGHT_OPTIMIZER_PROMPT, PHASE_ZERO_CONTEXT
        prompt = PHASE_ZERO_CONTEXT + f"""当前权重: 规则={aw_status['w_rule']*100:.0f}%, ML={aw_status['w_ml']*100:.0f}%, 当前等级={aw_status['tier']}
ML准确率: {aw_status['performance']*100:.1f}%, 已评估: {aw_status['evaluated']}条

最近交易统计:
- 总交易: {len(trade_summary)}笔, 胜率: {wins}/{len(trade_summary)}={wins/max(1,len(trade_summary))*100:.0f}%
- 平均盈利: {avg_win:.2f}%, 平均亏损: {avg_loss:.2f}%
- 高ML信心交易胜率: {ml_win_rate*100:.0f}% ({len(high_ml_trades)}笔)
- 高规则评分交易胜率: {rule_win_rate*100:.0f}% ({len(high_rule_trades)}笔)

请分析当前权重是否合理,并给出优化建议。"""

        result = chat_json(
            module="api_ai_coordination",
            messages=[{"role": "system", "content": WEIGHT_OPTIMIZER_PROMPT}, {"role": "user", "content": prompt}],
            max_tokens=500,
        )
        if not result:
            raise Exception("AI返回空结果")

        new_w_rule = max(0.1, min(0.9, result.get("recommended_w_rule", aw_status['w_rule'])))
        new_w_ml = round(1.0 - new_w_rule, 2)

        if result.get("confidence", 0) >= 0.5:
            adaptive_weights.ml_weight_override = new_w_ml
            adaptive_weights.performance_score = new_w_ml

        TitanState.add_log("system", f"🧠 AI优化权重: 规则{new_w_rule*100:.0f}%→ML{new_w_ml*100:.0f}% | {result.get('analysis','')}")

        return {
            "status": "ok",
            "current": {"w_rule": aw_status['w_rule'], "w_ml": aw_status['w_ml']},
            "recommended": {"w_rule": new_w_rule, "w_ml": new_w_ml},
            "analysis": result.get("analysis", ""),
            "reasoning": result.get("reasoning", ""),
            "confidence": result.get("confidence", 0),
        }
    except Exception as e:
        logging.getLogger("Titan").warning(f"AI权重优化异常: {e}")
        if ml_win_rate > rule_win_rate + 0.1:
            new_w_ml = min(0.5, aw_status['w_ml'] + 0.05)
        elif rule_win_rate > ml_win_rate + 0.1:
            new_w_ml = max(0.1, aw_status['w_ml'] - 0.05)
        else:
            new_w_ml = aw_status['w_ml']
        new_w_rule = round(1.0 - new_w_ml, 2)

        return {
            "status": "fallback",
            "current": {"w_rule": aw_status['w_rule'], "w_ml": aw_status['w_ml']},
            "recommended": {"w_rule": new_w_rule, "w_ml": new_w_ml},
            "analysis": f"规则胜率{rule_win_rate*100:.0f}% vs ML胜率{ml_win_rate*100:.0f}%",
            "reasoning": "基于规则回退分析",
        }


@router.get("/api/ai/reviews")
async def get_ai_reviews():
    from server.api import ai_reviewer
    return ai_reviewer.get_status()


@router.post("/api/ai/review/trigger")
async def trigger_ai_review():
    from server.api import paper_trader, dispatcher, ai_reviewer, synapse, risk_budget
    trades = paper_trader.get_recent_trades(10)
    if not trades:
        return {"status": "no_data", "message": "暂无交易数据可复盘"}

    trade_data = []
    for t in trades[:5]:
        trade_data.append({
            "symbol": t.get("symbol", ""),
            "direction": t.get("direction", "long"),
            "strategy_type": t.get("strategy_type", "trend"),
            "pnl_pct": t.get("pnl_pct", 0),
            "holding_hours": t.get("hold_hours", 0),
            "market_regime": dispatcher.current_regime,
            "signal_score": t.get("signal_score", 0),
            "entry_price": t.get("entry_price", 0),
            "exit_price": t.get("exit_price", 0),
            "close_reason": t.get("close_reason", ""),
        })

    result = ai_reviewer.batch_review(
        trades=trade_data,
        synapse_status=synapse.get_status(),
        risk_budget_status=risk_budget.get_status(),
        dispatcher_status=dispatcher.get_status(),
    )
    return {"status": "ok", "review": result}


@router.get("/api/ai/watchdog")
async def get_watchdog_status():
    from server.api import watchdog
    return watchdog.get_status()


@router.post("/api/ai/watchdog/diagnose")
async def trigger_watchdog_diagnosis():
    from server.api import watchdog
    result = watchdog.ai_diagnose(force=True)
    return {"status": "ok", "diagnosis": result}


@router.post("/api/ai/watchdog/resolve/{alert_id}")
async def resolve_watchdog_alert(alert_id: str):
    from server.api import watchdog
    watchdog.resolve_alert(alert_id)
    return {"status": "ok", "message": "警报已解除"}


@router.post("/api/ai/watchdog/check")
async def trigger_health_check():
    from server.api import watchdog, paper_trader, risk_budget, dispatcher, synapse, signal_quality, constitution
    market_info = {
        "btc_price": TitanState.market_snapshot.get("btc_pulse", {}).get("price", 0),
        "scan_count": TitanState.market_snapshot.get("total_scanned", 0),
        "last_scan": TitanState.market_snapshot.get("last_scan_time", ""),
    }
    result = watchdog.run_health_check(
        paper_trader=paper_trader,
        risk_budget=risk_budget,
        dispatcher=dispatcher,
        synapse=synapse,
        signal_quality=signal_quality,
        constitution=constitution,
        market_data=market_info,
    )
    return {"status": "ok", "health": result}


@router.get("/api/ai/coordinator")
async def get_coordinator_status():
    from server.api import ai_coordinator
    return ai_coordinator.get_status()


@router.post("/api/ai/coordinator/coordinate")
async def trigger_coordination():
    from server.api import ai_coordinator, adaptive_weights, risk_budget, dispatcher, synapse, signal_quality, paper_trader, feedback_engine, grid_engine, ai_reviewer, agent_memory, titan_agi, capital_sizer
    _diagnostic = None
    _rra = None
    try:
        from server.titan_ai_diagnostic import ai_diagnostic as _diag
        _diagnostic = _diag
    except Exception:
        pass
    try:
        from server.titan_return_rate_agent import return_rate_agent as _rra_mod
        _rra = _rra_mod
    except Exception:
        pass
    result = ai_coordinator.coordinate(
        adaptive_weights=adaptive_weights,
        risk_budget=risk_budget,
        dispatcher=dispatcher,
        synapse=synapse,
        signal_quality=signal_quality,
        paper_trader=paper_trader,
        feedback=feedback_engine,
        grid_engine=grid_engine,
        use_ai=True,
        reviewer=ai_reviewer,
        diagnostic=_diagnostic,
        return_rate_agent=_rra,
        agent_memory=agent_memory,
        agi=titan_agi,
    )
    capital_sizer.update_global_multipliers(
        "ai_override_mult", ai_coordinator.get_size_multiplier()
    )
    TitanState.add_log("system", f"🧠 AI协调完成: 仓位因子={ai_coordinator.get_size_multiplier():.2f} | {ai_coordinator.recommendations.get('reasoning', '')[:60]}")
    return result


@router.get("/api/ai-diagnostic")
async def get_ai_diagnostic():
    try:
        from server.titan_ai_diagnostic import ai_diagnostic
        return ai_diagnostic.get_status()
    except Exception as e:
        return {"error": str(e)}

@router.get("/api/ai-diagnostic/history")
async def get_ai_diagnostic_history():
    try:
        from server.titan_ai_diagnostic import ai_diagnostic
        return ai_diagnostic.get_history()
    except Exception as e:
        return {"error": str(e)}

@router.post("/api/ai-diagnostic/run")
async def run_ai_diagnostic():
    from server.api import ml_engine, paper_trader, return_target, risk_budget, dispatcher, synapse, signal_quality, ai_coordinator, unified_decision, constitution, adaptive_weights, feedback_engine, mega_backtest, grid_engine
    try:
        from server.titan_ai_diagnostic import ai_diagnostic
        diag_modules = {
            "ml_engine": ml_engine,
            "paper_trader": paper_trader,
            "return_target": return_target,
            "risk_budget": risk_budget,
            "dispatcher": dispatcher,
            "synapse": synapse,
            "signal_quality": signal_quality,
            "ai_coordinator": ai_coordinator,
            "unified_decision": unified_decision,
            "constitution": constitution,
            "adaptive_weights": adaptive_weights,
            "feedback_engine": feedback_engine,
            "mega_backtest": mega_backtest,
            "grid_engine": grid_engine,
            "market_snapshot": TitanState.market_snapshot,
        }
        try:
            from server.titan_return_rate_agent import return_rate_agent
            diag_modules["return_rate_agent"] = return_rate_agent
        except Exception:
            pass
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ai_diagnostic.run_diagnostic, diag_modules)
        return result
    except Exception as e:
        return {"error": str(e)}

@router.post("/api/ai-diagnostic/auto-execute")
async def auto_execute_diagnostic():
    from server.api import ml_engine, paper_trader, return_target, risk_budget, dispatcher, synapse, signal_quality, ai_coordinator, unified_decision, constitution, adaptive_weights, feedback_engine, mega_backtest, grid_engine, titan_critic, agent_memory
    actions_log = []
    try:
        from server.titan_ai_diagnostic import ai_diagnostic
        diag_modules = {
            "ml_engine": ml_engine, "paper_trader": paper_trader, "return_target": return_target,
            "risk_budget": risk_budget, "dispatcher": dispatcher, "synapse": synapse,
            "signal_quality": signal_quality, "ai_coordinator": ai_coordinator,
            "unified_decision": unified_decision, "constitution": constitution,
            "adaptive_weights": adaptive_weights, "feedback_engine": feedback_engine,
            "mega_backtest": mega_backtest, "grid_engine": grid_engine,
            "market_snapshot": TitanState.market_snapshot,
        }
        try:
            from server.titan_return_rate_agent import return_rate_agent
            diag_modules["return_rate_agent"] = return_rate_agent
        except Exception:
            pass

        loop = asyncio.get_event_loop()
        diag_result = await loop.run_in_executor(None, ai_diagnostic.run_diagnostic, diag_modules)
        health_score = diag_result.get("health_score", diag_result.get("diagnosis", {}).get("health_score", 100))
        actions_log.append({"step": "diagnostic", "status": "ok", "health_score": health_score})

        priorities = diag_result.get("top_priorities", diag_result.get("priorities", []))

        p1_assets = []
        for p in priorities:
            if p.get("priority") == 1 and p.get("action"):
                import re
                match = re.search(r'[\(（]([^)）]+)[\)）]', p["action"])
                if match:
                    found = [a.strip() for a in re.split(r'[,，、]', match.group(1)) if a.strip()]
                    p1_assets.extend(found)
        if p1_assets:
            import re as re_diag2
            valid_sym2 = re_diag2.compile(r'^[A-Z0-9]{2,15}$')
            frozen = []
            for asset in p1_assets:
                asset_clean = asset.replace("/USDT", "").replace("_USDT", "").upper().strip()
                if not valid_sym2.match(asset_clean):
                    continue
                existing = any(r.get("type") == "asset_avoid" and r.get("asset") == asset_clean for r in synapse.cross_strategy_rules)
                if not existing:
                    synapse.cross_strategy_rules.append({
                        "type": "asset_avoid", "asset": asset_clean, "win_rate": 0, "trades": 0,
                        "applies_to": "all", "reason": f"自动诊断冻结",
                    })
                    frozen.append(asset_clean)
            if frozen:
                TitanState.add_log("system", f"🚫 自动冻结亏损资产: {', '.join(frozen)}")
                actions_log.append({"step": "freeze_assets", "status": "ok", "frozen": frozen})

        if health_score < 50:
            new_size = max(0.3, min(0.8, health_score / 100))
            ai_coordinator.recommendations["size_multiplier"] = new_size
            ai_coordinator.recommendations["throttle_level"] = "tight" if health_score < 35 else "reduced"
            ai_coordinator.save()
            TitanState.add_log("system", f"⚙️ 自动调整: size={new_size:.2f}, throttle={ai_coordinator.recommendations['throttle_level']}")
            actions_log.append({"step": "adjust_coordinator", "status": "ok", "size_multiplier": new_size, "throttle_level": ai_coordinator.recommendations["throttle_level"]})

        if health_score < 40:
            constitution.RISK_LIMITS["MAX_DAILY_DRAWDOWN"] = 0.015
            constitution.RISK_LIMITS["MAX_TOTAL_DRAWDOWN"] = 0.03
            constitution.save()
            TitanState.add_log("system", f"🛡️ 自动收紧断路器: 日回撤1.5% / 总回撤3%")
            actions_log.append({"step": "tighten_breakers", "status": "ok", "daily": 0.015, "total": 0.03})

        try:
            portfolio_equity = 0
            if hasattr(paper_trader, 'get_portfolio_summary'):
                ps = paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                portfolio_equity = ps.get("equity", 0)
            if portfolio_equity > 0:
                rb_status = risk_budget.get_status()
                rb_capital = rb_status.get("total_capital", 0)
                if rb_capital > 0 and abs(rb_capital - portfolio_equity) / max(rb_capital, 1) > 0.05:
                    if hasattr(risk_budget, 'total_capital'):
                        risk_budget.total_capital = portfolio_equity
                    if hasattr(risk_budget, 'save'):
                        risk_budget.save()
                    TitanState.add_log("system", f"💰 资金口径同步: risk_budget {rb_capital:.0f} → {portfolio_equity:.0f}")
                    actions_log.append({"step": "sync_capital", "status": "ok", "old": rb_capital, "new": portfolio_equity})
        except Exception as e:
            actions_log.append({"step": "sync_capital", "status": "error", "error": str(e)})

        try:
            fb_acc = feedback_engine.get_rolling_accuracy()
            fb_total = len(getattr(feedback_engine, 'accuracy_history', []))
            if fb_acc is not None and fb_acc < 40 and fb_total >= 20:
                feedback_engine.auto_adjust_critic(titan_critic)
                suggestions = feedback_engine.suggest_threshold_adjustments()
                for sug in suggestions:
                    if sug.get("type") == "increase_ml_weight_caution" and hasattr(adaptive_weights, 'ml_weight_override'):
                        adaptive_weights.ml_weight_override = sug.get("ml_weight", 0.25)
                    elif sug.get("type") == "raise_score_threshold":
                        ai_coordinator.recommendations["min_score_threshold"] = sug.get("value", 85)
                if suggestions:
                    TitanState.add_log("system", f"🔄 ML反馈修正: {len(suggestions)}条建议已应用 (acc={fb_acc}%)")
                    actions_log.append({"step": "ml_feedback_fix", "status": "ok", "accuracy": fb_acc, "suggestions": len(suggestions)})
            elif fb_total < 10:
                actions_log.append({"step": "ml_feedback_fix", "status": "skipped", "reason": f"预测记录不足({fb_total}条，需≥10)"})
        except Exception as e:
            actions_log.append({"step": "ml_feedback_fix", "status": "error", "error": str(e)})

        try:
            ud_status = unified_decision.get_status()
            ud_stats = ud_status.get("stats", {})
            if ud_stats.get("total_decisions", 0) == 0:
                c_status = constitution.get_status()
                ud_context = {
                    "regime": dispatcher.current_regime,
                    "coordinator_recommendations": ai_coordinator.recommendations,
                    "constitution_status": c_status,
                    "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
                    "active_positions": len(paper_trader.positions) if hasattr(paper_trader, 'positions') else 0,
                    "active_grids": len(grid_engine.active_grids) if hasattr(grid_engine, 'active_grids') else 0,
                    "dispatcher_strategies": getattr(dispatcher, 'active_strategies', ["trend", "range", "grid"]),
                    "return_target_status": return_target.get_status(),
                    "max_positions": MAX_POSITIONS,
                }
                decision = unified_decision.evaluate(ud_context)
                unified_decision.save()
                TitanState.market_snapshot["unified_decision"] = unified_decision.get_status()
                TitanState.add_log("system", f"🎯 统一决策器激活: mode={decision['mode']}, 做多≥{decision['long_threshold']}, 做空≥{decision['short_threshold']}")
                actions_log.append({"step": "activate_unified_decision", "status": "ok", "mode": decision["mode"], "long_thr": decision["long_threshold"], "short_thr": decision["short_threshold"]})
        except Exception as e:
            actions_log.append({"step": "activate_unified_decision", "status": "error", "error": str(e)})

        try:
            if not mega_backtest.running and hasattr(mega_backtest, 'generation'):
                if getattr(mega_backtest, 'generation', 0) == 0:
                    from server.titan_mega_backtest import mega_backtest as mb
                    cruise_data = TitanState.market_snapshot.get("cruise", [])
                    if cruise_data and len(cruise_data) >= 5:
                        evo_data = {}
                        for o in cruise_data[:20]:
                            sym = o.get("symbol")
                            if sym and o.get("history"):
                                evo_data[sym] = o["history"]
                        if evo_data:
                            await loop.run_in_executor(None, mega_backtest.run_evolution_cycle, evo_data, 30)
                            TitanState.add_log("system", f"🧬 进化引擎启动: 30代迭代 {len(evo_data)}资产 Calmar={mega_backtest.best_calmar:.3f}")
                            actions_log.append({"step": "trigger_evolution", "status": "ok", "assets": len(evo_data), "calmar": mega_backtest.best_calmar})
                        else:
                            actions_log.append({"step": "trigger_evolution", "status": "skipped", "reason": "无可用历史数据"})
                    else:
                        actions_log.append({"step": "trigger_evolution", "status": "skipped", "reason": "扫描数据不足"})
        except Exception as e:
            actions_log.append({"step": "trigger_evolution", "status": "error", "error": str(e)})

        try:
            from server.titan_return_rate_agent import return_rate_agent
            rra_stats = return_rate_agent.stats
            if rra_stats.get("total_thoughts", 0) == 0:
                pt_summary = paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit) if hasattr(paper_trader, 'get_portfolio_summary') else {}
                rra_context = {
                    "portfolio": pt_summary,
                    "return_target": return_target.get_status(),
                    "ml_status": ml_engine.get_status(),
                    "risk_budget": risk_budget.get_status(),
                    "dispatcher": dispatcher.get_status(),
                    "coordinator": ai_coordinator.get_status(),
                    "synapse": synapse.get_status(),
                    "signal_quality": signal_quality.get_status(),
                }
                rra_result = return_rate_agent.periodic_review(rra_context, agent_memory, ai_coordinator, return_target)
                TitanState.market_snapshot["return_rate_agent"] = return_rate_agent.get_status()
                applied_count = rra_result.get("applied", 0)
                TitanState.add_log("system", f"🧠 收益智能体首次激活: {applied_count}条建议已应用")
                actions_log.append({"step": "activate_rra", "status": "ok", "applied": applied_count, "severity": rra_result.get("severity")})
        except Exception as e:
            actions_log.append({"step": "activate_rra", "status": "error", "error": str(e)})

        critic_result = None
        critic_applied = {"applied": 0, "rules": []}
        try:
            critic_result = await loop.run_in_executor(None, titan_critic.ai_deep_review)
            if critic_result:
                critic_applied = titan_critic.auto_apply_suggestions(critic_result)
                if critic_applied["applied"] > 0:
                    TitanState.add_log("system", f"🧠 Critic自动应用{critic_applied['applied']}条规则")
                actions_log.append({"step": "critic_review", "status": "ok", "risk_score": critic_result.get("risk_score"), "rules_applied": critic_applied["applied"]})
        except Exception as e:
            actions_log.append({"step": "critic_review", "status": "error", "error": str(e)})

        return {
            "status": "ok",
            "diagnostic": diag_result,
            "critic_review": critic_result,
            "critic_auto_applied": critic_applied,
            "actions_executed": actions_log,
            "total_actions": len(actions_log),
        }
    except Exception as e:
        return {"error": str(e), "actions_executed": actions_log}


@router.post("/api/asset/freeze")
async def freeze_assets(request: Request):
    from server.api import synapse, paper_trader
    try:
        body = await request.json()
        assets = body.get("assets", [])
        if not assets:
            return {"error": "未提供需要冻结的资产列表", "status": "failed"}
        reason = body.get("reason", "AI诊断建议冻结")
        frozen = []
        already = []
        import re as _re_freeze
        for asset in assets:
            asset_clean = asset.replace("/USDT", "").replace("_USDT", "").upper()
            if not _re_freeze.match(r'^[A-Z0-9]{2,15}$', asset_clean):
                continue
            existing = any(
                r.get("type") == "asset_avoid" and r.get("asset") == asset_clean
                for r in synapse.cross_strategy_rules
            )
            if existing:
                already.append(asset_clean)
                continue
            synapse.cross_strategy_rules.append({
                "type": "asset_avoid",
                "asset": asset_clean,
                "win_rate": 0,
                "trades": 0,
                "applies_to": "all",
                "reason": f"手动冻结: {reason}",
            })
            frozen.append(asset_clean)
            TitanState.add_log("system", f"🚫 资产冻结: {asset_clean} ({reason})")

        active_positions = paper_trader.get_positions_display() if hasattr(paper_trader, 'get_positions_display') else []
        closed = []
        for pos in active_positions:
            pos_sym = pos.get("symbol", "").replace("/USDT", "").replace("_USDT", "").upper()
            if pos_sym in [a.replace("/USDT", "").replace("_USDT", "").upper() for a in assets]:
                try:
                    price_data = TitanState.market_snapshot.get("prices", {})
                    current_price = price_data.get(pos.get("symbol", ""), pos.get("entry_price", 0))
                    result = paper_trader.close_position(pos["id"], current_price, "diagnostic_freeze")
                    if result:
                        closed.append(pos.get("symbol", ""))
                except Exception:
                    pass

        return {
            "status": "ok",
            "frozen": frozen,
            "already_frozen": already,
            "closed_positions": closed,
            "message": f"已冻结{len(frozen)}个资产" + (f"，{len(already)}个已在黑名单中" if already else "") + (f"，强制平仓{len(closed)}笔" if closed else ""),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/asset/frozen")
async def get_frozen_assets():
    from server.api import synapse
    frozen = [r for r in synapse.cross_strategy_rules if r.get("type") == "asset_avoid"]
    return {"frozen_assets": frozen, "count": len(frozen)}


@router.post("/api/asset/frozen/cleanup")
async def cleanup_frozen_garbage():
    from server.api import synapse
    import re
    before = len(synapse.cross_strategy_rules)
    valid_symbol_pattern = re.compile(r'^[A-Z0-9]{2,15}$')
    garbage = []
    clean_rules = []
    for r in synapse.cross_strategy_rules:
        if r.get("type") == "asset_avoid":
            asset_name = r.get("asset", "")
            normalized = asset_name.replace("/USDT", "").replace("_USDT", "").replace("-", "").upper().strip()
            if not valid_symbol_pattern.match(normalized):
                garbage.append(asset_name)
                continue
        clean_rules.append(r)
    synapse.cross_strategy_rules = clean_rules
    removed = before - len(clean_rules)
    if removed > 0:
        synapse.save()
        TitanState.add_log("system", f"🧹 清理{removed}条垃圾冻结条目: {garbage}")
    return {"status": "ok", "removed_count": removed, "garbage_entries": garbage, "remaining": len(clean_rules)}


@router.delete("/api/asset/freeze/{asset}")
async def unfreeze_asset(asset: str):
    from server.api import synapse
    asset_clean = asset.replace("/USDT", "").replace("_USDT", "").upper()
    before = len(synapse.cross_strategy_rules)
    synapse.cross_strategy_rules = [
        r for r in synapse.cross_strategy_rules
        if not (r.get("type") == "asset_avoid" and r.get("asset") == asset_clean)
    ]
    removed = before - len(synapse.cross_strategy_rules)
    if removed > 0:
        synapse.save()
        TitanState.add_log("system", f"✅ 资产解冻: {asset_clean}")
    return {"status": "ok", "asset": asset_clean, "removed": removed > 0}


@router.post("/api/ai-diagnostic/execute")
async def execute_diagnostic_action(request: Request):
    from server.api import synapse, constitution
    try:
        body = await request.json()
        action_id = body.get("action_id", "")
        action_type = body.get("type", "")
        results = []

        if action_type == "freeze_assets":
            assets = body.get("assets", [])
            reason = body.get("reason", "P1诊断建议")
            frozen = []
            for asset in assets:
                asset_clean = asset.replace("/USDT", "").replace("_USDT", "").upper()
                existing = any(
                    r.get("type") == "asset_avoid" and r.get("asset") == asset_clean
                    for r in synapse.cross_strategy_rules
                )
                if not existing:
                    synapse.cross_strategy_rules.append({
                        "type": "asset_avoid",
                        "asset": asset_clean,
                        "win_rate": 0,
                        "trades": 0,
                        "applies_to": "all",
                        "reason": f"诊断执行: {reason}",
                    })
                    frozen.append(asset_clean)
                    TitanState.add_log("system", f"🚫 P1冻结: {asset_clean}")
            results.append({"action": "freeze_assets", "frozen": frozen})

        elif action_type == "enable_risk_limits":
            constitution.RISK_LIMITS["MAX_DAILY_DRAWDOWN"] = body.get("daily_limit", 0.02)
            constitution.RISK_LIMITS["MAX_TOTAL_DRAWDOWN"] = body.get("total_limit", 0.05)
            TitanState.add_log("system", f"⚠️ P3风控阈值已启用: 日回撤{constitution.RISK_LIMITS['MAX_DAILY_DRAWDOWN']*100}% / 总回撤{constitution.RISK_LIMITS['MAX_TOTAL_DRAWDOWN']*100}%")
            results.append({"action": "enable_risk_limits", "daily": constitution.RISK_LIMITS["MAX_DAILY_DRAWDOWN"], "total": constitution.RISK_LIMITS["MAX_TOTAL_DRAWDOWN"]})

        elif action_type == "calibrate_signals":
            TitanState.add_log("system", "📊 P2信号校准: 需要持续运行积累数据，已标记优先校准")
            results.append({"action": "calibrate_signals", "status": "marked"})

        else:
            return {"error": f"未知操作类型: {action_type}"}

        return {"status": "ok", "action_id": action_id, "results": results}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/critic/ai-review")
async def trigger_critic_ai_review():
    from server.api import titan_critic
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, titan_critic.ai_deep_review)
        if result:
            _pipe_critic_bans_to_evolution(result)
            return {"status": "ok", "review": result}
        trade_count = len(titan_critic.trade_history)
        if trade_count < 5:
            return {"status": "skipped", "reason": f"交易数据不足（当前{trade_count}笔，需要至少5笔历史交易才能进行AI复盘分析）"}
        return {"status": "skipped", "reason": "AI未配置或复盘分析暂时不可用"}
    except Exception as e:
        return {"error": str(e)}


def _pipe_critic_bans_to_evolution(review_result):
    try:
        bans = review_result.get("new_ban_suggestions", [])
        if not bans:
            return
        from server.titan_db import db_connection
        created = 0
        with db_connection(dict_cursor=True) as (conn, cur):
            for ban in bans:
                confidence = ban.get("confidence", 0)
                if confidence < 80:
                    continue
                condition = ban.get("condition", "")
                reason = ban.get("reason", "")
                target = f"critic_ban_{condition[:40].replace(' ', '_').lower()}"

                cur.execute("""
                    SELECT COUNT(*) as n FROM evolution_proposals
                    WHERE target = %s AND status = 'pending'
                """, (target,))
                row = cur.fetchone()
                if row and row.get('n', 0) > 0:
                    continue

                cur.execute("""
                    INSERT INTO evolution_proposals
                    (target, suggested_value, confidence, risk_level, status, source, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    target,
                    "true",
                    confidence / 100.0,
                    "medium",
                    "pending",
                    "critic_analysis",
                    f"Critic AI建议: {condition}。原因: {reason}"
                ))
                created += 1
            conn.commit()

        if created > 0:
            logger.info(f"[Critic→Evolution] 生成{created}条进化提案")
    except Exception as e:
        logger.warning(f"[Critic→Evolution] 管道异常(非致命): {e}")

@router.post("/api/dispatcher/ai-analysis")
async def trigger_dispatcher_ai():
    from server.api import dispatcher
    try:
        fng = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
        btc_data = TitanState.market_snapshot.get("btc", {})
        cruise = TitanState.market_snapshot.get("cruise", [])
        signals = sorted(cruise, key=lambda x: x.get("score", 0), reverse=True)[:10] if cruise else []
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, dispatcher.ai_analyze_market, signals, fng, btc_data)
        if result:
            return {"status": "ok", "analysis": result}
        return {"status": "skipped", "reason": "AI not configured or no signals"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/signal-quality/ai-evaluate")
async def signal_quality_ai_evaluate():
    from server.api import signal_quality
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, signal_quality.ai_evaluate_summary)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/api/portfolio-correlation")
async def portfolio_correlation():
    from server.api import paper_trader, risk_matrix
    from server.titan_portfolio_analyst import portfolio_correlation_analyst
    try:
        positions = list(getattr(paper_trader, 'positions', {}).values()) if hasattr(paper_trader, 'positions') else []
        if not positions:
            return {"status": "no_positions", "correlation_risk": "low", "risk_score": 0}

        price_data = {}
        cruise = TitanState.market_snapshot.get("cruise", [])
        for item in cruise:
            sym = item.get("sym", item.get("symbol", "")).replace("/USDT", "").replace("_USDT", "")
            history = item.get("history", [])
            if sym and history:
                price_data[sym] = history

        try:
            from server.titan_grid import grid_engine
            grid_pnl = grid_engine.get_unrealized_pnl()
            grid_realized = grid_engine.total_grid_profit
        except Exception:
            grid_pnl = 0
            grid_realized = 0

        equity = paper_trader.get_equity(grid_pnl=grid_pnl, grid_realized_pnl=grid_realized) if hasattr(paper_trader, 'get_equity') else 100000

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, portfolio_correlation_analyst.analyze, positions, price_data, equity
        )
        return {"status": "ok", "analysis": result}
    except Exception as e:
        logger.error(f"Portfolio correlation分析异常: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/regime-transition")
async def regime_transition():
    from server.api import dispatcher, paper_trader
    from server.titan_portfolio_analyst import regime_transition_detector
    try:
        btc_pulse = TitanState.market_snapshot.get("btc_pulse", {})
        fng_detail = btc_pulse.get("fng_detail", {})
        cruise = TitanState.market_snapshot.get("cruise", [])

        btc_vol_1h = 0
        btc_vol_7d_avg = 0
        volume_ratio = 1.0
        btc_data = None
        for item in cruise:
            sym = item.get("sym", item.get("symbol", ""))
            if sym and "BTC" in sym:
                btc_data = item
                break

        if btc_data and btc_data.get("history"):
            import numpy as np_rt
            prices = np_rt.array(btc_data["history"], dtype=float)
            if len(prices) >= 24:
                returns_1h = np_rt.abs(np_rt.diff(prices[-2:])) / (prices[-2] + 1e-10)
                btc_vol_1h = float(returns_1h[0]) if len(returns_1h) > 0 else 0
                returns_7d = np_rt.abs(np_rt.diff(prices[-168:])) / (prices[-168:-1] + 1e-10)
                btc_vol_7d_avg = float(np_rt.mean(returns_7d)) if len(returns_7d) > 0 else btc_vol_1h

            if btc_data.get("volume_history"):
                vols = btc_data["volume_history"]
                if len(vols) >= 7:
                    recent_vol = vols[-1] if vols else 0
                    avg_vol = sum(vols[-7:]) / 7 if len(vols) >= 7 else recent_vol
                    volume_ratio = recent_vol / (avg_vol + 1e-10) if avg_vol > 0 else 1.0

        high_score_count = sum(1 for item in cruise if item.get("score", 0) >= 65) if cruise else 0
        recent_sl = 0
        try:
            recent_trades = paper_trader.get_recent_trades(10) if hasattr(paper_trader, 'get_recent_trades') else []
            for t in recent_trades:
                if t.get("close_reason", "").lower() in ("sl", "stop_loss", "sl_hit"):
                    recent_sl += 1
        except Exception:
            pass

        market_data = {
            "regime": getattr(dispatcher, "current_regime", "unknown"),
            "btc_price": btc_pulse.get("price", 0),
            "fng": btc_pulse.get("fng", 50),
            "fng_prev": fng_detail.get("avg_7d", btc_pulse.get("fng", 50)),
            "btc_vol_1h": btc_vol_1h,
            "btc_vol_7d_avg": btc_vol_7d_avg,
            "volume_ratio": volume_ratio,
            "recent_stop_losses": recent_sl,
            "high_score_signals": high_score_count,
            "active_positions": len(getattr(paper_trader, 'positions', {})),
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, regime_transition_detector.detect, market_data)
        return {"status": "ok", "detection": result}
    except Exception as e:
        logger.error(f"Regime transition检测异常: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/synapse/ai-insights")
async def synapse_ai_insights():
    from server.api import synapse
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, synapse.ai_cross_strategy_insights)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/api/mailer/ai-summary")
async def mailer_ai_summary():
    from server.api import TitanMailer, ml_engine, paper_trader, grid_engine
    try:
        alpha_signals = TitanState.market_snapshot.get("cruise", [])
        market_info = {
            "btc": TitanState.market_snapshot.get("btc_pulse", {}),
            "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng_detail", {"value": 50, "label": "Neutral"}),
            "total_scanned": TitanState.market_snapshot.get("total_scanned", 0),
        }
        ml_status = ml_engine.get_status()
        paper_portfolio = paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit) if hasattr(paper_trader, 'get_portfolio_summary') else {}
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, TitanMailer.ai_generate_summary, alpha_signals, market_info, ml_status, paper_portfolio)
        return {"summary": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
