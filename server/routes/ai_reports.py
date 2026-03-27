import os
import json
import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

import pandas as pd
import pytz

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.titan_state import TitanState, CONFIG
from server.titan_ai_coordinator import ai_coordinator
from server.titan_db import TitanDB
from server.titan_ml import ml_engine, adaptive_weights, titan_critic
from server.titan_money_manager import money_manager
from server.titan_agent import agent_memory, governor, feedback_engine
from server.titan_dispatcher import dispatcher
from server.titan_grid import grid_engine
from server.titan_unified_decision import unified_decision
from server.titan_return_target import return_target
from server.titan_ai_reviewer import ai_reviewer
from server.titan_mega_backtest import mega_backtest
from server.titan_monte_carlo import monte_carlo
from server.titan_synapse import TitanSynapse
from server.titan_risk_budget import TitanRiskBudget
from server.titan_signal_quality import TitanSignalQuality
from server.titan_constitution import TitanConstitution
from server.titan_paper_trader import TitanPaperTrader
from server.titan_autopilot import TitanAutoPilot
from server.titan_external_data import TitanExternalDataManager
from server.titan_self_inspector import TitanSelfInspector
from server.titan_agi import titan_agi

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["ai_reports"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

paper_trader = TitanPaperTrader()
synapse = TitanSynapse()
risk_budget = TitanRiskBudget()
signal_quality = TitanSignalQuality()
constitution = TitanConstitution()
autopilot = TitanAutoPilot()
external_data = TitanExternalDataManager()
self_inspector = TitanSelfInspector()

_cto_briefing_state = {"status": "idle", "log": [], "results": {}, "errors": [], "started_at": None, "finished_at": None}


class _TitanMailerHelper:
    _last_emergency_email_time = 0

    @staticmethod
    def get_receivers():
        receivers = []
        r1 = os.getenv('RECEIVER_EMAIL')
        r2 = os.getenv('RECEIVER_EMAIL_2')
        if r1:
            receivers.append(r1)
        if r2:
            receivers.append(r2)
        return receivers


TitanMailer = _TitanMailerHelper


@router.get("/api/cto-briefing-status")
async def get_cto_briefing_status():
    import copy
    state = _cto_briefing_state
    return {
        "status": state.get("status", "idle"),
        "log": list(state.get("log", [])),
        "results": state.get("results", {}),
        "errors": list(state.get("errors", [])),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "summary": state.get("summary", ""),
        "elapsed_seconds": state.get("elapsed_seconds", ""),
    }

async def _run_cto_briefing():
    global _cto_briefing_state
    import time as _time
    start = _time.time()
    tz = pytz.timezone(CONFIG['TIMEZONE'])
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    briefing_log = []
    errors = []
    results = {}
    retrain_ml = _cto_briefing_state.get("_retrain_ml", False)
    _cto_briefing_state = {"status": "running", "log": briefing_log, "results": results, "errors": errors, "started_at": now_str, "finished_at": None}

    def log_step(msg):
        briefing_log.append(f"[{datetime.now(tz).strftime('%H:%M:%S')}] {msg}")
        print(f"[CTO-BRIEFING] {msg}", flush=True)
        TitanState.add_log("system", f"📋 CTO简报: {msg}")
    try:
        await _run_cto_briefing_inner(start, tz, now_str, briefing_log, errors, results, log_step, retrain_ml=retrain_ml)
    except Exception as fatal_err:
        errors.append(f"fatal: {fatal_err}")
        log_step(f"=== CTO简报致命错误: {fatal_err} ===")
    finally:
        elapsed_final = round(_time.time() - start, 1)
        _cto_briefing_state.update({
            "status": "completed" if not errors else "partial",
            "finished_at": datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S'),
            "elapsed_seconds": elapsed_final,
        })

async def _run_cto_briefing_inner(start, tz, now_str, briefing_log, errors, results, log_step, retrain_ml=False):
    import time as _time
    log_step("=== CTO全面简报流程启动 ===")

    log_step("[1/4] 数据清洗启动...")
    try:
        trades_path = os.path.join(BASE_DIR, "data", "titan_trades.json")
        trades_data = []
        if os.path.exists(trades_path):
            with open(trades_path) as f:
                trades_data = json.load(f)

        original_count = len(trades_data)
        cleaned_trades = []
        removed_reasons = {}

        for t in trades_data:
            issues = []
            if not t.get("symbol"):
                issues.append("missing_symbol")
            if not t.get("entry_price") or t["entry_price"] <= 0:
                issues.append("invalid_entry_price")
            if not t.get("exit_price") or t["exit_price"] <= 0:
                issues.append("invalid_exit_price")
            if t.get("pnl_pct") is None:
                issues.append("missing_pnl")
            if not t.get("direction"):
                issues.append("missing_direction")

            if t.get("strategy_type") in ("unknown", "", None):
                ai_v = (t.get("ai_verdict") or "").lower()
                reason = (t.get("reason") or "").lower()
                combined = f"{ai_v} {reason}"
                if "grid" in combined:
                    t["strategy_type"] = "grid"
                elif "range" in combined:
                    t["strategy_type"] = "range"
                elif "short" in combined or "做空" in combined:
                    t["strategy_type"] = "trend"
                else:
                    t["strategy_type"] = "trend"

            if issues:
                for i in issues:
                    removed_reasons[i] = removed_reasons.get(i, 0) + 1
            else:
                cleaned_trades.append(t)

        removed_count = original_count - len(cleaned_trades)
        with open(trades_path, "w") as f:
            json.dump(cleaned_trades, f, ensure_ascii=False, indent=2)

        synapse_path = os.path.join(BASE_DIR, "data", "titan_synapse.json")
        synapse_cleaned = False
        if os.path.exists(synapse_path):
            try:
                with open(synapse_path) as f:
                    syn_data = json.load(f)
                broadcast_log = syn_data.get("broadcast_log", [])
                if len(broadcast_log) > 200:
                    syn_data["broadcast_log"] = broadcast_log[-200:]
                    synapse_cleaned = True
                kb = syn_data.get("knowledge_base", {})
                for sym, entries in kb.items():
                    if isinstance(entries, list) and len(entries) > 50:
                        kb[sym] = entries[-50:]
                        synapse_cleaned = True
                if synapse_cleaned:
                    with open(synapse_path, "w") as f:
                        json.dump(syn_data, f, ensure_ascii=False, indent=2)
            except Exception as syn_e:
                errors.append(f"synapse_clean: {syn_e}")

        feedback_path = os.path.join(BASE_DIR, "data", "titan_feedback.json")
        feedback_cleaned = False
        if os.path.exists(feedback_path):
            try:
                with open(feedback_path) as f:
                    fb_data = json.load(f)
                acc_hist = fb_data.get("accuracy_history", [])
                if len(acc_hist) > 100:
                    fb_data["accuracy_history"] = acc_hist[-100:]
                    feedback_cleaned = True
                if feedback_cleaned:
                    with open(feedback_path, "w") as f:
                        json.dump(fb_data, f, ensure_ascii=False, indent=2)
            except Exception as fb_e:
                errors.append(f"feedback_clean: {fb_e}")

        results["data_cleaning"] = {
            "original_trades": original_count,
            "cleaned_trades": len(cleaned_trades),
            "removed": removed_count,
            "removed_reasons": removed_reasons,
            "strategy_fixed": sum(1 for t in cleaned_trades if t.get("_strategy_fixed")),
            "synapse_trimmed": synapse_cleaned,
            "feedback_trimmed": feedback_cleaned,
        }
        log_step(f"[1/4] 数据清洗完成: {original_count}→{len(cleaned_trades)}笔交易, 移除{removed_count}笔无效, Synapse/Feedback已精简")

    except Exception as e:
        errors.append(f"data_cleaning: {e}")
        log_step(f"[1/4] 数据清洗异常: {e}")

    if retrain_ml:
        log_step("[2/4] ML模型重训练启动(数据获取中,最长5分钟)...")
    else:
        log_step("[2/4] ML重训练已跳过(使用已有模型), 可通过 retrain_ml=true 强制重训")
        results["ml_retrain"] = {"status": "skipped", "reason": "使用已有模型,如需重训请加 retrain_ml=true 参数"}
    if retrain_ml:
        try:
            training_data = None
            local_ohlcv_path = os.path.join(BASE_DIR, "data", "titan_historical_ohlcv.json")
            if os.path.exists(local_ohlcv_path):
                log_step("[2/4] 优先使用本地历史数据(29资产×540根4H)...")
                try:
                    with open(local_ohlcv_path) as f:
                        local_ohlcv = json.load(f)
                    training_data = {}
                    for coin, info in local_ohlcv.items():
                        candles = info.get('data', [])
                        if len(candles) >= 100:
                            df_4h = pd.DataFrame(candles, columns=['t','o','h','l','c','v'])
                            for col in ['o','h','l','c','v']:
                                df_4h[col] = df_4h[col].astype(float)
                            df_1h = df_4h.copy()
                            training_data[coin] = {'1h': df_1h, '4h': df_4h}
                    log_step(f"[2/4] 本地数据加载完成: {len(training_data)}资产")
                except Exception as le:
                    log_step(f"[2/4] 本地数据加载失败: {le}, 降级到API获取...")
                    training_data = None

            if not training_data:
                elite = list(CONFIG['ELITE_UNIVERSE'])[:15]
                log_step(f"[2/4] 从交易所获取{len(elite)}资产数据...")
                try:
                    from server.api import commander
                    training_data = await asyncio.wait_for(commander.fetch_deep_training_history(elite), timeout=300)
                except asyncio.TimeoutError:
                    log_step("[2/4] ML训练数据获取超时(5分钟), 尝试用已有模型继续...")
                    training_data = None
                    errors.append("ml_data_fetch_timeout")
                except ImportError:
                    log_step("[2/4] commander不可用, 跳过API数据获取")
                    training_data = None
                    errors.append("commander_unavailable")
            if training_data:
                total_1h = sum(len(v.get('1h', [])) for v in training_data.values())
                total_4h = sum(len(v.get('4h', [])) for v in training_data.values())
                log_step(f"[2/4] ML训练数据: {len(training_data)}资产, 1h={total_1h}根, 4h={total_4h}根")
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, ml_engine.train, training_data)
                if success:
                    ml_engine.mark_deep_trained()
                    ml_status = ml_engine.get_status()
                    results["ml_retrain"] = {
                        "status": "ok",
                        "accuracy": ml_status.get("accuracy", 0),
                        "f1": ml_status.get("f1", 0),
                        "samples": ml_status.get("samples_trained", 0),
                        "model_version": ml_status.get("model_version", ""),
                        "per_class": ml_status.get("per_class", {}),
                        "assets_used": len(training_data),
                    }
                    log_step(f"[2/4] ML训练完成! 准确率={ml_status['accuracy']}% F1={ml_status['f1']}% 样本={ml_status.get('samples_trained',0)} 版本={ml_status.get('model_version','')}")
                else:
                    results["ml_retrain"] = {"status": "failed", "reason": "数据不足"}
                    log_step("[2/4] ML训练失败: 数据不足")
            else:
                results["ml_retrain"] = {"status": "no_data"}
                log_step("[2/4] ML训练数据获取失败")
        except Exception as e:
            errors.append(f"ml_retrain: {e}")
            results["ml_retrain"] = {"status": "error", "error": str(e)[:100]}
            log_step(f"[2/4] ML训练异常: {str(e)[:80]}")

    log_step("[3/4] 全AI岗前培训启动...")
    ai_training_results = {}

    try:
        from server.titan_deep_evolution import TitanDeepEvolution
        engine = TitanDeepEvolution()
        mega_data = None
        mm_data = None
        try:
            mp = os.path.join(BASE_DIR, "data", "titan_mega_backtest.json")
            if os.path.exists(mp):
                with open(mp) as f:
                    mega_data = json.load(f)
            mmp = os.path.join(BASE_DIR, "data", "titan_mm_metrics.json")
            if os.path.exists(mmp):
                with open(mmp) as f:
                    mm_data = json.load(f)
        except Exception:
            pass
        de_result = engine.run_deep_evolution(
            synapse=synapse, signal_quality=signal_quality,
            agent_memory=agent_memory, feedback_engine=feedback_engine,
            risk_budget=risk_budget, governor=governor,
            return_target=return_target, ai_coordinator=ai_coordinator,
            dispatcher=dispatcher, paper_trader=paper_trader,
            mega_backtest_data=mega_data, mm_metrics_data=mm_data,
            memory_bank=external_data.memory_bank,
        )
        ai_analysis = de_result.get("ai_analysis", {})
        ai_training_results["deep_evolution"] = {
            "status": "ok",
            "trades_processed": de_result.get("trades_processed", 0),
            "synapse_broadcasts": de_result.get("synapse_broadcasts", 0),
            "signal_quality_records": de_result.get("signal_quality_records", 0),
            "insights": de_result.get("insights_generated", 0),
            "memory_records": de_result.get("memory_records", 0),
            "patterns": de_result.get("patterns", {}),
            "ai_deep_analysis": {
                "available": ai_analysis.get("available", False),
                "core_problems": ai_analysis.get("core_problems", [])[:5],
                "winning_patterns": ai_analysis.get("winning_patterns", [])[:3],
                "losing_patterns": ai_analysis.get("losing_patterns", [])[:3],
                "hold_time_insight": ai_analysis.get("hold_time_insight", ""),
                "signal_quality_insight": ai_analysis.get("signal_quality_insight", ""),
                "ml_confidence_insight": ai_analysis.get("ml_confidence_insight", ""),
                "direction_insight": ai_analysis.get("direction_insight", ""),
                "optimization_plan": ai_analysis.get("optimization_plan", {}),
                "risk_warnings": ai_analysis.get("risk_warnings", [])[:3],
                "recommendations_count": ai_analysis.get("recommendations_count", 0),
            },
            "repeat_losers": de_result.get("repeat_losers", [])[:5],
            "losing_streaks": de_result.get("losing_streaks", [])[:3],
        }
        ai_ok = "✓AI深度分析" if ai_analysis.get("available") else ""
        mem_ok = f"+{de_result.get('memory_records',0)}记忆" if de_result.get("memory_records", 0) > 0 else ""
        log_step(f"[3/4] 深度进化完成: {de_result.get('trades_processed',0)}笔交易→Synapse/信号质量/Governor全部更新 {ai_ok} {mem_ok}")

        repeat_losers = de_result.get("repeat_losers", [])
        auto_frozen = []
        for rl in repeat_losers:
            sym = rl.get("symbol", "")
            if not sym:
                continue
            asset_clean = sym.replace("/USDT", "").replace("_USDT", "").upper()
            rl_losses = rl.get("losses", 0)
            rl_wins = rl.get("wins", 0)
            rl_total = rl_losses + rl_wins
            if rl_total < 3 or rl_wins > 0:
                continue
            already = any(
                r.get("type") == "asset_avoid" and r.get("asset") == asset_clean
                for r in synapse.cross_strategy_rules
            )
            if not already:
                synapse.cross_strategy_rules.append({
                    "type": "asset_avoid",
                    "asset": asset_clean,
                    "win_rate": round(rl_wins / max(1, rl_total) * 100, 1),
                    "trades": rl_total,
                    "applies_to": "all",
                    "reason": f"AI深度分析自动冻结: {rl_losses}负{rl_wins}胜, PnL={rl.get('total_pnl',0)}%",
                    "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                auto_frozen.append(asset_clean)
        if auto_frozen:
            synapse.save()
            TitanState.add_log("system", f"🚫 AI自动冻结重复亏损币种: {', '.join(auto_frozen)}")
            log_step(f"[3/4] 自动冻结重复亏损币种: {', '.join(auto_frozen)}")
        ai_training_results["deep_evolution"]["auto_frozen"] = auto_frozen
    except Exception as e:
        errors.append(f"deep_evolution: {e}")
        ai_training_results["deep_evolution"] = {"status": "error", "error": str(e)[:100]}

    try:
        _diagnostic_c = None
        _rra_c = None
        try:
            from server.titan_ai_diagnostic import ai_diagnostic as _diag_c
            _diagnostic_c = _diag_c
        except Exception:
            pass
        try:
            from server.titan_return_rate_agent import return_rate_agent as _rra_c_mod
            _rra_c = _rra_c_mod
        except Exception:
            pass
        ai_coordinator.stats["last_ai_analysis"] = ""
        coord_result = ai_coordinator.coordinate(
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
            diagnostic=_diagnostic_c,
            return_rate_agent=_rra_c,
            agent_memory=agent_memory,
            agi=titan_agi,
        )
        ai_training_results["cto_ai"] = {
            "status": coord_result.get("status", "unknown"),
            "size_multiplier": ai_coordinator.recommendations.get("size_multiplier", 1.0),
            "throttle": ai_coordinator.recommendations.get("throttle_level", "normal"),
            "risk": ai_coordinator.recommendations.get("risk_level", "standard"),
            "reasoning": ai_coordinator.recommendations.get("reasoning", "")[:200],
            "market_outlook": ai_coordinator.recommendations.get("market_outlook", ""),
            "evolution_tips": ai_coordinator.recommendations.get("evolution_tips", []),
            "priority_action": ai_coordinator.recommendations.get("priority_action", ""),
        }
        log_step(f"[3/4] CTO AI协调完成: 仓位因子={ai_coordinator.recommendations.get('size_multiplier',1.0):.3f}")
    except Exception as e:
        errors.append(f"cto_ai: {e}")
        ai_training_results["cto_ai"] = {"status": "error", "error": str(e)[:100]}

    try:
        ref_result = ai_coordinator.reflect()
        if ref_result:
            ai_training_results["cto_reflection"] = {
                "status": "ok",
                "accuracy": ref_result.get("accuracy_score", 0),
                "lessons": ref_result.get("lessons", []),
            }
            log_step(f"[3/4] CTO自我反思: 准确率={ref_result.get('accuracy_score',0)*100:.0f}%, 教训{len(ref_result.get('lessons',[]))}条")
        else:
            ai_training_results["cto_reflection"] = {"status": "insufficient_data"}
    except Exception as e:
        ai_training_results["cto_reflection"] = {"status": "error", "error": str(e)[:100]}

    try:
        from server.titan_return_rate_agent import return_rate_agent
        rra_context = {
            "return_target": return_target.get_status(),
            "paper_portfolio": paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
            "trades_history": paper_trader.trade_history[-20:] if hasattr(paper_trader, 'trade_history') else [],
            "coordinator_recs": ai_coordinator.recommendations,
            "dispatcher_regime": dispatcher.current_regime,
            "risk_budget": risk_budget.get_status(),
            "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
            "unified_decision": unified_decision.get_status(),
            "ml_accuracy": ml_engine.get_status().get("accuracy", 0),
            "synapse": synapse.get_status(),
            "signal_quality": signal_quality.get_status(),
        }
        rra_result = return_rate_agent.think(rra_context, agent_memory, ai_coordinator, return_target)
        TitanState.market_snapshot["return_rate_agent"] = return_rate_agent.get_status()
        diag = rra_result.get("diagnosis", {})
        diag_str = json.dumps(diag, ensure_ascii=False)[:150] if isinstance(diag, dict) else str(diag)[:150]
        ai_training_results["return_rate_agent"] = {
            "status": "ok",
            "severity": diag.get("severity", "unknown") if isinstance(diag, dict) else rra_result.get("severity", "unknown"),
            "diagnosis": diag_str,
            "recommendations": rra_result.get("recommendations", [])[:5],
        }
        sev = diag.get("severity", "unknown") if isinstance(diag, dict) else "unknown"
        log_step(f"[3/4] 收益率诊断完成: 严重度={sev}")
    except Exception as e:
        errors.append(f"return_rate_agent: {e}")
        ai_training_results["return_rate_agent"] = {"status": "error", "error": str(e)[:100]}

    try:
        titan_critic.trade_history = []
        for t in cleaned_trades if 'cleaned_trades' in dir() else paper_trader.trade_history:
            titan_critic.record_trade({
                "sym": t.get("symbol", ""),
                "direction": t.get("direction", "long"),
                "entry": t.get("entry_price", 0),
                "exit": t.get("exit_price", 0),
                "pnl": t.get("pnl_pct", 0),
                "result": t.get("result", "loss"),
                "score": t.get("signal_score", 0),
                "rsi": 50,
                "adx": 20,
                "regime": dispatcher.current_regime,
                "bb_pos": 0.5,
                "vol_ratio": 1.0,
            })
        ai_training_results["critic"] = {
            "status": "ok",
            "trades_reviewed": len(titan_critic.trade_history),
            "ban_rules": len(titan_critic.ban_rules),
            "ban_details": [r.get("reason", "") for r in titan_critic.ban_rules[:5]],
        }
        log_step(f"[3/4] Critic批评系统更新: {len(titan_critic.trade_history)}笔交易复盘, {len(titan_critic.ban_rules)}条禁止规则")
    except Exception as e:
        ai_training_results["critic"] = {"status": "error", "error": str(e)[:100]}

    try:
        risk_budget.rebalance(
            dispatcher_allocation=dispatcher.allocation if hasattr(dispatcher, 'allocation') else None,
            synapse_advice=synapse.cross_strategy_rules if hasattr(synapse, 'cross_strategy_rules') else None,
            coordinator_advice=ai_coordinator.get_rebalance_advice(),
        )
        ai_training_results["risk_budget_rebalance"] = {"status": "ok"}
        log_step("[3/4] 风险预算再平衡完成")
    except Exception as e:
        ai_training_results["risk_budget_rebalance"] = {"status": "error", "error": str(e)[:100]}

    try:
        agent_memory.save()
        synapse.save()
        signal_quality.save()
        governor.save()
        ai_coordinator.save()
        log_step("[3/4] 所有AI子系统状态已持久化保存")
    except Exception as e:
        errors.append(f"save_all: {e}")

    results["ai_training"] = ai_training_results
    log_step(f"[3/4] 全AI岗前培训完成! {sum(1 for v in ai_training_results.values() if v.get('status')=='ok')}/{len(ai_training_results)}个模块成功")

    def _build_ai_deep_analysis_html(ai_results):
        de = ai_results.get("deep_evolution", {})
        ai_deep = de.get("ai_deep_analysis", {})
        if not ai_deep.get("available"):
            return ""

        html = '<div style="margin-bottom:20px; padding:16px; background:linear-gradient(135deg,#faf5ff,#eff6ff); border-radius:8px; border:1px solid #c4b5fd;">'
        html += '<div style="font-size:13px; font-weight:800; color:#5b21b6; margin-bottom:10px;">🧠 AI深度交易分析</div>'

        core_problems = ai_deep.get("core_problems", [])
        if core_problems:
            html += '<div style="margin-bottom:10px;"><div style="font-size:11px; font-weight:700; color:#991b1b; margin-bottom:4px;">核心问题</div>'
            for p in core_problems[:5]:
                html += f'<div style="padding:4px 10px; background:#fef2f2; border-left:3px solid #ef4444; margin-bottom:3px; font-size:11px; border-radius:0 4px 4px 0;">⚠️ {p}</div>'
            html += '</div>'

        winning = ai_deep.get("winning_patterns", [])
        losing = ai_deep.get("losing_patterns", [])
        if winning or losing:
            html += '<div style="margin-bottom:10px; display:flex; gap:10px;">'
            if winning:
                html += '<div style="flex:1;"><div style="font-size:11px; font-weight:700; color:#065f46; margin-bottom:4px;">盈利模式</div>'
                for w in winning[:3]:
                    html += f'<div style="padding:3px 10px; background:#ecfdf5; font-size:10px; color:#065f46; border-radius:4px; margin-bottom:2px;">✅ {w}</div>'
                html += '</div>'
            if losing:
                html += '<div style="flex:1;"><div style="font-size:11px; font-weight:700; color:#991b1b; margin-bottom:4px;">亏损模式</div>'
                for l in losing[:3]:
                    html += f'<div style="padding:3px 10px; background:#fef2f2; font-size:10px; color:#991b1b; border-radius:4px; margin-bottom:2px;">❌ {l}</div>'
                html += '</div>'
            html += '</div>'

        insights = []
        for key, label in [("hold_time_insight","持仓时间"), ("signal_quality_insight","信号质量"), ("ml_confidence_insight","ML置信度"), ("direction_insight","方向偏好")]:
            val = ai_deep.get(key, "")
            if val:
                insights.append((label, val))
        if insights:
            html += '<div style="margin-bottom:10px;"><div style="font-size:11px; font-weight:700; color:#1e3a5f; margin-bottom:4px;">维度洞察</div>'
            for name, text in insights:
                html += f'<div style="padding:4px 10px; background:#eff6ff; border-left:3px solid #3b82f6; margin-bottom:3px; font-size:11px; border-radius:0 4px 4px 0;"><b>{name}:</b> {text[:100]}</div>'
            html += '</div>'

        opt_plan = ai_deep.get("optimization_plan", {})
        if opt_plan:
            html += '<div style="margin-bottom:8px;"><div style="font-size:11px; font-weight:700; color:#1e293b; margin-bottom:4px;">优化路线图</div>'
            for period, label in [("short_term","短期(1周)"), ("medium_term","中期(1月)"), ("long_term","长期")]:
                items = opt_plan.get(period, [])
                if items:
                    html += f'<div style="font-size:10px; font-weight:600; color:#475569; margin:4px 0 2px;">{label}:</div>'
                    for item in items[:3]:
                        html += f'<div style="padding:3px 10px; font-size:10px; color:#334155;">→ {item}</div>'
            html += '</div>'

        warnings = ai_deep.get("risk_warnings", [])
        if warnings:
            html += '<div><div style="font-size:11px; font-weight:700; color:#dc2626; margin-bottom:4px;">风险警告</div>'
            for w in warnings[:3]:
                html += f'<div style="padding:4px 10px; background:#fef2f2; font-size:11px; color:#dc2626; border-radius:4px; margin-bottom:2px;">🚨 {w}</div>'
            html += '</div>'

        repeat_losers = de.get("repeat_losers", [])
        if repeat_losers:
            html += '<div style="margin-top:8px;"><div style="font-size:11px; font-weight:700; color:#92400e; margin-bottom:4px;">重复亏损币种</div>'
            for rl in repeat_losers[:5]:
                html += f'<div style="padding:3px 10px; font-size:10px; color:#92400e;">⛔ {rl["symbol"]}: {rl["losses"]}负{rl["wins"]}胜, PnL={rl["total_pnl"]}%</div>'
            html += '</div>'

        html += '</div>'
        return html

    log_step("[4/4] 生成CTO简报并发送邮件...")
    try:
        pt_summary = paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
        ml_st = ml_engine.get_status()
        coord_recs = ai_coordinator.recommendations
        trade_stats = {
            "total": len(cleaned_trades) if 'cleaned_trades' in dir() else 0,
            "wins": sum(1 for t in (cleaned_trades if 'cleaned_trades' in dir() else []) if t.get("result") == "win"),
            "losses": sum(1 for t in (cleaned_trades if 'cleaned_trades' in dir() else []) if t.get("result") != "win"),
        }
        trade_stats["win_rate"] = round(trade_stats["wins"] / max(1, trade_stats["total"]) * 100, 1)
        trade_stats["avg_pnl"] = round(sum(t.get("pnl_pct", 0) for t in (cleaned_trades if 'cleaned_trades' in dir() else [])) / max(1, trade_stats["total"]), 2)

        strategy_breakdown = {}
        for t in (cleaned_trades if 'cleaned_trades' in dir() else []):
            st = t.get("strategy_type", "unknown")
            if st not in strategy_breakdown:
                strategy_breakdown[st] = {"count": 0, "wins": 0, "pnl": 0}
            strategy_breakdown[st]["count"] += 1
            if t.get("result") == "win":
                strategy_breakdown[st]["wins"] += 1
            strategy_breakdown[st]["pnl"] += t.get("pnl_pct", 0)

        steps_html = ""
        step_items = [
            ("数据清洗", results.get("data_cleaning", {})),
            ("ML重训练", results.get("ml_retrain", {})),
        ]
        for name, data in step_items:
            status = data.get("status", "ok")
            color = "#10b981" if status == "ok" else "#ef4444"
            icon = "✅" if status == "ok" else "❌"
            detail = ""
            if name == "数据清洗":
                detail = f"原始{data.get('original_trades',0)}→清洗后{data.get('cleaned_trades',0)}笔"
            elif name == "ML重训练":
                detail = f"准确率{data.get('accuracy',0)}% F1={data.get('f1',0)}% 版本{data.get('model_version','')}"
            steps_html += f'<div style="padding:8px 12px; border-left:3px solid {color}; background:#f8fafc; margin-bottom:4px; font-size:12px; border-radius:0 6px 6px 0;">{icon} <b>{name}</b>: {detail}</div>'

        ai_items = ai_training_results
        ai_steps_html = ""
        ai_name_map = {
            "deep_evolution": "深度进化",
            "cto_ai": "CTO AI协调",
            "cto_reflection": "CTO自我反思",
            "return_rate_agent": "收益率诊断",
            "critic": "Critic批评系统",
            "risk_budget_rebalance": "风险预算再平衡",
        }
        for key, data in ai_items.items():
            name = ai_name_map.get(key, key)
            status = data.get("status", "unknown")
            color = "#10b981" if status == "ok" else ("#f59e0b" if status in ("cooldown","insufficient_data","fallback") else "#ef4444")
            icon = "✅" if status == "ok" else ("⏸" if status in ("cooldown","insufficient_data","fallback") else "❌")
            detail = ""
            if key == "deep_evolution":
                mem_info = f", 记忆+{data.get('memory_records',0)}" if data.get('memory_records',0) > 0 else ""
                ai_info = ", AI深度分析✓" if data.get('ai_deep_analysis',{}).get('available') else ""
                detail = f"交易{data.get('trades_processed',0)}笔, Synapse广播{data.get('synapse_broadcasts',0)}, 洞察{data.get('insights',0)}条{mem_info}{ai_info}"
            elif key == "cto_ai":
                detail = f"仓位×{data.get('size_multiplier',1.0):.2f}, 油门={data.get('throttle','')}, 展望: {data.get('market_outlook','')[:40]}"
            elif key == "cto_reflection":
                detail = f"准确率{data.get('accuracy',0)*100:.0f}%, 教训{len(data.get('lessons',[]))}条"
            elif key == "return_rate_agent":
                detail = f"严重度={data.get('severity','')}, 诊断: {data.get('diagnosis','')[:60]}"
            elif key == "critic":
                detail = f"复盘{data.get('trades_reviewed',0)}笔, 禁止规则{data.get('ban_rules',0)}条"
            elif key == "risk_budget_rebalance":
                detail = "资金重新分配完成"
            ai_steps_html += f'<div style="padding:8px 12px; border-left:3px solid {color}; background:#f8fafc; margin-bottom:4px; font-size:12px; border-radius:0 6px 6px 0;">{icon} <b>{name}</b>: {detail}</div>'

        strategy_rows = ""
        for st, data in strategy_breakdown.items():
            wr = round(data["wins"] / max(1, data["count"]) * 100, 1)
            avg = round(data["pnl"] / max(1, data["count"]), 2)
            strategy_rows += f'<tr style="font-size:11px; border-bottom:1px solid #f1f5f9;"><td style="padding:6px 10px; font-weight:700;">{st}</td><td style="text-align:center;">{data["count"]}</td><td style="text-align:center;">{data["wins"]}</td><td style="text-align:center; color:{"#10b981" if wr>=40 else "#ef4444"};">{wr}%</td><td style="text-align:center; color:{"#10b981" if avg>=0 else "#ef4444"};">{avg:+.2f}%</td></tr>'

        tips_html = ""
        evolution_tips = coord_recs.get("evolution_tips", [])
        for tip in evolution_tips[:5]:
            tips_html += f'<div style="padding:6px 10px; background:#eff6ff; border-left:3px solid #3b82f6; margin-bottom:4px; font-size:11px; border-radius:0 6px 6px 0;">💡 {tip}</div>'

        elapsed = round(_time.time() - start, 1)

        email_body = f"""
        <html>
        <body style="margin:0; padding:20px; background-color:#f1f5f9; font-family:sans-serif;">
            <div style="max-width:780px; margin:auto; background:#fff; border-radius:12px; overflow:hidden; border:2px solid #6366f1; box-shadow:0 4px 20px rgba(0,0,0,0.1);">
                <div style="background:linear-gradient(135deg,#1e3a8a,#7c3aed,#1e293b); padding:28px; color:#fff;">
                    <div style="font-size:10px; font-weight:800; letter-spacing:2px; color:#fbbf24; margin-bottom:6px;">神盾计划 | CTO 全面简报 & AI岗前培训报告</div>
                    <h1 style="margin:0; font-size:22px; font-weight:900;">系统更新逻辑 & AI全员复盘报告</h1>
                    <p style="margin:6px 0 0; font-size:11px; color:#cbd5e1;">{now_str} | 全自动生成 | 耗时{elapsed}秒</p>
                </div>
                <div style="padding:25px;">
                    <div style="margin-bottom:20px;">
                        <div style="font-size:13px; font-weight:800; color:#1e293b; margin-bottom:10px;">📊 投资组合状态</div>
                        <div style="display:flex; gap:10px; flex-wrap:wrap;">
                            <div style="flex:1; min-width:100px; background:#f0fdf4; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">总资产</div>
                                <div style="font-size:18px; font-weight:900; color:#10b981;">${pt_summary.get('equity', 100000):.0f}</div>
                            </div>
                            <div style="flex:1; min-width:100px; background:#fef2f2; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">收益率</div>
                                <div style="font-size:18px; font-weight:900; color:{'#10b981' if pt_summary.get('return_pct',0)>=0 else '#ef4444'};">{pt_summary.get('return_pct', 0):+.2f}%</div>
                            </div>
                            <div style="flex:1; min-width:100px; background:#eff6ff; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">胜率</div>
                                <div style="font-size:18px; font-weight:900; color:#3b82f6;">{trade_stats['win_rate']}%</div>
                            </div>
                            <div style="flex:1; min-width:100px; background:#faf5ff; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">持仓数</div>
                                <div style="font-size:18px; font-weight:900; color:#8b5cf6;">{len(paper_trader.positions)}</div>
                            </div>
                            <div style="flex:1; min-width:100px; background:#fff7ed; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">回撤</div>
                                <div style="font-size:18px; font-weight:900; color:#f59e0b;">{pt_summary.get('max_drawdown_pct', 0):.2f}%</div>
                            </div>
                        </div>
                    </div>

                    <div style="margin-bottom:20px;">
                        <div style="font-size:13px; font-weight:800; color:#1e293b; margin-bottom:8px;">🧹 Step 1: 数据清洗</div>
                        {steps_html}
                    </div>

                    <div style="margin-bottom:20px;">
                        <div style="font-size:13px; font-weight:800; color:#1e293b; margin-bottom:8px;">🎓 Step 2: AI全员岗前培训</div>
                        {ai_steps_html}
                    </div>

                    <div style="margin-bottom:20px;">
                        <div style="font-size:13px; font-weight:800; color:#1e293b; margin-bottom:8px;">📈 策略表现分解</div>
                        <table style="width:100%; border-collapse:collapse;">
                            <thead><tr style="background:#1e293b; color:#fff; font-size:10px;">
                                <th style="padding:8px 10px; text-align:left;">策略</th><th>总交易</th><th>盈利</th><th>胜率</th><th>均PnL</th>
                            </tr></thead>
                            <tbody>{strategy_rows if strategy_rows else '<tr><td colspan="5" style="padding:20px; text-align:center; color:#94a3b8;">暂无策略数据</td></tr>'}</tbody>
                        </table>
                    </div>

                    {_build_ai_deep_analysis_html(ai_training_results)}

                    <div style="margin-bottom:20px;">
                        <div style="font-size:13px; font-weight:800; color:#1e293b; margin-bottom:8px;">🤖 ML模型状态</div>
                        <div style="display:flex; gap:10px;">
                            <div style="flex:1; background:#f0fdf4; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">准确率</div>
                                <div style="font-size:18px; font-weight:900; color:#10b981;">{ml_st.get('accuracy',0)}%</div>
                            </div>
                            <div style="flex:1; background:#eff6ff; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">F1</div>
                                <div style="font-size:18px; font-weight:900; color:#3b82f6;">{ml_st.get('f1',0)}%</div>
                            </div>
                            <div style="flex:1; background:#faf5ff; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">版本</div>
                                <div style="font-size:14px; font-weight:900; color:#8b5cf6;">{ml_st.get('model_version','N/A')}</div>
                            </div>
                            <div style="flex:1; background:#fff7ed; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:9px; color:#94a3b8;">样本</div>
                                <div style="font-size:14px; font-weight:900; color:#f59e0b;">{ml_st.get('samples_trained',0)}</div>
                            </div>
                        </div>
                    </div>

                    <div style="margin-bottom:20px; padding:16px; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
                        <div style="font-size:13px; font-weight:800; color:#1e293b; margin-bottom:8px;">🎯 CTO AI决策摘要</div>
                        <div style="display:flex; gap:8px; margin-bottom:10px;">
                            <div style="flex:1; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                                <div style="font-size:9px; color:#94a3b8;">仓位乘数</div>
                                <div style="font-size:18px; font-weight:900; color:#6366f1;">{coord_recs.get('size_multiplier', 1.0):.3f}</div>
                            </div>
                            <div style="flex:1; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                                <div style="font-size:9px; color:#94a3b8;">油门级别</div>
                                <div style="font-size:14px; font-weight:900; color:#f59e0b;">{coord_recs.get('throttle_level', 'normal')}</div>
                            </div>
                            <div style="flex:1; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                                <div style="font-size:9px; color:#94a3b8;">风险级别</div>
                                <div style="font-size:14px; font-weight:900; color:#dc2626;">{coord_recs.get('risk_level', 'standard')}</div>
                            </div>
                            <div style="flex:1; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                                <div style="font-size:9px; color:#94a3b8;">市场偏向</div>
                                <div style="font-size:14px; font-weight:900; color:#1e293b;">{coord_recs.get('regime_bias', 'neutral')}</div>
                            </div>
                        </div>
                        <div style="font-size:12px; color:#475569; line-height:1.6;">
                            <b>推理:</b> {coord_recs.get('reasoning', '无')[:300]}<br/>
                            <b>市场展望:</b> {coord_recs.get('market_outlook', '无')}<br/>
                            <b>优先行动:</b> {coord_recs.get('priority_action', '无')}
                        </div>
                    </div>

                    {'<div style="margin-bottom:20px;"><div style="font-size:13px; font-weight:800; color:#1e293b; margin-bottom:8px;">💡 CTO进化建议</div>' + tips_html + '</div>' if tips_html else ''}

                    <div style="margin-top:16px; padding:12px; background:#ecfdf5; border-radius:8px; border:1px solid #6ee7b7;">
                        <div style="font-size:12px; color:#065f46; font-weight:700;">📋 简报总结: {sum(1 for v in ai_training_results.values() if v.get('status')=='ok')}/{len(ai_training_results)}个AI模块训练成功, {len(errors)}个错误, 耗时{elapsed}秒</div>
                    </div>
                </div>
                <div style="background:#1e293b; padding:14px; text-align:center; font-size:10px; color:#64748b;">
                    神盾计划：不死量化 | CTO全面简报 | {now_str} | 全自动AI岗前培训
                </div>
            </div>
        </body>
        </html>
        """

        sender = os.getenv('SENDER_EMAIL')
        password = os.getenv('SENDER_PASSWORD')
        receivers = TitanMailer.get_receivers()
        email_sent = False
        if sender and password and receivers:
            try:
                from email.mime.text import MIMEText
                from email.header import Header
                import smtplib
                TitanMailer._last_emergency_email_time = 0
                msg = MIMEText(email_body, 'html', 'utf-8')
                msg['Subject'] = Header(f"[神盾CTO简报] 系统更新&AI全员复盘 | 胜率{trade_stats['win_rate']}% 准确率{ml_st.get('accuracy',0)}% | {now_str}", 'utf-8')
                msg['From'] = sender
                msg['To'] = ', '.join(receivers)
                with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                    s.login(sender, password)
                    s.sendmail(sender, receivers, msg.as_string())
                email_sent = True
                log_step("[4/4] CTO简报邮件已成功发送!")
            except Exception as mail_err:
                errors.append(f"email: {mail_err}")
                log_step(f"[4/4] 邮件发送失败: {mail_err}")
        else:
            log_step("[4/4] 邮件配置不完整, 跳过发送")

        results["cto_report"] = {
            "email_sent": email_sent,
            "trade_stats": trade_stats,
            "strategy_breakdown": strategy_breakdown,
            "coordinator_recommendations": coord_recs,
        }

    except Exception as e:
        errors.append(f"cto_report: {e}")
        log_step(f"[4/4] CTO简报生成异常: {e}")

    elapsed_final = round(_time.time() - start, 1)
    ok_count = sum(1 for v in ai_training_results.values() if v.get("status") == "ok")
    summary = f"CTO全面简报完成: {ok_count}/{len(ai_training_results)}个AI模块训练成功, {len(errors)}个错误, 耗时{elapsed_final}秒"
    log_step(f"=== {summary} ===")
    _cto_briefing_state["summary"] = summary

@router.post("/api/cto-full-briefing")
async def cto_full_briefing(retrain_ml: bool = False):
    global _cto_briefing_state
    if _cto_briefing_state.get("status") == "running":
        return {"status": "already_running", "log": list(_cto_briefing_state.get("log", []))[-10:]}
    _cto_briefing_state["_retrain_ml"] = retrain_ml
    asyncio.create_task(_run_cto_briefing())
    mode = "含ML重训练(需5-10分钟)" if retrain_ml else "快速模式(跳过ML训练)"
    return {"status": "started", "message": f"CTO全面简报已启动 [{mode}]，请通过 /api/cto-briefing-status 查看进度"}


@router.get("/api/department-briefings")
async def get_department_briefings():
    return ai_coordinator.get_department_briefings()

@router.post("/api/department-briefings/generate")
async def generate_department_briefings():
    result = ai_coordinator.generate_department_briefings()
    return result


@router.get("/api/cto-report")
async def get_cto_report():
    return ai_coordinator.get_cto_report()


@router.post("/api/cto-report/generate")
async def generate_cto_report():
    result = ai_coordinator.generate_cto_report()
    return result


@router.get("/api/strategic-directives")
async def get_strategic_directives():
    try:
        from server.titan_db import db_connection
        directives_list = []
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT id, directive_type, content, priority, source, executed, executed_at, created_at
                FROM strategic_directives ORDER BY created_at DESC LIMIT 50
            """)
            for r in cur.fetchall():
                directives_list.append({
                    "id": r["id"],
                    "type": r["directive_type"],
                    "content": r["content"],
                    "priority": r["priority"],
                    "source": r["source"],
                    "executed": r["executed"],
                    "executed_at": str(r["executed_at"]) if r["executed_at"] else None,
                    "created_at": str(r["created_at"]) if r["created_at"] else None,
                })
        live = ai_coordinator.strategic_directives if ai_coordinator else {}
        return {"status": "ok", "directives": directives_list, "live_config": live, "total": len(directives_list)}
    except Exception as e:
        return {"status": "error", "error": str(e), "directives": [], "live_config": ai_coordinator.strategic_directives if ai_coordinator else {}}


@router.get("/api/cto-decisions")
async def get_cto_decisions():
    try:
        from server.titan_db import db_connection
        decisions = []
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT id, decision_type, target, old_value, new_value, reason,
                       btc_price_at_decision, fng_at_decision, btc_macro_trend,
                       current_drawdown_pct, verified_at, decision_correct,
                       decision_quality_score, created_at
                FROM cto_decisions ORDER BY created_at DESC LIMIT 50
            """)
            for r in cur.fetchall():
                decisions.append({
                    "id": r["id"],
                    "type": r["decision_type"],
                    "target": r["target"],
                    "old_value": r["old_value"],
                    "new_value": r["new_value"],
                    "reason": r["reason"],
                    "btc_price": r["btc_price_at_decision"],
                    "fng": r["fng_at_decision"],
                    "macro_trend": r["btc_macro_trend"],
                    "drawdown_pct": float(r["current_drawdown_pct"]) if r["current_drawdown_pct"] else None,
                    "verified_at": str(r["verified_at"]) if r["verified_at"] else None,
                    "correct": r["decision_correct"],
                    "quality_score": float(r["decision_quality_score"]) if r["decision_quality_score"] else None,
                    "created_at": str(r["created_at"]) if r["created_at"] else None,
                })
        return {"status": "ok", "decisions": decisions, "total": len(decisions)}
    except Exception as e:
        return {"status": "error", "error": str(e), "decisions": []}


@router.get("/api/anomaly-patrol")
async def get_anomaly_patrol():
    try:
        from server.titan_state import TitanState
        anomalies = []
        all_logs = list(TitanState.market_snapshot.get("logs", []))
        for log in all_logs:
            msg = str(log.get("msg", ""))
            log_type = log.get("type", "")
            if log_type == "gate" or any(k in msg for k in ["异常", "拒绝", "逆势", "熔断", "告警", "禁入"]):
                anomalies.append(log)

        from server.titan_db import db_connection
        recent_rejections = []
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT symbol, direction, signal_score, rejection_reason, created_at
                FROM rejected_signals
                WHERE created_at > NOW() - INTERVAL '6 hours'
                ORDER BY created_at DESC LIMIT 30
            """)
            for r in cur.fetchall():
                recent_rejections.append({
                    "symbol": r["symbol"],
                    "direction": r["direction"],
                    "score": r["signal_score"],
                    "reason": r["rejection_reason"],
                    "time": str(r["created_at"]) if r["created_at"] else None,
                })
        return {
            "status": "ok",
            "anomalies": anomalies,
            "recent_rejections": recent_rejections,
            "rejection_count_6h": len(recent_rejections),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "anomalies": [], "recent_rejections": []}


@router.get("/api/ceo-report")
async def get_ceo_report():
    try:
        now = datetime.now()
        from pytz import timezone as pytz_tz
        try:
            cst = pytz_tz("Asia/Shanghai")
            now_cst = datetime.now(cst)
        except Exception:
            now_cst = now

        paper_data = paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit) if paper_trader else {}
        all_trades = paper_trader.get_recent_trades(limit=9999) if paper_trader else []
        closed = [t for t in all_trades if t.get("close_time") or t.get("result")]
        wins = [t for t in closed if t.get("result") == "win" or (t.get("pnl_value", t.get("pnl_usd", 0)) or 0) > 0]
        losses = [t for t in closed if t.get("result") == "loss" or (t.get("pnl_value", t.get("pnl_usd", 0)) or 0) < 0]
        open_pos = paper_trader.get_positions_display() if paper_trader else []

        total_pnl = sum(t.get("pnl_value", t.get("pnl_usd", 0)) or 0 for t in closed)
        avg_win_pct = sum(t.get("pnl_pct", 0) for t in wins) / len(wins) if wins else 0
        avg_loss_pct = sum(t.get("pnl_pct", 0) for t in losses) / len(losses) if losses else 0
        best_trade = max(closed, key=lambda t: t.get("pnl_pct", 0)) if closed else None
        worst_trade = min(closed, key=lambda t: t.get("pnl_pct", 0)) if closed else None

        ml = {}
        if ml_engine:
            try:
                ml = ml_engine.get_status()
            except Exception:
                ml = {}

        const_status = constitution.get_status() if constitution else {}
        risk_b = risk_budget.get_status() if risk_budget else {}
        sig_q = signal_quality.get_status() if signal_quality else {}
        try:
            disp = "unknown"
            if dispatcher and hasattr(dispatcher, 'current_regime') and dispatcher.current_regime:
                disp = dispatcher.current_regime
            if disp == "unknown":
                snap_regime = TitanState.market_snapshot.get("regime", "")
                if snap_regime:
                    disp = snap_regime
        except Exception:
            disp = "unknown"

        ap = autopilot.get_status()

        strat_perf = []
        try:
            strat_map = {}
            for t in closed:
                st = t.get("strategy_type", t.get("strategy", "unknown"))
                if st not in strat_map:
                    strat_map[st] = {"wins": 0, "losses": 0, "pnl": 0, "worst_assets": {}}
                pv = t.get("pnl_value", t.get("pnl_usd", 0)) or 0
                if t.get("result") == "win" or pv > 0:
                    strat_map[st]["wins"] += 1
                else:
                    strat_map[st]["losses"] += 1
                strat_map[st]["pnl"] += pv
                if pv < 0:
                    sym = t.get("symbol", "?")
                    strat_map[st]["worst_assets"][sym] = strat_map[st]["worst_assets"].get(sym, 0) + abs(pv)
            for sk, sd in strat_map.items():
                total = sd["wins"] + sd["losses"]
                strat_perf.append({
                    "strategy": sk,
                    "wins": sd["wins"],
                    "losses": sd["losses"],
                    "total_trades": total,
                    "win_rate": round(sd["wins"] / total * 100, 1) if total > 0 else 0,
                    "total_pnl": round(sd["pnl"], 2),
                    "worst_assets": dict(sorted(sd["worst_assets"].items(), key=lambda x: -x[1])[:5]),
                })
            try:
                gh = grid_engine.grid_history if hasattr(grid_engine, 'grid_history') else []
                grid_wins = sum(1 for g in gh if g.get("pnl", 0) > 0)
                grid_losses = len(gh) - grid_wins
                grid_pnl_total = sum(g.get("pnl", 0) for g in gh)
                grid_unrealized = grid_engine.get_unrealized_pnl()
                grid_total = len(gh)
                if grid_total > 0 or grid_unrealized != 0:
                    strat_perf.append({
                        "strategy": "grid",
                        "wins": grid_wins,
                        "losses": grid_losses,
                        "total_trades": grid_total,
                        "win_rate": round(grid_wins / grid_total * 100, 1) if grid_total > 0 else 0,
                        "total_pnl": round(grid_pnl_total + grid_unrealized, 2),
                        "worst_assets": {},
                    })
            except Exception:
                pass
        except Exception:
            pass

        coord_data = {}
        try:
            coord = TitanState.market_snapshot.get("coordinator", {})
            coord_data = {
                "size_multiplier": coord.get("size_multiplier", 1.0),
                "throttle_level": coord.get("throttle_level", 0),
                "risk_level": coord.get("risk_level", "medium"),
                "recommendations": coord.get("recommendations", {}),
            }
        except Exception:
            pass

        adaptive_data = {}
        try:
            adaptive_data = TitanState.market_snapshot.get("adaptive_weights", {})
        except Exception:
            pass

        equity = paper_data.get("equity", 100000)
        initial = paper_data.get("initial_capital", 100000)
        return_pct = ((equity - initial) / initial * 100) if initial > 0 else 0
        drawdown = paper_data.get("max_drawdown_pct", 0)

        try:
            if all_trades:
                trade_times = [t.get("open_time", "") for t in all_trades if t.get("open_time")]
                if trade_times:
                    earliest = min(trade_times)
                    days_running = (now - datetime.fromisoformat(earliest.replace("Z","").replace("+08:00",""))).days
                else:
                    days_running = 0
            else:
                days_running = 0
        except Exception:
            days_running = 0
        ann_return = return_pct * (365 / max(days_running, 1)) if days_running > 0 else 0

        btc_pulse = TitanState.market_snapshot.get("btc_pulse", {})
        fng_detail = btc_pulse.get("fng_detail", {})
        fng_value = fng_detail.get("value", btc_pulse.get("fng", 50)) if fng_detail else btc_pulse.get("fng", 50)
        fng_label = fng_detail.get("label", "") if fng_detail else ""
        btc = btc_pulse.get("price", 0)

        trend_data = next((s for s in strat_perf if s.get("strategy") == "trend"), {})
        range_data = next((s for s in strat_perf if s.get("strategy") == "range"), {})
        grid_data = next((s for s in strat_perf if s.get("strategy") == "grid"), {})

        risk_assessment = "低"
        if drawdown > 5:
            risk_assessment = "高"
        elif drawdown > 3:
            risk_assessment = "中"

        health_grade = "A"
        health_score = 100
        issues = []

        win_rate = len(wins) / len(closed) * 100 if closed else 0
        if win_rate < 40:
            health_score -= 20
            issues.append(f"胜率偏低 ({win_rate:.1f}%)")
        if return_pct < 0:
            health_score -= 15
            issues.append(f"收益为负 ({return_pct:.2f}%)")
        if drawdown > 5:
            health_score -= 20
            issues.append(f"回撤超标 ({drawdown:.2f}%)")
        ml_acc = ml.get("accuracy", 0)
        if ml_acc < 60:
            health_score -= 10
            issues.append(f"ML准确率不足 ({ml_acc:.1f}%)")
        trend_wr = trend_data.get("win_rate", 0)
        if trend_wr < 30 and trend_data.get("total_trades", 0) > 50:
            health_score -= 10
            issues.append(f"趋势策略胜率仅 {trend_wr:.1f}%")
        if sig_q.get("avg_quality", 1) < 0.6:
            health_score -= 5
            issues.append(f"信号质量偏低 ({sig_q.get('avg_quality',0):.2f})")

        if health_score >= 80:
            health_grade = "A"
        elif health_score >= 60:
            health_grade = "B"
        elif health_score >= 40:
            health_grade = "C"
        elif health_score >= 20:
            health_grade = "D"
        else:
            health_grade = "F"

        strategic_recommendations = []
        if win_rate < 40:
            strategic_recommendations.append({
                "priority": "高",
                "category": "交易策略",
                "action": "收紧信号过滤，提高最低评分阈值至75+",
                "expected_impact": "减少低质量交易，提升胜率",
                "auto_adjustable": True,
            })
        if trend_wr < 30 and trend_data.get("total_trades", 0) > 100:
            strategic_recommendations.append({
                "priority": "高",
                "category": "策略分配",
                "action": "降低趋势策略权重，增加区间/网格策略分配",
                "expected_impact": "减少趋势策略亏损敞口",
                "auto_adjustable": True,
            })
        if ml_acc < 65:
            strategic_recommendations.append({
                "priority": "中",
                "category": "ML模型",
                "action": "触发云端深度训练，扩充训练样本",
                "expected_impact": "提升ML预测准确率至65%+",
                "auto_adjustable": True,
            })
        if return_pct < 0:
            strategic_recommendations.append({
                "priority": "中",
                "category": "资金管理",
                "action": "降低单笔风险敞口，缩减仓位规模",
                "expected_impact": "控制损失速度，保护本金",
                "auto_adjustable": True,
            })
        strategic_recommendations.append({
            "priority": "低",
            "category": "持续优化",
            "action": "维持当前CTO自动调整机制，收集更多交易数据",
            "expected_impact": "数据积累后可进行更准确的策略优化",
            "auto_adjustable": True,
        })

        report = {
            "report_time": now_cst.strftime("%Y-%m-%d %H:%M:%S CST"),
            "report_title": "CEO战略评估报告",
            "executive_summary": {
                "health_grade": health_grade,
                "health_score": max(0, health_score),
                "issues_count": len(issues),
                "key_issues": issues,
                "verdict": "系统运行正常，CTO自动调整机制已激活。" if health_score >= 60 else "系统需要关注，建议审查以下问题。" if health_score >= 40 else "系统表现不佳，建议CEO介入决策。",
            },
            "market_environment": {
                "btc_price": btc,
                "fear_greed_index": fng_value,
                "fear_greed_label": fng_label,
                "regime": disp if isinstance(disp, str) else disp.get("regime", "unknown") if isinstance(disp, dict) else "unknown",
                "market_assessment": "极度恐惧市场，波动性高，趋势策略面临挑战" if fng_value < 20 else "市场情绪中性，适合多策略运行" if fng_value < 60 else "市场乐观，趋势策略有利",
            },
            "portfolio_performance": {
                "total_equity": round(equity, 2),
                "initial_capital": initial,
                "total_return_pct": round(return_pct, 4),
                "total_pnl_usd": round(total_pnl, 2),
                "annualized_return_pct": round(ann_return, 2),
                "max_drawdown_pct": round(drawdown, 4),
                "risk_assessment": risk_assessment,
                "total_trades": len(closed),
                "win_rate": round(win_rate, 1),
                "avg_win_pct": round(avg_win_pct, 2),
                "avg_loss_pct": round(avg_loss_pct, 2),
                "best_trade": {"symbol": best_trade.get("symbol",""), "pnl_pct": best_trade.get("pnl_pct",0)} if best_trade else None,
                "worst_trade": {"symbol": worst_trade.get("symbol",""), "pnl_pct": worst_trade.get("pnl_pct",0)} if worst_trade else None,
                "active_positions": len(open_pos),
                "days_running": days_running,
            },
            "strategy_analysis": {
                "trend_following": {
                    "total_trades": trend_data.get("total_trades", 0),
                    "win_rate": trend_data.get("win_rate", 0),
                    "pnl": trend_data.get("total_pnl", 0),
                    "worst_assets": list(trend_data.get("worst_assets", {}).keys())[:5],
                    "verdict": "亏损集中，需降低权重" if trend_data.get("total_pnl", 0) < -50 else "表现可接受" if trend_data.get("total_trades", 0) > 0 else "待激活",
                },
                "range_harvester": {
                    "total_trades": range_data.get("total_trades", 0),
                    "win_rate": range_data.get("win_rate", 0),
                    "pnl": range_data.get("total_pnl", 0),
                    "verdict": "亏损中" if range_data.get("total_pnl", 0) < 0 and range_data.get("total_trades", 0) > 0 else "盈利中" if range_data.get("total_pnl", 0) > 0 else "待激活" if range_data.get("total_trades", 0) == 0 else "运行中",
                },
                "grid_trading": {
                    "total_trades": grid_data.get("total_trades", 0),
                    "win_rate": grid_data.get("win_rate", 0),
                    "pnl": grid_data.get("total_pnl", 0),
                    "verdict": "盈利中" if grid_data.get("total_pnl", 0) > 0 else "亏损中" if grid_data.get("total_pnl", 0) < 0 and grid_data.get("total_trades", 0) > 0 else "持续运行" if grid_data.get("total_trades", 0) > 0 else "待激活",
                },
            },
            "ml_intelligence": {
                "model_version": ml.get("model_version", "N/A"),
                "accuracy": ml.get("accuracy", 0),
                "f1_score": ml.get("f1", 0),
                "cv_accuracy": ml.get("cv_accuracy", 0),
                "training_samples": ml.get("samples", 0),
                "train_count": ml.get("train_count", 0),
                "deep_trained": ml.get("deep_trained", False),
                "per_class": ml.get("per_class", {}),
            },
            "risk_control": {
                "constitution_status": "正常" if const_status.get("can_open_new") else "限制中",
                "permanent_breaker": const_status.get("permanent_breaker", False),
                "daily_breaker": const_status.get("daily_breaker", False),
                "blocked_trades_total": ap.get("blocked_trades_count", 0),
            },
            "cto_autonomy": {
                "adaptive_weights": {
                    "ml_weight": adaptive_data.get("w_ml", 0),
                    "rule_weight": adaptive_data.get("w_rule", 0),
                },
                "coordinator": coord_data,
                "autopilot_cycles": ap.get("cycle_count", 0),
                "uptime_hours": ap.get("uptime_hours", 0),
                "schedule": ap.get("schedule", {}),
            },
            "strategic_recommendations": strategic_recommendations,
            "ceo_decision_needed": len([d for d in ap.get("ceo_decisions", []) if not d.get("resolved")]) > 0,
            "pending_decisions": [d for d in ap.get("ceo_decisions", []) if not d.get("resolved")],
        }

        return report

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()[:500]}


@router.post("/api/self-inspection/run")
async def run_self_inspection(inspector: str = None):
    try:
        if inspector:
            result = self_inspector.run_single(inspector, use_ai_summary=True)
        else:
            result = self_inspector.run_all(use_ai_summary=True)
        return result
    except Exception as e:
        return {"error": str(e)}

@router.get("/api/self-inspection/report")
async def get_inspection_report():
    latest = self_inspector.get_latest_report()
    return latest or {"message": "尚未执行自检", "findings": []}

@router.get("/api/self-inspection/history")
async def get_inspection_history(limit: int = 10):
    return {"reports": self_inspector.get_report_history(limit)}

@router.get("/api/self-inspection/inspectors")
async def get_inspectors():
    return {"inspectors": self_inspector.get_available_inspectors()}
