import os
import json
import time
import asyncio
import logging

import numpy as np
import pandas as pd

from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.titan_state import CONFIG, TitanState, get_coin_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["system"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DarwinRequest(BaseModel):
    generations: int = 10
    population_size: int = 30


class MonteCarloRequest(BaseModel):
    iterations: int = 500
    paths: int = 300


class PipelineState:
    running = False
    stage = ""
    progress = 0
    progress_msg = ""
    result: dict | None = None
    start_time: float | None = None

pipeline_state = PipelineState()


class PipelineRequest(BaseModel):
    target_backtests: int = 100000
    mc_iterations: int = 500
    mc_paths: int = 300


training_loop_status = {"running": False, "cycles_completed": 0, "total_cycles": 6, "started_at": None, "last_cycle_at": None, "interval_minutes": 60, "results": []}


@router.post("/api/darwin/run")
async def start_darwin_evolution(req: DarwinRequest):
    from server.api import darwin_lab, commander
    if darwin_lab.running:
        return {"status": "already_running", "progress": darwin_lab.progress}

    symbols = list(CONFIG['ELITE_UNIVERSE'])

    async def run_evo():
        try:
            await darwin_lab.run_evolution(
                commander.exchange, symbols,
                generations=req.generations,
                population_size=req.population_size
            )
            TitanState.add_log("system", f"达尔文进化完成: {req.generations}代 x {req.population_size}个体")
        except Exception as e:
            logger.error(f"达尔文进化异常: {e}")

    asyncio.create_task(run_evo())
    return {"status": "started", "config": {"generations": req.generations, "population_size": req.population_size}}


@router.get("/api/darwin")
async def get_darwin_status():
    from server.api import darwin_lab
    return darwin_lab.get_status()


@router.post("/api/darwin/toggle")
async def toggle_darwin_params():
    from server.api import darwin_lab
    if darwin_lab.results:
        darwin_lab.results["enabled"] = not darwin_lab.results.get("enabled", False)
        darwin_lab._save_results(darwin_lab.results)
        state = "启用" if darwin_lab.results["enabled"] else "禁用"
        TitanState.add_log("system", f"进化参数已{state}")
        return {"status": "ok", "enabled": darwin_lab.results["enabled"]}
    return {"status": "error", "message": "尚无进化结果"}


@router.post("/api/monte-carlo/run")
async def start_monte_carlo(req: MonteCarloRequest):
    from server.api import monte_carlo, commander
    if monte_carlo.running:
        return {"status": "already_running", "progress": monte_carlo.progress}

    symbols_to_use = list(CONFIG['ELITE_UNIVERSE'])

    async def run_mc():
        data_map = {}
        try:
            batch_size = 5
            for i in range(0, len(symbols_to_use), batch_size):
                batch = symbols_to_use[i:i+batch_size]
                tasks = []
                for sym_name in batch:
                    tasks.append(commander.exchange.fetch_ohlcv(f"{sym_name}_USDT", '1h', limit=1000))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for sym_name, res in zip(batch, results):
                    if not isinstance(res, Exception) and res and len(res) > 100:
                        data_map[sym_name] = pd.DataFrame(res, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                await asyncio.sleep(0.2)
            if data_map:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    monte_carlo.run_evolution,
                    data_map,
                    req.iterations,
                    req.paths
                )
                TitanState.add_log("system",
                    f"Monte Carlo完成: {req.iterations}迭代x{req.paths}路径, "
                    f"Calmar={monte_carlo.best_calmar:.3f} Sharpe={monte_carlo.best_sharpe:.3f}")
            else:
                monte_carlo.running = False
        except Exception as e:
            logger.error(f"Monte Carlo异常: {e}")
            monte_carlo.running = False

    asyncio.create_task(run_mc())
    return {"status": "started", "iterations": req.iterations, "paths": req.paths}


@router.get("/api/monte-carlo")
async def get_monte_carlo_status():
    from server.api import monte_carlo
    return monte_carlo.get_status()


@router.get("/api/monte-carlo/explain")
async def get_monte_carlo_explanation():
    from server.api import monte_carlo
    return monte_carlo.get_param_explanation()


@router.post("/api/pipeline/run")
async def start_full_pipeline(req: PipelineRequest):
    from server.api import mega_backtest, monte_carlo, commander
    if pipeline_state.running:
        return {"status": "already_running", "stage": pipeline_state.stage, "progress": pipeline_state.progress}
    if mega_backtest.running or monte_carlo.running:
        return {"status": "engine_busy", "msg": "万次回测或Monte Carlo正在运行"}

    symbols_to_use = list(CONFIG['ELITE_UNIVERSE'])

    async def run_pipeline():
        pipeline_state.running = True
        pipeline_state.stage = "data"
        pipeline_state.progress = 0
        pipeline_state.progress_msg = "正在获取市场数据..."
        pipeline_state.result = None
        pipeline_state.start_time = time.time()

        try:
            data_map = {}
            batch_size = 5
            total_batches = (len(symbols_to_use) + batch_size - 1) // batch_size
            for batch_idx in range(total_batches):
                start = batch_idx * batch_size
                batch = symbols_to_use[start:start+batch_size]
                tasks = []
                for sym_name in batch:
                    tasks.append(commander.exchange.fetch_ohlcv(f"{sym_name}_USDT", '1h', limit=1000))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for sym_name, res in zip(batch, results):
                    if not isinstance(res, Exception) and res and len(res) > 100:
                        data_map[sym_name] = pd.DataFrame(res, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                fetched = start + len(batch)
                pipeline_state.progress = int(fetched / len(symbols_to_use) * 100)
                pipeline_state.progress_msg = f"获取数据 {fetched}/{len(symbols_to_use)}"
                await asyncio.sleep(0.2)

            if len(data_map) < 5:
                pipeline_state.result = {"error": f"有效数据不足: 仅{len(data_map)}个资产"}
                pipeline_state.running = False
                return

            n_assets = len(data_map)
            current_bt = mega_backtest.total_backtests
            remaining = max(0, req.target_backtests - current_bt)
            iters_needed = max(100, int(remaining / n_assets) + 10)
            batch_size = 200

            pipeline_state.stage = "mega_backtest"
            pipeline_state.progress = 0
            pipeline_state.progress_msg = f"策略回测进化: 目标{req.target_backtests}次 (当前{current_bt}次)"
            TitanState.add_log("system", f"🔄 管道启动: 目标{req.target_backtests}次回测, {n_assets}个资产, 需{iters_needed}次迭代")

            total_done = 0
            loop = asyncio.get_event_loop()
            while total_done < iters_needed:
                this_batch = min(batch_size, iters_needed - total_done)
                await loop.run_in_executor(
                    None,
                    mega_backtest.run_evolution_cycle,
                    data_map,
                    this_batch
                )
                total_done += this_batch
                pipeline_state.progress = min(99, int(total_done / iters_needed * 100))
                pipeline_state.progress_msg = (
                    f"策略回测 {mega_backtest.total_backtests:,}次 | "
                    f"迭代 {total_done}/{iters_needed} | "
                    f"最佳Calmar: {mega_backtest.best_calmar:.3f}"
                )
                await asyncio.sleep(0.1)

            mega_result = {
                "total_backtests": mega_backtest.total_backtests,
                "best_calmar": mega_backtest.best_calmar,
                "best_params": mega_backtest.get_best_params(),
                "generations": mega_backtest.total_generations,
            }
            TitanState.add_log("system",
                f"✅ 策略回测完成: {mega_backtest.total_backtests:,}次, Calmar={mega_backtest.best_calmar:.3f}")

            pipeline_state.stage = "monte_carlo"
            pipeline_state.progress = 0
            pipeline_state.progress_msg = "Monte Carlo资管进化启动..."

            await loop.run_in_executor(
                None,
                monte_carlo.run_evolution,
                data_map,
                req.mc_iterations,
                req.mc_paths
            )

            mc_result = {
                "total_simulations": monte_carlo.total_simulations,
                "best_calmar": monte_carlo.best_calmar,
                "best_sharpe": monte_carlo.best_sharpe,
                "best_params": monte_carlo.get_best_params(),
            }
            TitanState.add_log("system",
                f"✅ MC资管完成: {monte_carlo.total_simulations:,}次模拟, Calmar={monte_carlo.best_calmar:.3f}")

            pipeline_state.stage = "final_eval"
            pipeline_state.progress = 50
            pipeline_state.progress_msg = "最终评估: 计算年化收益率..."

            strategy_p = mega_backtest.get_best_params()
            mc_p = monte_carlo.get_best_params()

            all_returns = []
            all_drawdowns = []
            all_trades = []
            all_sharpes = []
            for sym, df in data_map.items():
                r = mega_backtest._fast_backtest(df, strategy_p)
                if r["trade_count"] >= 3:
                    all_returns.append(r["total_return"])
                    all_drawdowns.append(r["max_drawdown"])
                    all_trades.append(r["trade_count"])
                    all_sharpes.append(r["sharpe"])

            if not all_returns:
                pipeline_state.result = {"error": "无有效回测结果"}
                pipeline_state.running = False
                return

            avg_return = np.mean(all_returns)
            median_return = np.median(all_returns)
            p25_return = np.percentile(all_returns, 25)
            p75_return = np.percentile(all_returns, 75)
            avg_dd = np.mean(all_drawdowns)
            worst_dd = np.percentile(all_drawdowns, 95)
            valid_sharpes = [s for s in all_sharpes if abs(s) < 50]
            avg_sharpe = np.median(valid_sharpes) if valid_sharpes else 0.0
            if avg_sharpe == 0 and avg_return > 0:
                ret_std = np.std(all_returns) if len(all_returns) > 1 else 0.01
                avg_sharpe = (avg_return / (ret_std + 1e-10)) * np.sqrt(8.76)
            total_trade_count = sum(all_trades)

            data_hours = 1000
            annual_hours = 8760
            time_scale = annual_hours / data_hours

            kelly_adj = mc_p.get("kelly_fraction", 0.5)
            risk_adj = mc_p.get("max_risk_per_trade", 0.02) / 0.02
            dd_protect = 1.0
            if avg_dd > mc_p.get("drawdown_reduce_trigger", 0.06):
                dd_protect = mc_p.get("drawdown_reduce_factor", 0.5)

            mc_scaling = kelly_adj * risk_adj * dd_protect
            mc_scaling = max(0.3, min(mc_scaling, 2.0))

            raw_annual = avg_return * time_scale
            mc_annual = raw_annual * mc_scaling

            conservative_annual = mc_annual * 0.6
            optimistic_annual = mc_annual * 1.2

            mc_dd_adj = avg_dd * (1 + (1 - dd_protect) * 0.5)
            annual_dd = min(mc_dd_adj * np.sqrt(time_scale) * 0.3, worst_dd * 1.5)
            annual_dd = max(annual_dd, worst_dd)

            calmar_ratio = mc_annual / (annual_dd + 1e-10)

            elapsed = round(time.time() - pipeline_state.start_time, 1)

            pipeline_state.stage = "done"
            pipeline_state.progress = 100
            pipeline_state.progress_msg = f"管道完成 | 年化收益: {mc_annual:.1%} | Calmar: {calmar_ratio:.2f}"
            pipeline_state.result = {
                "summary": {
                    "annual_return": round(mc_annual * 100, 2),
                    "annual_return_conservative": round(conservative_annual * 100, 2),
                    "annual_return_optimistic": round(optimistic_annual * 100, 2),
                    "annual_max_drawdown": round(annual_dd * 100, 2),
                    "calmar_ratio": round(calmar_ratio, 3),
                    "sharpe_ratio": round(avg_sharpe, 3),
                    "total_backtests": mega_backtest.total_backtests,
                    "total_mc_simulations": monte_carlo.total_simulations,
                    "assets_tested": len(all_returns),
                    "avg_trades_per_asset": round(np.mean(all_trades), 1),
                    "total_trades": total_trade_count,
                    "win_rate_range": f"{np.percentile([mega_backtest._fast_backtest(df, strategy_p)['win_rate'] for df in list(data_map.values())[:5]], 25):.0%} - {np.percentile([mega_backtest._fast_backtest(df, strategy_p)['win_rate'] for df in list(data_map.values())[:5]], 75):.0%}",
                    "elapsed_seconds": elapsed,
                },
                "strategy_params": strategy_p,
                "money_management_params": {k: round(v, 4) if isinstance(v, float) else v for k, v in mc_p.items()},
                "per_asset_stats": {
                    "avg_return": round(avg_return * 100, 2),
                    "median_return": round(median_return * 100, 2),
                    "p25_return": round(p25_return * 100, 2),
                    "p75_return": round(p75_return * 100, 2),
                    "avg_drawdown": round(avg_dd * 100, 2),
                    "worst_dd_95pct": round(worst_dd * 100, 2),
                },
                "mc_adjustments": {
                    "kelly_fraction": round(kelly_adj, 4),
                    "risk_scaling": round(risk_adj, 4),
                    "drawdown_protection": round(dd_protect, 4),
                    "total_mc_scaling": round(mc_scaling, 4),
                },
                "risk_feedback": {
                    "annual_dd_limit": round(annual_dd * 100, 2),
                    "daily_loss_limit": round(mc_p.get("daily_loss_limit", 0.02) * 100, 2),
                    "drawdown_trigger": round(mc_p.get("drawdown_reduce_trigger", 0.06) * 100, 2),
                    "drawdown_reduce": round(mc_p.get("drawdown_reduce_factor", 0.5) * 100, 2),
                    "correlation_cap": round(mc_p.get("correlation_cap", 0.7) * 100, 2),
                },
            }

            TitanState.add_log("system",
                f"🏆 管道完成: 年化收益{mc_annual:.1%}, 最大回撤{annual_dd:.1%}, Calmar={calmar_ratio:.2f}, 用时{elapsed}秒")

        except Exception as e:
            logger.error(f"管道异常: {e}")
            import traceback
            traceback.print_exc()
            pipeline_state.result = {"error": str(e)}
            pipeline_state.stage = "error"
        finally:
            pipeline_state.running = False

    asyncio.create_task(run_pipeline())
    return {
        "status": "started",
        "target_backtests": req.target_backtests,
        "mc_iterations": req.mc_iterations,
        "mc_paths": req.mc_paths,
        "assets": len(symbols_to_use),
    }


@router.get("/api/pipeline/status")
async def get_pipeline_status():
    from server.api import mega_backtest, monte_carlo
    return {
        "running": pipeline_state.running,
        "stage": pipeline_state.stage,
        "progress": pipeline_state.progress,
        "progress_msg": pipeline_state.progress_msg,
        "result": pipeline_state.result,
        "mega_backtest": mega_backtest.get_status(),
        "monte_carlo": monte_carlo.get_status(),
    }


@router.post("/api/constitution/reset")
async def reset_constitution():
    """重置永久熔断（谨慎使用）"""
    from server.api import constitution, paper_trader
    constitution.reset_permanent_breaker()
    paper_trader.peak_equity = paper_trader.get_equity()
    paper_trader.save()
    TitanState.add_log("system", "🔧 宪法永久熔断已手动重置")
    return {"status": "ok", "message": "永久熔断已重置"}


@router.post("/api/deep-evolution")
async def trigger_deep_evolution():
    from server.api import synapse, signal_quality, agent_memory, feedback_engine, risk_budget, governor, return_target, ai_coordinator, dispatcher, paper_trader, external_data
    from server.titan_deep_evolution import TitanDeepEvolution
    engine = TitanDeepEvolution()
    mega_data = None
    mm_data = None
    try:
        import os as _os
        mp = _os.path.join(BASE_DIR, "data", "titan_mega_backtest.json")
        if _os.path.exists(mp):
            with open(mp) as f:
                mega_data = json.load(f)
        mmp = _os.path.join(BASE_DIR, "data", "titan_mm_metrics.json")
        if _os.path.exists(mmp):
            with open(mmp) as f:
                mm_data = json.load(f)
    except Exception:
        pass
    result = engine.run_deep_evolution(
        synapse=synapse, signal_quality=signal_quality,
        agent_memory=agent_memory, feedback_engine=feedback_engine,
        risk_budget=risk_budget, governor=governor,
        return_target=return_target, ai_coordinator=ai_coordinator,
        dispatcher=dispatcher, paper_trader=paper_trader,
        mega_backtest_data=mega_data, mm_metrics_data=mm_data,
        memory_bank=external_data.memory_bank,
    )
    TitanState.add_log("system", f"🧬 深度进化完成: {result.get('summary_text', '')[:100]}")
    return result


@router.post("/api/full-training-cycle")
async def full_training_cycle():
    from server.api import synapse, signal_quality, agent_memory, feedback_engine, risk_budget, governor, return_target, ai_coordinator, dispatcher, paper_trader, external_data, adaptive_weights, ai_reviewer, titan_agi, unified_decision, grid_engine, ml_engine
    import time as _time
    start = _time.time()
    results = {"steps": [], "errors": []}

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
        results["steps"].append({"name": "deep_evolution", "status": "ok", "trades": de_result.get("trades_processed", 0), "insights": de_result.get("insights_generated", 0)})
    except Exception as e:
        results["errors"].append(f"deep_evolution: {e}")
        results["steps"].append({"name": "deep_evolution", "status": "error", "error": str(e)})

    try:
        _diagnostic_b = None
        _rra_b = None
        try:
            from server.titan_ai_diagnostic import ai_diagnostic as _diag_b
            _diagnostic_b = _diag_b
        except Exception:
            pass
        try:
            from server.titan_return_rate_agent import return_rate_agent as _rra_b_mod
            _rra_b = _rra_b_mod
        except Exception:
            pass
        coord_result = ai_coordinator.coordinate(
            adaptive_weights=adaptive_weights,
            risk_budget=risk_budget,
            dispatcher=dispatcher,
            synapse=synapse,
            signal_quality=signal_quality,
            paper_trader=paper_trader,
            feedback=feedback_engine,
            use_ai=False,
            reviewer=ai_reviewer,
            diagnostic=_diagnostic_b,
            return_rate_agent=_rra_b,
            agent_memory=agent_memory,
            agi=titan_agi,
        )
        results["steps"].append({"name": "ai_coordinator", "status": "ok", "recommendations": len(coord_result.get("recommendations", []))})
    except Exception as e:
        results["errors"].append(f"ai_coordinator: {e}")
        results["steps"].append({"name": "ai_coordinator", "status": "error", "error": str(e)})

    try:
        from server.titan_return_rate_agent import return_rate_agent
        context = {
            "return_target": return_target.get_status(),
            "paper_portfolio": paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
            "trades_history": paper_trader.trade_history[-20:] if hasattr(paper_trader, 'trade_history') else [],
            "coordinator_recs": ai_coordinator.recommendations,
            "dispatcher_regime": dispatcher.current_regime,
            "risk_budget": risk_budget.get_status(),
            "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
            "unified_decision": unified_decision.get_status(),
            "ml_accuracy": TitanState.market_snapshot.get("ml_status", {}).get("accuracy", 0),
            "synapse": synapse.get_status(),
            "signal_quality": signal_quality.get_status(),
        }
        rra_result = return_rate_agent.think(context, agent_memory, ai_coordinator, return_target)
        TitanState.market_snapshot["return_rate_agent"] = return_rate_agent.get_status()
        results["steps"].append({"name": "return_rate_agent", "status": "ok", "severity": rra_result.get("severity"), "recommendations": len(rra_result.get("recommendations", []))})
    except Exception as e:
        results["errors"].append(f"return_rate_agent: {e}")
        results["steps"].append({"name": "return_rate_agent", "status": "error", "error": str(e)})

    try:
        from server.titan_mega_backtest import TitanMegaBacktest
        mega = TitanMegaBacktest()
        mb_result = mega.run_evolution_cycle(data_map={}, num_iterations=50)
        results["steps"].append({"name": "mega_backtest", "status": "ok", "result": str(mb_result)[:100] if mb_result else "done"})
    except Exception as e:
        results["errors"].append(f"mega_backtest: {e}")
        results["steps"].append({"name": "mega_backtest", "status": "error", "error": str(e)})

    try:
        risk_budget.rebalance(
            dispatcher_allocation=dispatcher.allocation if hasattr(dispatcher, 'allocation') else None,
            synapse_advice=synapse.cross_strategy_rules if hasattr(synapse, 'cross_strategy_rules') else None,
            coordinator_advice=ai_coordinator.get_rebalance_advice(),
        )
        results["steps"].append({"name": "risk_budget_rebalance", "status": "ok"})
    except Exception as e:
        results["errors"].append(f"risk_budget_rebalance: {e}")
        results["steps"].append({"name": "risk_budget_rebalance", "status": "error", "error": str(e)})

    try:
        agent_memory.save()
        synapse.save()
        signal_quality.save()
        governor.save()
        results["steps"].append({"name": "save_all", "status": "ok"})
    except Exception as e:
        results["errors"].append(f"save_all: {e}")
        results["steps"].append({"name": "save_all", "status": "error", "error": str(e)})

    elapsed = round(_time.time() - start, 2)
    ok_count = sum(1 for s in results["steps"] if s["status"] == "ok")
    total_count = len(results["steps"])
    summary = f"Full training cycle: {ok_count}/{total_count} steps OK, {len(results['errors'])} errors, {elapsed}s"
    results["summary"] = summary
    results["elapsed_seconds"] = elapsed
    TitanState.add_log("system", f"🎓 {summary}")
    return results


@router.get("/api/training-loop/status")
async def get_training_loop_status():
    return training_loop_status


@router.post("/api/training-loop/start")
async def start_training_loop(interval_minutes: int = 60, total_cycles: int = 6):
    if training_loop_status["running"]:
        return {"status": "already_running", "message": "训练循环已在运行中"}

    now = datetime.now()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    wait_seconds = (next_hour - now).total_seconds()
    scheduled_hours = [(next_hour + timedelta(hours=i)).strftime("%H:%M") for i in range(total_cycles)]

    training_loop_status["running"] = True
    training_loop_status["cycles_completed"] = 0
    training_loop_status["total_cycles"] = total_cycles
    training_loop_status["started_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    training_loop_status["interval_minutes"] = interval_minutes
    training_loop_status["results"] = []
    training_loop_status["mode"] = "hourly_aligned"
    training_loop_status["next_run_at"] = next_hour.strftime("%Y-%m-%d %H:%M:%S")
    training_loop_status["scheduled_hours"] = scheduled_hours
    training_loop_status["wait_seconds_to_first"] = round(wait_seconds)

    asyncio.create_task(_run_training_loop_aligned(total_cycles))
    TitanState.add_log("system", f"🔄 整点训练循环已启动: 首轮在 {next_hour.strftime('%H:%M')} 执行, 共{total_cycles}轮, 计划时间: {', '.join(scheduled_hours)}")
    return {"status": "started", "total_cycles": total_cycles, "first_run": next_hour.strftime("%H:%M:%S"), "wait_seconds": round(wait_seconds), "scheduled_hours": scheduled_hours}


@router.post("/api/training-loop/stop")
async def stop_training_loop():
    training_loop_status["running"] = False
    TitanState.add_log("system", "⏹️ 训练循环已手动停止")
    return {"status": "stopped", "cycles_completed": training_loop_status["cycles_completed"]}


async def _run_training_loop_aligned(total_cycles):
    now = datetime.now()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    wait_seconds = (next_hour - now).total_seconds()

    TitanState.add_log("system", f"⏳ 等待至整点 {next_hour.strftime('%H:%M')} 开始首轮训练 (约{int(wait_seconds)}秒)")

    check_interval = 10
    while wait_seconds > 0 and training_loop_status["running"]:
        sleep_time = min(check_interval, wait_seconds)
        await asyncio.sleep(sleep_time)
        wait_seconds -= sleep_time
        now = datetime.now()
        remaining = (next_hour - now).total_seconds()
        if remaining <= 0:
            break
        wait_seconds = remaining
        training_loop_status["next_run_at"] = next_hour.strftime("%Y-%m-%d %H:%M:%S")
        training_loop_status["wait_seconds_to_first"] = round(remaining)

    for cycle in range(total_cycles):
        if not training_loop_status["running"]:
            break

        cycle_num = cycle + 1
        target_time = next_hour + timedelta(hours=cycle)
        TitanState.add_log("system", f"🔄 整点训练 {cycle_num}/{total_cycles} @ {target_time.strftime('%H:%M')} 开始...")

        try:
            result = await full_training_cycle()
        except Exception as e2:
            result = {"summary": f"Cycle {cycle_num} error: {e2}", "errors": [str(e2)]}

        training_loop_status["cycles_completed"] = cycle_num
        training_loop_status["last_cycle_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        training_loop_status["results"].append({
            "cycle": cycle_num,
            "time": datetime.now().strftime("%H:%M:%S"),
            "scheduled": target_time.strftime("%H:%M"),
            "summary": result.get("summary", "unknown"),
            "errors": len(result.get("errors", [])),
        })

        TitanState.add_log("system", f"✅ 整点训练 {cycle_num}/{total_cycles} @ {target_time.strftime('%H:%M')} 完成: {result.get('summary', '')[:80]}")

        if cycle_num < total_cycles and training_loop_status["running"]:
            next_target = next_hour + timedelta(hours=cycle + 1)
            now = datetime.now()
            sleep_secs = (next_target - now).total_seconds()
            training_loop_status["next_run_at"] = next_target.strftime("%Y-%m-%d %H:%M:%S")
            if sleep_secs > 0:
                TitanState.add_log("system", f"⏳ 下一轮整点训练: {next_target.strftime('%H:%M')}，等待 {int(sleep_secs)}秒")
                while sleep_secs > 0 and training_loop_status["running"]:
                    s = min(10, sleep_secs)
                    await asyncio.sleep(s)
                    sleep_secs -= s

    training_loop_status["running"] = False
    training_loop_status["next_run_at"] = None
    TitanState.add_log("system", f"🏁 整点训练循环全部完成: {training_loop_status['cycles_completed']}/{total_cycles}轮")


@router.get("/api/equity-history")
async def get_equity_history():
    from server.api import paper_trader
    try:
        trades = paper_trader.trade_history
        if not trades:
            return {"equity_curve": []}
        equity = paper_trader.INITIAL_CAPITAL
        curve = [{"time": "起始", "equity": equity}]
        for t in trades:
            pnl = t.get("pnl_value", 0)
            equity += pnl
            curve.append({
                "time": t.get("close_time", t.get("open_time", ""))[:10] if t.get("close_time") or t.get("open_time") else "",
                "equity": round(equity, 2),
                "symbol": t.get("symbol", ""),
                "pnl": round(pnl, 2),
            })
        return {"equity_curve": curve[-200:]}
    except Exception as e:
        return {"equity_curve": [], "error": str(e)}


@router.get("/api/notifications")
async def get_notifications():
    try:
        logs = list(TitanState.market_snapshot.get("logs", []))
        important_types = {"system", "warn", "alert", "error", "critical"}
        filtered = [log for log in logs if log.get("type", "") in important_types]
        return {"notifications": filtered[:50], "total": len(filtered)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/system/comprehensive-optimize")
async def comprehensive_optimize(source: str = "manual_optimize"):
    from server.api import synapse, paper_trader, adaptive_weights, ml_engine, commander, dispatcher, risk_budget, mega_backtest, ai_coordinator, grid_engine, constitution
    results = {"steps": [], "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "source": source}

    bad_rules = [
        r for r in synapse.cross_strategy_rules
        if r.get("type") == "asset_avoid" and not r.get("asset", "").replace("/USDT", "").replace("_USDT", "").strip().isalpha()
        and len(r.get("asset", "")) > 10
    ]
    if bad_rules:
        before = len(synapse.cross_strategy_rules)
        synapse.cross_strategy_rules = [
            r for r in synapse.cross_strategy_rules
            if not (r.get("type") == "asset_avoid" and len(r.get("asset", "")) > 10 and not r.get("asset", "").isalpha())
        ]
        cleaned = before - len(synapse.cross_strategy_rules)
        results["steps"].append({"name": "clean_invalid_rules", "cleaned": cleaned})

    target_freeze = ["BLUAI", "XAUT", "POWER", "USD1", "PAXG"]
    frozen_new = []
    already_frozen = []
    for asset in target_freeze:
        existing = any(
            r.get("type") == "asset_avoid" and r.get("asset") == asset
            for r in synapse.cross_strategy_rules
        )
        if existing:
            already_frozen.append(asset)
        else:
            synapse.cross_strategy_rules.append({
                "type": "asset_avoid", "asset": asset, "win_rate": 0, "trades": 0,
                "applies_to": "all", "reason": "综合优化:表现最差资产冻结",
            })
            frozen_new.append(asset)
    synapse.save()

    active_positions = paper_trader.get_positions() if hasattr(paper_trader, 'get_positions') else []
    closed_positions = []
    for pos in active_positions:
        pos_sym = pos.get("symbol", "").replace("/USDT", "").replace("_USDT", "").upper()
        if pos_sym in target_freeze:
            try:
                price_data = TitanState.market_snapshot.get("prices", {})
                current_price = price_data.get(pos.get("symbol", ""), pos.get("entry_price", 0))
                close_result = paper_trader.close_position(pos["id"], current_price, "comprehensive_optimize_freeze")
                if close_result:
                    closed_positions.append(pos_sym)
            except Exception:
                pass

    results["steps"].append({
        "name": "freeze_worst_assets",
        "new_frozen": frozen_new,
        "already_frozen": already_frozen,
        "closed_positions": closed_positions,
    })
    TitanState.add_log("system", f"🚫 综合优化: 冻结资产 {', '.join(target_freeze)} (新增{len(frozen_new)})")

    adaptive_weights.ml_weight_override = 0.05
    TitanState.add_log("system", "📊 综合优化: ML权重临时降至5%，等待重训练验证")
    results["steps"].append({"name": "reduce_ml_weight", "new_weight": 0.05})

    ml_retrain_result = {"status": "pending"}
    try:
        if hasattr(ml_engine, '_training_in_progress') and ml_engine._training_in_progress:
            ml_retrain_result = {"status": "skipped", "reason": "训练进行中"}
        else:
            training_data = getattr(commander, '_last_training_data', None)
            if training_data and len(training_data) > 0:
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, ml_engine.train, training_data)
                ml_retrain_result = {"status": "ok" if success else "failed", "samples": len(training_data)}
                TitanState.add_log("system", f"🧠 综合优化: ML重训练完成 ({len(training_data)}样本)")
            else:
                ml_retrain_result = {"status": "no_data", "reason": "训练数据不足，将在下次扫描后自动训练"}
    except Exception as e:
        ml_retrain_result = {"status": "error", "error": str(e)}
    results["steps"].append({"name": "ml_retrain", **ml_retrain_result})

    old_alloc = dict(dispatcher.allocation)
    dispatcher.allocation = {"trend": 0.35, "range": 0.30, "grid": 0.35}
    if "grid" not in dispatcher.active_strategies:
        dispatcher.active_strategies.append("grid")
    if "range" not in dispatcher.active_strategies:
        dispatcher.active_strategies.append("range")
    dispatcher.save()

    try:
        grid_budget = 500
        available = risk_budget.get_available_budget("grid")
        if available < grid_budget:
            risk_budget.request_capital("grid", grid_budget)
        range_budget = 300
        available_r = risk_budget.get_available_budget("range")
        if available_r < range_budget:
            risk_budget.request_capital("range", range_budget)
        risk_budget.save()
    except Exception:
        pass

    results["steps"].append({
        "name": "rebalance_strategies",
        "old_allocation": old_alloc,
        "new_allocation": dispatcher.allocation,
        "active_strategies": dispatcher.active_strategies,
    })
    TitanState.add_log("system", f"⚖️ 综合优化: 策略再平衡 trend={dispatcher.allocation['trend']:.0%} range={dispatcher.allocation['range']:.0%} grid={dispatcher.allocation['grid']:.0%}")

    mega_result = {"status": "pending"}
    try:
        if mega_backtest.running:
            mega_result = {"status": "already_running"}
        else:
            evo_symbols = list(CONFIG.get('ELITE_UNIVERSE', []))
            if evo_symbols:
                async def run_mega_optimization():
                    data_map = {}
                    try:
                        for i in range(0, len(evo_symbols), 5):
                            batch = evo_symbols[i:i+5]
                            tasks = [commander.exchange.fetch_ohlcv(f"{s}_USDT", '1h', limit=1000) for s in batch]
                            fetch_results = await asyncio.gather(*tasks, return_exceptions=True)
                            for s, r in zip(batch, fetch_results):
                                if not isinstance(r, Exception) and r and len(r) > 100:
                                    data_map[s] = pd.DataFrame(r, columns=['t','o','h','l','c','v'])
                            await asyncio.sleep(0.2)
                        if len(data_map) >= 10:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, mega_backtest.run_evolution_cycle, data_map, 200)
                            TitanState.add_log("system",
                                f"🧬 综合优化: MegaBacktest 200次迭代完成 {len(data_map)}资产 Calmar={mega_backtest.best_calmar:.3f}")
                        else:
                            mega_backtest.running = False
                    except Exception as e:
                        mega_backtest.running = False
                        TitanState.add_log("warn", f"MegaBacktest异常: {str(e)[:60]}")

                asyncio.create_task(run_mega_optimization())
                mega_result = {"status": "started", "iterations": 200, "assets": len(evo_symbols)}
            else:
                mega_result = {"status": "no_universe"}
    except Exception as e:
        mega_result = {"status": "error", "error": str(e)}
    results["steps"].append({"name": "mega_backtest_evolution", **mega_result})

    ai_coordinator.recommendations["size_multiplier"] = 0.5
    ai_coordinator.recommendations["throttle_level"] = "tight"
    ai_coordinator.save()
    results["steps"].append({
        "name": "tighten_risk",
        "size_multiplier": 0.5,
        "throttle_level": "tight",
    })
    TitanState.add_log("system", "🛡️ 综合优化: 风控收紧 仓位乘数=0.5 节流=tight")

    try:
        history_path = os.path.join(CONFIG.get("DATA_DIR", "data"), "auto_exec_history.json")
        exec_record = {
            "time": results["timestamp"],
            "health": "comprehensive_optimize",
            "actions": [s["name"] for s in results["steps"]],
            "source": source,
            "had_actions": True,
        }
        if not hasattr(TitanState, '_auto_exec_history'):
            TitanState._auto_exec_history = []
        TitanState._auto_exec_history.append(exec_record)
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        with open(history_path, "w") as f:
            json.dump(TitanState._auto_exec_history[-100:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return results


@router.get("/api/autopilot/status")
async def autopilot_status():
    from server.api import autopilot
    return autopilot.get_status()

@router.post("/api/autopilot/start")
async def autopilot_start():
    from server.api import autopilot, risk_budget, constitution, ml_engine, paper_trader, signal_quality, dispatcher, synapse, external_data
    modules = {
        "risk_budget": risk_budget,
        "constitution": constitution,
        "ml_engine": ml_engine,
        "paper_trader": paper_trader,
        "signal_quality": signal_quality,
        "dispatcher": dispatcher,
        "state": TitanState,
        "deep_evolution": None,
        "synapse": synapse,
        "memory_bank": external_data,
    }
    await autopilot.start(modules)
    return {"status": "started", "message": "AutoPilot自动驾驶已启动"}

@router.post("/api/autopilot/stop")
async def autopilot_stop():
    from server.api import autopilot
    autopilot.stop()
    return {"status": "stopped", "message": "AutoPilot已停止"}

@router.post("/api/autopilot/training")
async def autopilot_training(iterations: int = 6, hours: float = 5.5):
    from server.api import autopilot, risk_budget, constitution, ml_engine, paper_trader, signal_quality, dispatcher
    if autopilot.training_status.get("running"):
        return {"status": "already_running", "iteration": autopilot.training_status.get("iteration")}
    modules = {
        "risk_budget": risk_budget,
        "constitution": constitution,
        "ml_engine": ml_engine,
        "paper_trader": paper_trader,
        "signal_quality": signal_quality,
        "dispatcher": dispatcher,
        "state": TitanState,
        "deep_evolution": None,
    }
    async def _run_training_step(start_step=1):
        return await _autopilot_single_training(start_step)
    class _DEProxy:
        async def run_full_pipeline(self, start_step=1):
            return await _run_training_step(start_step)
    modules["deep_evolution"] = _DEProxy()
    asyncio.create_task(autopilot.run_cyclic_training(modules, max_iterations=iterations, time_budget_hours=hours))
    return {"status": "started", "max_iterations": iterations, "time_budget_hours": hours}

async def _autopilot_single_training(start_step=1):
    from server.api import ml_engine, money_manager, mega_backtest, monte_carlo
    from server.titan_deep_evolution import TitanDeepEvolution
    deep_evo = TitanDeepEvolution()
    local_path = os.path.join(BASE_DIR, "data", "titan_historical_ohlcv.json")
    preloaded = {}
    if os.path.exists(local_path):
        with open(local_path) as f:
            raw = json.load(f)
        for coin, info in raw.items():
            candles = info.get("data", [])
            if len(candles) >= 100:
                df = pd.DataFrame(candles, columns=['t','o','h','l','c','v'])
                for col in ['o','h','l','c','v']:
                    df[col] = df[col].astype(float)
                preloaded[coin] = df
    elite = list(CONFIG['ELITE_UNIVERSE'])
    results = {}
    if start_step <= 1:
        try:
            training_data = {}
            for coin in preloaded:
                training_data[coin] = {'1h': preloaded[coin].copy(), '4h': preloaded[coin]}
            if training_data:
                result = ml_engine.deep_train(training_data, money_manager)
                results["ml_engine"] = {"status": "ok", "accuracy": result.get("accuracy"), "f1": result.get("f1")}
        except Exception as e:
            results["ml_engine"] = {"status": "error", "error": str(e)[:100]}
    if start_step <= 2:
        try:
            mm_r = money_manager.full_kelly_sharpe_optimization(preloaded)
            results["money_manager"] = {"status": "ok" if mm_r else "skipped"}
        except Exception as e:
            results["money_manager"] = {"status": "error", "error": str(e)[:100]}
    if start_step <= 3:
        try:
            mb_r = mega_backtest.run_mega_evolution(elite[:20], preloaded_data=preloaded, rounds=500)
            results["mega_backtest"] = {"status": "ok", "best_calmar": getattr(mega_backtest, 'best_calmar', 0)}
        except Exception as e:
            results["mega_backtest"] = {"status": "error", "error": str(e)[:100]}
    if start_step <= 5:
        try:
            mc_r = await monte_carlo.run(elite[:20], preloaded_data=preloaded, rounds=500, paths=300)
            results["monte_carlo"] = {"status": "ok", "best_calmar": mc_r.get("best_calmar"), "best_sharpe": mc_r.get("best_sharpe")}
        except Exception as e:
            results["monte_carlo"] = {"status": "error", "error": str(e)[:100]}
    return results

@router.post("/api/autopilot/resolve/{index}")
async def autopilot_resolve(index: int, body: dict = None):
    from server.api import autopilot
    if body is None:
        body = {}
    if 0 <= index < len(autopilot.pending_ceo_decisions):
        decision = autopilot.pending_ceo_decisions[index]
        decision["resolved"] = True
        decision["ceo_action"] = body.get("action", "approve")
        decision["ceo_note"] = body.get("note", "")
        decision["resolved_at"] = datetime.now().isoformat()
        autopilot._save_state()
        return {"status": "resolved", "action": decision["ceo_action"]}
    return {"status": "not_found"}

@router.post("/api/autopilot/test-email")
async def send_test_email():
    from server.api import autopilot, paper_trader, constitution, risk_budget, ml_engine, signal_quality, dispatcher
    try:
        modules = {
            "state": TitanState,
            "paper_trader": paper_trader,
            "constitution": constitution,
            "risk_budget": risk_budget,
            "ml_engine": ml_engine,
            "signal_quality": signal_quality,
            "dispatcher": dispatcher,
            "memory_bank": None,
        }
        reports = {}
        reports["risk"] = autopilot._check_risk_system(modules)
        reports["ml"] = autopilot._check_ml_status(modules)
        reports["trades"] = autopilot._check_trade_performance(modules)
        reports["signal_quality"] = autopilot._check_signal_quality(modules)
        reports["dispatcher"] = autopilot._check_dispatcher(modules)
        reports["constitution"] = autopilot._check_constitution(modules)
        reports["memory"] = autopilot._check_memory(modules)

        result = autopilot._send_operations_email(modules, reports)
        return {"status": "sent" if result else "failed"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
