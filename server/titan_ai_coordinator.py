import os
import json
import logging
import time
from datetime import datetime
from server.titan_utils import atomic_json_save
from server.titan_db import db_connection

logger = logging.getLogger("TitanAICoordinator")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATOR_PATH = os.path.join(BASE_DIR, "data", "titan_coordinator.json")


class TitanAICoordinator:
    def __init__(self):
        self.module_metrics = {
            "ml_accuracy": 0.5,
            "ml_win_rate": 0.5,
            "rule_win_rate": 0.5,
            "signal_quality_avg": 0.5,
            "regime": "unknown",
            "drawdown_pct": 0.0,
            "consecutive_losses": 0,
            "consecutive_wins": 0,
            "daily_pnl": 0.0,
            "total_trades": 0,
            "synapse_rule_count": 0,
            "frozen_strategies": 0,
            "capital_utilization": 0.0,
            "ml_weight": 0.5,
            "rule_weight": 0.5,
            "equity": 100000,
            "total_pnl": 0.0,
            "open_positions": 0,
            "max_dd_pct": 0.0,
            "max_drawdown_ever": 0.0,
            "active_strategies": [],
            "strategy_budgets": {},
            "grid_active": 0,
            "grid_win_rate": 0,
            "grid_geo_wr": 0.0,
            "grid_arith_wr": 0.0,
            "grid_trailing_shifts": 0,
            "feedback_suggestions": 0,
        }
        self.recommendations = {
            "size_multiplier": 1.0,
            "throttle_level": "normal",
            "regime_bias": "neutral",
            "risk_level": "standard",
            "rebalance_advice": {},
            "reasoning": "",
        }
        self.strategic_directives = {
            "strategy_preference": "balanced",
            "asset_blacklist": [],
            "asset_whitelist": [],
            "aggression_mode": "moderate",
            "max_concurrent_positions": 8,
            "regime_strategy_map": {
                "trending": {"trend": 0.7, "range": 0.0, "grid": 0.3},
                "ranging": {"trend": 0.2, "range": 0.0, "grid": 0.8},
                "volatile": {"trend": 0.3, "range": 0.0, "grid": 0.7},
                "unknown": {"trend": 0.5, "range": 0.0, "grid": 0.5},
            },
            "min_signal_score": 73,
            "directives_updated_at": "",
        }
        self.intelligence_pool = {}
        self.coordination_log = []
        self.ai_analysis_history = []
        self.reflection_log = []
        self.stats = {
            "total_coordinations": 0,
            "total_ai_analyses": 0,
            "last_coordination": "",
            "last_ai_analysis": "",
            "module_sync_count": 0,
            "reflection_count": 0,
            "ai_accuracy_score": 0.5,
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(COORDINATOR_PATH):
                with open(COORDINATOR_PATH, "r") as f:
                    data = json.load(f)
                self.module_metrics = data.get("module_metrics", self.module_metrics)
                self.recommendations = data.get("recommendations", self.recommendations)
                self.stats = data.get("stats", self.stats)
                self.coordination_log = data.get("coordination_log", [])[-50:]
                self.ai_analysis_history = data.get("ai_analysis_history", [])[-20:]
                self.reflection_log = data.get("reflection_log", [])[-10:]
                loaded_sd = data.get("strategic_directives", self.strategic_directives)
                if loaded_sd.get("min_signal_score", 73) > 80:
                    loaded_sd["min_signal_score"] = 73
                    logger.info(f"[CTO] 持久化min_signal_score>{80}过高, 重置为73")
                dd_loaded = self.module_metrics.get("drawdown_pct", 0)
                cl_loaded = self.module_metrics.get("consecutive_losses", 0)
                if loaded_sd.get("aggression_mode") == "conservative" and dd_loaded < 2 and cl_loaded < 5:
                    loaded_sd["aggression_mode"] = "moderate"
                    logger.info(f"[CTO] 持久化aggressive=conservative但DD={dd_loaded}%<2%, 重置为moderate")
                self.strategic_directives = loaded_sd
                self.intelligence_pool = data.get("intelligence_pool", {})
                logger.info(f"AICoordinator loaded: {self.stats['total_coordinations']} coordinations")
        except Exception as e:
            logger.warning(f"AICoordinator load failed: {e}")

    def _record_cto_decision(self, decision_type, target, old_value, new_value, reason=""):
        try:
            m = self.module_metrics
            btc_price = m.get("btc_price", 0)
            fng = m.get("fng_value", 0)
            btc_trend = m.get("btc_macro_trend", "unknown")
            dd = m.get("drawdown_pct", 0)

            target_price = None
            if decision_type == "blacklist_add":
                try:
                    import ccxt
                    exchange = ccxt.gate()
                    ticker = exchange.fetch_ticker(f"{target}/USDT")
                    if ticker and ticker.get("last"):
                        target_price = ticker["last"]
                except Exception:
                    pass

            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO cto_decisions
                    (decision_type, target, old_value, new_value, reason,
                     btc_price_at_decision, fng_at_decision,
                     btc_macro_trend, current_drawdown_pct, target_price_at_decision)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (decision_type, target, str(old_value), str(new_value),
                      reason, btc_price, fng, btc_trend, dd, target_price))
                conn.commit()
        except Exception as e:
            logger.warning(f"CTO决策记录失败(非致命): {e}")

    def save(self):
        try:
            existing = {}
            if os.path.exists(COORDINATOR_PATH):
                try:
                    with open(COORDINATOR_PATH, 'r') as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}

            preserved_keys = ['last_daily_tasks_date', 'last_evolution_run', 'last_daily_tasks_results']
            preserved = {k: existing[k] for k in preserved_keys if k in existing}

            data = {
                "module_metrics": self.module_metrics,
                "recommendations": self.recommendations,
                "stats": self.stats,
                "coordination_log": self.coordination_log[-50:],
                "ai_analysis_history": self.ai_analysis_history[-20:],
                "reflection_log": self.reflection_log[-10:],
                "strategic_directives": self.strategic_directives,
                "intelligence_pool": self.intelligence_pool,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            data.update(preserved)
            atomic_json_save(COORDINATOR_PATH, data)
        except Exception:
            pass

    def collect_metrics(self, adaptive_weights=None, risk_budget=None, dispatcher=None,
                        synapse=None, signal_quality=None, paper_trader=None, feedback=None,
                        grid_engine=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if adaptive_weights:
            aw = adaptive_weights.get_adaptive_weights()
            self.module_metrics["ml_accuracy"] = aw.get("performance", 50) / 100
            self.module_metrics["ml_weight"] = aw.get("ml_weight", 0.5)
            self.module_metrics["rule_weight"] = aw.get("rule_weight", 0.5)
            ml_preds = [p for p in adaptive_weights.ml_predictions if p.get("outcome") and p["outcome"] != "neutral"]
            if ml_preds:
                recent = ml_preds[-30:]
                self.module_metrics["ml_win_rate"] = sum(1 for p in recent if p["outcome"] == "correct") / len(recent)

        if risk_budget:
            status = risk_budget.get_status()
            self.module_metrics["drawdown_pct"] = status.get("total_drawdown_pct", 0)
            self.module_metrics["daily_pnl"] = status.get("daily_pnl", 0)
            frozen = sum(1 for s, b in status.get("strategy_budgets", {}).items() if b.get("frozen"))
            self.module_metrics["frozen_strategies"] = frozen
            total_available = sum(b.get("available", 0) for b in status.get("strategy_budgets", {}).values())
            total_cap = status.get("total_capital", 10000)
            self.module_metrics["capital_utilization"] = round(1.0 - total_available / max(total_cap, 1), 4)
            self.module_metrics["max_drawdown_ever"] = status.get("max_drawdown_ever_pct", 0)
            budgets = status.get("strategy_budgets", {})
            self.module_metrics["strategy_budgets"] = {
                k: {"available": round(v.get("available", 0), 2), "frozen": v.get("frozen", False),
                     "drawdown": round(v.get("drawdown_pct", 0), 2)}
                for k, v in budgets.items()
            }

        if dispatcher:
            self.module_metrics["regime"] = dispatcher.current_regime
            self.module_metrics["active_strategies"] = list(getattr(dispatcher, "active_strategies", []))

        if synapse:
            syn_status = synapse.get_status()
            self.module_metrics["synapse_rule_count"] = syn_status.get("total_rules", 0)

        if paper_trader:
            self.module_metrics["consecutive_wins"] = paper_trader.consecutive_wins
            self.module_metrics["consecutive_losses"] = paper_trader.consecutive_losses
            self.module_metrics["total_trades"] = paper_trader.total_wins + paper_trader.total_losses
            total = paper_trader.total_wins + paper_trader.total_losses
            if total >= 5:
                self.module_metrics["rule_win_rate"] = paper_trader.total_wins / total
            try:
                portfolio = paper_trader.get_portfolio_summary()
                self.module_metrics["equity"] = portfolio.get("equity", 100000)
                self.module_metrics["total_pnl"] = portfolio.get("total_pnl", 0)
                self.module_metrics["max_dd_pct"] = portfolio.get("max_drawdown_pct", 0)
                self.module_metrics["current_dd_pct"] = portfolio.get("current_drawdown_pct", 0)
            except Exception:
                self.module_metrics["equity"] = paper_trader.get_equity() if hasattr(paper_trader, 'get_equity') else 100000
                self.module_metrics["total_pnl"] = sum(t.get("pnl_value", 0) for t in getattr(paper_trader, "trade_history", []))
            self.module_metrics["open_positions"] = len(getattr(paper_trader, "positions", []))
            self.module_metrics["max_dd_pct"] = getattr(paper_trader, "max_drawdown_pct", 0)

            try:
                self._calc_wall_street_metrics(paper_trader)
            except Exception:
                pass

        if signal_quality:
            sq_status = signal_quality.get_status()
            self.module_metrics["signal_quality_avg"] = sq_status.get("avg_quality", 0.5)

        if grid_engine:
            try:
                gs = grid_engine.get_status()
                self.module_metrics["grid_active"] = gs.get("active_grids", 0)
                self.module_metrics["grid_win_rate"] = gs.get("win_rate", 0)
                ms = gs.get("mode_stats", {})
                geo = ms.get("geometric", {})
                arith = ms.get("arithmetic", {})
                trail = ms.get("trailing", {})
                self.module_metrics["grid_geo_wr"] = round(geo.get("wins", 0) / max(geo.get("trades", 1), 1) * 100, 1)
                self.module_metrics["grid_arith_wr"] = round(arith.get("wins", 0) / max(arith.get("trades", 1), 1) * 100, 1)
                self.module_metrics["grid_trailing_shifts"] = trail.get("successful_shifts", 0)
            except Exception:
                pass

        if feedback:
            try:
                fb_status = feedback.get_status() if hasattr(feedback, "get_status") else {}
                self.module_metrics["feedback_suggestions"] = fb_status.get("pending_suggestions", 0)
            except Exception:
                pass

        try:
            from server.titan_position_advisor import position_advisor
            adv_snap = getattr(position_advisor, 'advice_history', [])
            if adv_snap:
                recent = adv_snap[-10:]
                action_dist = {}
                for a in recent:
                    act = a.get("action", "hold")
                    action_dist[act] = action_dist.get(act, 0) + 1
                self.module_metrics["advisor_actions"] = ", ".join(f"{k}:{v}" for k, v in action_dist.items())
            else:
                self.module_metrics["advisor_actions"] = "暂无数据"
        except Exception:
            self.module_metrics["advisor_actions"] = "未加载"

        self.stats["module_sync_count"] += 1
        self.stats["last_coordination"] = now
        return self.module_metrics

    def _calc_wall_street_metrics(self, paper_trader):
        import math
        _TEST_SYMBOLS = {'STABLE', 'COINON', 'MY', 'USELESS', '我踏马来了'}
        trade_log = [t for t in getattr(paper_trader, 'trade_history', getattr(paper_trader, 'trade_log', []))
                     if t.get('symbol') not in _TEST_SYMBOLS]
        if len(trade_log) < 2:
            return

        pnls = [t.get("pnl_pct", 0) for t in trade_log]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        gross_win = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        self.module_metrics["ws_profit_factor"] = round(gross_win / gross_loss, 2) if gross_loss > 0 else 0
        self.module_metrics["ws_expectancy"] = round(sum(pnls) / len(pnls), 3) if pnls else 0
        self.module_metrics["ws_risk_reward"] = round(abs((sum(wins)/len(wins)) / (sum(losses)/len(losses))), 2) if wins and losses and sum(losses) != 0 else 0

        max_cw = 0
        max_cl = 0
        cw = 0
        cl = 0
        for p in pnls:
            if p > 0:
                cw += 1; cl = 0
            else:
                cl += 1; cw = 0
            max_cw = max(max_cw, cw)
            max_cl = max(max_cl, cl)
        self.module_metrics["ws_max_cw"] = max_cw
        self.module_metrics["ws_max_cl"] = max_cl

        first_time = None
        last_time = None
        for t in trade_log:
            ct = t.get("close_time") or t.get("time", "")
            if ct:
                if first_time is None or ct < first_time:
                    first_time = ct
                if last_time is None or ct > last_time:
                    last_time = ct

        trading_days = max(1, len(pnls) // 3)
        if first_time and last_time:
            try:
                from datetime import datetime as dt2
                ft = dt2.fromisoformat(first_time[:19])
                lt = dt2.fromisoformat(last_time[:19])
                trading_days = max(1, (lt - ft).days)
            except Exception:
                pass

        initial = getattr(paper_trader, 'INITIAL_CAPITAL', 100000)
        equity = paper_trader.get_equity() if hasattr(paper_trader, 'get_equity') else initial
        total_return = (equity - initial) / initial * 100 if initial > 0 else 0
        years = trading_days / 365

        if years > 0 and equity > 0 and initial > 0:
            self.module_metrics["ws_annualized_return"] = round(((equity / initial) ** (1 / years) - 1) * 100, 2)
        else:
            self.module_metrics["ws_annualized_return"] = round(total_return, 2)

        peak = initial
        max_dd = 0
        running = initial
        for p in pnls:
            running *= (1 + p / 100)
            peak = max(peak, running)
            dd = (peak - running) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        self.module_metrics["ws_max_dd"] = round(max_dd, 2)

        daily_returns = [p / 100 for p in pnls]
        mean_r = sum(daily_returns) / len(daily_returns)
        var_r = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1) if len(daily_returns) > 1 else 0
        std_r = math.sqrt(var_r) if var_r > 0 else 0
        trades_per_year = len(pnls) / max(years, 0.01)
        annual_std = std_r * math.sqrt(trades_per_year) if trades_per_year > 0 else 0
        self.module_metrics["ws_volatility"] = round(annual_std * 100, 2)

        if std_r > 0:
            self.module_metrics["ws_sharpe"] = round((mean_r / std_r) * math.sqrt(trades_per_year), 2)
        else:
            self.module_metrics["ws_sharpe"] = 0

        downside = [r for r in daily_returns if r < 0]
        if downside:
            down_var = sum(r ** 2 for r in downside) / len(downside)
            down_std = math.sqrt(down_var)
            if down_std > 0:
                self.module_metrics["ws_sortino"] = round((mean_r / down_std) * math.sqrt(trades_per_year), 2)
            else:
                self.module_metrics["ws_sortino"] = 0
        else:
            self.module_metrics["ws_sortino"] = 0

        if max_dd > 0:
            self.module_metrics["ws_calmar"] = round(self.module_metrics.get("ws_annualized_return", 0) / max_dd, 2)
        else:
            self.module_metrics["ws_calmar"] = 0

    def collect_intelligence(self, reviewer=None, diagnostic=None, return_rate_agent=None, synapse=None, agent_memory=None, agi=None):
        intel = {}

        if reviewer:
            try:
                rev_status = reviewer.get_status()
                validated = [p for p in getattr(reviewer, 'validated_patterns', []) if p.get('status') == 'validated']
                recent_reviews = rev_status.get('recent_reviews', [])

                losing_patterns = []
                for r in getattr(reviewer, 'reviews', [])[-20:]:
                    analysis = r.get('ai_analysis', {})
                    if analysis.get('verdict') in ('poor', 'bad') and analysis.get('score', 100) < 40:
                        sym = r.get('symbol', '')
                        if sym:
                            losing_patterns.append(sym)

                total_trades = self.module_metrics.get("total_trades", 0)
                win_rate = self.module_metrics.get("rule_win_rate", 0) * 100
                total_pnl = self.module_metrics.get("total_pnl", 0)
                equity = self.module_metrics.get("equity", 100000)

                intel["reviewer"] = {
                    "total_reviews": rev_status.get("total_reviews", 0),
                    "avg_score": rev_status.get("avg_score", 0),
                    "validated_patterns_count": len(validated),
                    "recent_losing_symbols": list(set(losing_patterns))[:10],
                    "total_trades": total_trades,
                    "win_rate": win_rate,
                    "total_pnl": total_pnl,
                    "equity": equity,
                    "pending_trades": rev_status.get("pending_trades", 0),
                    "recent_reviews_detail": [
                        f"{r.get('type','')}: score={r.get('score',0)}, verdict={r.get('verdict','')}"
                        for r in recent_reviews[-5:]
                    ],
                    "summary": f"复盘{rev_status.get('total_reviews', 0)}笔/{total_trades}总交易, 均分{rev_status.get('avg_score', 0):.0f}, 胜率{win_rate:.1f}%, 盈亏${total_pnl:+,.2f}"
                }
            except Exception as e:
                logger.warning(f"收集Reviewer情报失败: {e}")

        if diagnostic:
            try:
                diag_status = diagnostic.get_status()
                latest = diag_status.get("latest_report", {})
                diag_inner = latest.get("diagnosis", latest)
                health = diag_inner.get("health_score", 0)
                severity = diag_inner.get("severity", "unknown")
                summary_text = diag_inner.get("summary", "")
                vs_last = diag_inner.get("vs_last", "")
                dims = diag_inner.get("dimensions", {})
                issues = []
                suggestions = []
                for dim_name, dim_data in dims.items():
                    if isinstance(dim_data, dict):
                        for iss in dim_data.get("issues", []):
                            issues.append(f"[{dim_name}] {iss}")
                        for sug in dim_data.get("suggestions", []):
                            suggestions.append(f"[{dim_name}] {sug}")

                dim_scores = {k: v.get("score", 0) for k, v in dims.items() if isinstance(v, dict)}

                intel["diagnostic"] = {
                    "health_score": health,
                    "severity": severity,
                    "summary": summary_text or f"健康分{health}/100, 级别{severity}",
                    "vs_last": vs_last,
                    "dimension_scores": dim_scores,
                    "top_issues": issues[:8],
                    "top_suggestions": suggestions[:5],
                    "total_diagnostics": diag_status.get("stats", {}).get("total_diagnostics", 0),
                }
            except Exception as e:
                logger.warning(f"收集Diagnostic情报失败: {e}")

        if return_rate_agent:
            try:
                rra_status = return_rate_agent.get_status()
                diagnosis = rra_status.get("current_diagnosis", {})
                recs = rra_status.get("latest_recommendations", [])

                annualized = 0
                equity = self.module_metrics.get("equity", 100000)
                initial = 100000
                try:
                    from server.api import paper_trader as _pt
                    if _pt:
                        pt_status = _pt.get_status()
                        equity = pt_status.get("equity", equity)
                        initial = pt_status.get("initial_capital", initial)
                except Exception:
                    pass
                if equity > 0 and initial > 0:
                    return_pct = (equity - initial) / initial * 100
                    from datetime import datetime
                    try:
                        from server.titan_state import TitanState
                        start_str = TitanState.market_snapshot.get("start_date", None)
                        if start_str:
                            days = max(1, (datetime.now() - datetime.fromisoformat(start_str)).days)
                        else:
                            rra_stats = rra_status.get("stats", {})
                            days = max(1, rra_stats.get("days_running", rra_stats.get("total_reviews", 7)))
                    except Exception:
                        days = max(1, self.module_metrics.get("trading_days", 7))
                    if days > 0:
                        annualized = return_pct * (365 / days)

                aggression_hint = "moderate"
                if diagnosis.get("severity") == "critical":
                    aggression_hint = "conservative"
                elif diagnosis.get("severity") in ("healthy", "good"):
                    aggression_hint = "aggressive"

                recent_thinking = rra_status.get("recent_thinking", [])
                observations = []
                for t in recent_thinking[-2:]:
                    for obs in t.get("observations", [])[:3]:
                        observations.append(obs[:100] if isinstance(obs, str) else str(obs)[:100])

                intel["return_rate"] = {
                    "severity": diagnosis.get("severity", "unknown"),
                    "annualized_return": round(annualized, 2),
                    "current_return_pct": round((equity - initial) / initial * 100, 3) if initial > 0 else 0,
                    "drawdown_pct": diagnosis.get("drawdown_pct", 0),
                    "recent_win_rate": diagnosis.get("recent_win_rate", 0),
                    "recent_avg_pnl": diagnosis.get("recent_avg_pnl", 0),
                    "data_maturity": diagnosis.get("data_maturity", "unknown"),
                    "recommendations_count": len(recs),
                    "aggression_hint": aggression_hint,
                    "top_recommendations": [r.get("action", "") if isinstance(r, dict) else str(r) for r in recs[:3]],
                    "recent_observations": observations[:5],
                    "summary": f"年化{annualized:.1f}%, 级别{diagnosis.get('severity', '?')}, 回撤{diagnosis.get('drawdown_pct', 0):.2f}%"
                }
            except Exception as e:
                logger.warning(f"收集ReturnRate情报失败: {e}")

        if synapse:
            try:
                syn_status = synapse.get_status()
                strat_perf = syn_status.get("strategy_performance", {})
                regime_insights = syn_status.get("regime_insights", {})

                best_strat = None
                worst_strat = None
                best_wr = 0
                worst_wr = 100
                for s, perf in strat_perf.items():
                    wr = perf.get("win_rate", 50)
                    if perf.get("total_trades", 0) >= 5:
                        if wr > best_wr:
                            best_wr = wr
                            best_strat = s
                        if wr < worst_wr:
                            worst_wr = wr
                            worst_strat = s

                all_worst_assets = []
                for s, perf in strat_perf.items():
                    worst = perf.get("worst_assets", {})
                    for asset, count in worst.items():
                        if count >= 3:
                            all_worst_assets.append(asset)

                asset_insights_raw = syn_status.get("asset_insights", {})
                if not asset_insights_raw and hasattr(synapse, 'knowledge_base'):
                    asset_insights_raw = synapse.knowledge_base.get("asset_insights", {})
                asset_win_rates = {}
                for ak, ai_data in asset_insights_raw.items():
                    t = ai_data.get("total_trades", 0)
                    w = ai_data.get("wins", 0)
                    if t > 0:
                        asset_win_rates[ak] = {"win_rate": w / t, "total": t}

                intel["synapse"] = {
                    "best_strategy": best_strat,
                    "best_win_rate": best_wr,
                    "worst_strategy": worst_strat,
                    "worst_win_rate": worst_wr,
                    "worst_assets": list(set(all_worst_assets))[:10],
                    "asset_win_rates": asset_win_rates,
                    "regime_insights": {k: v.get("best_strategy") for k, v in regime_insights.items()},
                    "active_rules": syn_status.get("active_rules", 0),
                    "summary": f"最佳策略{best_strat}({best_wr:.0f}%), 最差{worst_strat}({worst_wr:.0f}%), 规则{syn_status.get('active_rules', 0)}条"
                }
            except Exception as e:
                logger.warning(f"收集Synapse情报失败: {e}")

        if agent_memory:
            try:
                mem_status = agent_memory.get_status()
                ban_rules = getattr(agent_memory, 'critic_ban_rules', [])
                banned_symbols = []
                for rule in ban_rules:
                    sym = rule.get("symbol", "") if isinstance(rule, dict) else ""
                    if sym:
                        banned_symbols.append(sym)

                intel["agent_memory"] = {
                    "ban_rules_count": len(ban_rules),
                    "banned_symbols": list(set(banned_symbols))[:15],
                    "patterns_tracked": mem_status.get("patterns_tracked", 0),
                    "recent_insights": [i.get("content", str(i))[:80] if isinstance(i, dict) else str(i)[:80] for i in mem_status.get("recent_insights", [])[:3]],
                    "summary": f"禁用规则{len(ban_rules)}条, 模式{mem_status.get('patterns_tracked', 0)}个"
                }
            except Exception as e:
                logger.warning(f"收集AgentMemory情报失败: {e}")

        if agi:
            try:
                agi_status = agi.get_status() if hasattr(agi, 'get_status') else {}
                cog = agi_status.get("cognitive_state", {})
                latest_ref = agi_status.get("latest_reflection", {})
                latest_jnl = agi_status.get("latest_journal", [])
                jnl_entries = latest_jnl if isinstance(latest_jnl, list) else ([latest_jnl] if latest_jnl else [])

                ref_findings = []
                ref_recs = []
                if isinstance(latest_ref, dict):
                    ref_findings = latest_ref.get("findings", [])
                    ref_recs = latest_ref.get("recommendations", [])

                jnl_insights = []
                for entry in jnl_entries[:3]:
                    if isinstance(entry, dict):
                        insight = entry.get("insight", "")
                        if insight:
                            jnl_insights.append(insight[:200])

                intel["agi"] = {
                    "cognitive_state": {
                        "confidence": cog.get("confidence_calibration", 0),
                        "risk_appetite": cog.get("risk_appetite", "unknown"),
                        "learning_rate": cog.get("learning_rate", 0),
                        "total_reflections": cog.get("total_reflections", 0),
                        "insight_count": cog.get("insight_count", 0),
                    },
                    "latest_findings": ref_findings[:5],
                    "latest_recommendations": ref_recs[:5],
                    "journal_insights": jnl_insights,
                    "decision_count": agi_status.get("decision_count", 0),
                    "reflection_count": agi_status.get("reflection_count", 0),
                    "summary": f"信心度{cog.get('confidence_calibration', 0):.0%}, 风险偏好{cog.get('risk_appetite', '?')}, 累计反思{cog.get('total_reflections', 0)}次, 洞察{cog.get('insight_count', 0)}个"
                }
            except Exception as e:
                logger.warning(f"收集AGI情报失败: {e}")

        self.intelligence_pool = intel
        logger.info(f"CTO情报汇总完成: {', '.join(intel.keys())}")
        return intel

    def generate_strategic_directives(self):
        intel = self.intelligence_pool
        m = self.module_metrics
        directives = dict(self.strategic_directives)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        old_blacklist = set(directives.get("asset_blacklist", []))
        old_aggression = directives.get("aggression_mode", "moderate")
        old_min_score = directives.get("min_signal_score", 70)
        old_max_pos = directives.get("max_concurrent_positions", 8)

        blacklist = set(old_blacklist)

        reviewer_intel = intel.get("reviewer", {})
        synapse_intel = intel.get("synapse", {})
        memory_intel = intel.get("agent_memory", {})

        asset_win_rates = synapse_intel.get("asset_win_rates", {})
        self._cached_asset_win_rates = asset_win_rates
        if not asset_win_rates:
            logger.warning("[CTO] 无资产胜率数据, 封禁门控将阻止所有reviewer/synapse封禁")

        for sym in reviewer_intel.get("recent_losing_symbols", []):
            if not sym:
                continue
            stats = asset_win_rates.get(sym)
            if stats and (stats["win_rate"] >= 0.30 or stats["total"] < 3):
                logger.info(f"[CTO] 拒绝封禁{sym}: 胜率{stats['win_rate']:.0%}({stats['total']}笔), 不满足封禁条件(需<30%且≥3笔)")
                continue
            if not stats:
                logger.warning(f"[CTO] {sym}无历史交易数据, 跳过reviewer封禁")
                continue
            blacklist.add(sym)

        for sym in synapse_intel.get("worst_assets", []):
            if not sym:
                continue
            stats = asset_win_rates.get(sym)
            if stats and (stats["win_rate"] >= 0.30 or stats["total"] < 3):
                logger.info(f"[CTO] 拒绝Synapse封禁{sym}: 胜率{stats['win_rate']:.0%}({stats['total']}笔)")
                continue
            if not stats:
                logger.warning(f"[CTO] {sym}无历史交易数据, 跳过Synapse封禁")
                continue
            blacklist.add(sym)

        for sym in memory_intel.get("banned_symbols", []):
            if not sym:
                continue
            stats = asset_win_rates.get(sym)
            if stats and (stats["win_rate"] >= 0.30 or stats["total"] < 3):
                logger.info(f"[CTO] 拒绝Memory封禁{sym}: 胜率{stats['win_rate']:.0%}({stats['total']}笔)")
                continue
            if not stats:
                logger.warning(f"[CTO] {sym}无历史交易数据, 跳过Memory封禁")
                continue
            blacklist.add(sym)

        directives["asset_blacklist"] = list(blacklist)[:30]

        new_symbols = blacklist - old_blacklist
        removed_symbols = old_blacklist - blacklist
        for sym in new_symbols:
            sources = []
            if sym in reviewer_intel.get("recent_losing_symbols", []):
                sources.append("reviewer")
            if sym in synapse_intel.get("worst_assets", []):
                sources.append("synapse")
            if sym in memory_intel.get("banned_symbols", []):
                sources.append("memory")
            self._record_cto_decision("blacklist_add", sym, "", sym,
                                      f"来源: {','.join(sources)}")
        for sym in removed_symbols:
            self._record_cto_decision("blacklist_remove", sym, sym, "",
                                      "从黑名单移除")

        diag_intel = intel.get("diagnostic", {})
        rr_intel = intel.get("return_rate", {})

        health = diag_intel.get("health_score", 70)
        dd = m.get("drawdown_pct", 0)
        c_losses = m.get("consecutive_losses", 0)

        if dd >= 5 or (health < 25 and dd >= 2) or c_losses >= 8:
            directives["aggression_mode"] = "conservative"
        elif dd >= 3 or (health < 40 and dd >= 1) or c_losses >= 5:
            directives["aggression_mode"] = "moderate"
        elif rr_intel.get("aggression_hint") == "aggressive" and health >= 60 and dd < 1.5:
            directives["aggression_mode"] = "aggressive"
        else:
            directives["aggression_mode"] = "moderate"

        if directives["aggression_mode"] != old_aggression:
            self._record_cto_decision("aggression_change", "aggression_mode",
                                      old_aggression, directives["aggression_mode"],
                                      f"DD={dd:.1f}% health={health} 连亏={c_losses}")

        regime = m.get("regime", "unknown")
        regime_best = synapse_intel.get("regime_insights", {}).get(regime)
        if regime_best:
            directives["strategy_preference"] = regime_best
        elif synapse_intel.get("best_strategy"):
            directives["strategy_preference"] = synapse_intel["best_strategy"]
        else:
            directives["strategy_preference"] = "balanced"

        if health < 30:
            directives["max_concurrent_positions"] = 3
        elif health < 50:
            directives["max_concurrent_positions"] = 5
        elif dd >= 3:
            directives["max_concurrent_positions"] = 4
        else:
            directives["max_concurrent_positions"] = 8

        if directives["max_concurrent_positions"] != old_max_pos:
            self._record_cto_decision("max_positions_change", "max_concurrent_positions",
                                      old_max_pos, directives["max_concurrent_positions"],
                                      f"health={health} DD={dd:.1f}%")

        if c_losses >= 5 or dd >= 3:
            directives["min_signal_score"] = 78
        elif health < 50 and dd >= 1:
            directives["min_signal_score"] = 75
        else:
            directives["min_signal_score"] = 73

        if directives["min_signal_score"] != old_min_score:
            self._record_cto_decision("score_threshold_change", "min_signal_score",
                                      old_min_score, directives["min_signal_score"],
                                      f"连亏={c_losses} DD={dd:.1f}% health={health}")

        if synapse_intel.get("regime_insights"):
            for regime_key, best_strat in synapse_intel["regime_insights"].items():
                if best_strat and regime_key in directives["regime_strategy_map"]:
                    rsm = dict(directives["regime_strategy_map"][regime_key])
                    if best_strat in rsm:
                        boost = min(0.15, 0.5 - rsm[best_strat])
                        if boost > 0:
                            rsm[best_strat] += boost
                            others = [k for k in rsm if k != best_strat]
                            if others:
                                reduction = boost / len(others)
                                for o in others:
                                    rsm[o] = max(0.1, rsm[o] - reduction)
                            total = sum(rsm.values())
                            if total > 0:
                                rsm = {k: round(v/total, 3) for k, v in rsm.items()}
                            directives["regime_strategy_map"][regime_key] = rsm

        directives["directives_updated_at"] = now
        self.strategic_directives = directives

        logger.info(f"CTO战略指令更新: aggression={directives['aggression_mode']}, blacklist={len(directives['asset_blacklist'])}个, max_pos={directives['max_concurrent_positions']}")
        return directives

    def rule_based_coordination(self):
        m = self.module_metrics
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        size_mult = 1.0
        throttle = "normal"
        risk = "standard"
        reasons = []

        dd = m.get("drawdown_pct", 0)
        if dd >= 5:
            size_mult *= 0.3
            throttle = "emergency"
            risk = "critical"
            reasons.append(f"回撤{dd:.1f}%达警戒线, 紧急缩仓")
        elif dd >= 3:
            size_mult *= 0.5
            throttle = "reduced"
            risk = "elevated"
            reasons.append(f"回撤{dd:.1f}%, 降低仓位")
        elif dd >= 1.5:
            size_mult *= 0.75
            reasons.append(f"回撤{dd:.1f}%, 适度谨慎")

        c_losses = m.get("consecutive_losses", 0)
        if c_losses >= 8:
            size_mult *= 0.5
            throttle = "emergency" if throttle != "emergency" else throttle
            reasons.append(f"连亏{c_losses}笔, 紧急缩仓50%")
        elif c_losses >= 5:
            size_mult *= 0.6
            if throttle == "normal":
                throttle = "reduced"
            reasons.append(f"连亏{c_losses}笔, 降速缩仓40%")
        elif c_losses >= 3:
            size_mult *= 0.7
            reasons.append(f"连亏{c_losses}笔, 缩仓30%")
        elif c_losses >= 2:
            size_mult *= 0.85
            reasons.append(f"连亏{c_losses}笔, 适度缩仓")

        ml_acc = m.get("ml_accuracy", 0.5)
        if ml_acc >= 0.65:
            size_mult *= 1.15
            reasons.append(f"ML准确率{ml_acc*100:.0f}%优秀, 适度加仓")
        elif ml_acc < 0.4:
            size_mult *= 0.8
            reasons.append(f"ML准确率{ml_acc*100:.0f}%偏低, 减少依赖")

        if m.get("frozen_strategies", 0) >= 2:
            size_mult *= 0.5
            reasons.append(f"{m['frozen_strategies']}个策略冻结, 系统压力大")

        regime = m.get("regime", "unknown")
        if regime == "volatile":
            size_mult *= 0.7
            reasons.append("高波动市场, 降低暴露")
        elif regime == "trending":
            size_mult *= 1.1
            reasons.append("趋势明确, 可适度增仓")

        sq = m.get("signal_quality_avg", 0.5)
        if sq >= 0.7:
            size_mult *= 1.1
            reasons.append(f"信号质量{sq:.2f}高, 信号可信度增加")
        elif sq < 0.3:
            size_mult *= 0.7
            reasons.append(f"信号质量{sq:.2f}低, 信号可信度下降")

        size_mult = max(0.4, min(2.5, size_mult))

        rebalance = {}
        if regime == "trending":
            rebalance = {"trend": 0.45, "range": 0.25, "grid": 0.30}
        elif regime == "ranging":
            rebalance = {"trend": 0.20, "range": 0.35, "grid": 0.45}
        elif regime == "volatile":
            rebalance = {"trend": 0.35, "range": 0.30, "grid": 0.35}
        else:
            rebalance = {"trend": 0.35, "range": 0.30, "grid": 0.35}

        old_size_mult = self.recommendations.get("size_multiplier", 1.0)
        new_size_mult = round(size_mult, 3)

        self.recommendations = {
            "size_multiplier": new_size_mult,
            "throttle_level": throttle,
            "regime_bias": regime,
            "risk_level": risk,
            "rebalance_advice": rebalance,
            "reasoning": "; ".join(reasons) if reasons else "系统正常运行, 维持标准参数",
        }

        if abs(new_size_mult - old_size_mult) >= 0.05:
            self._record_cto_decision("size_multiplier_change", "size_multiplier(rule)",
                                      old_size_mult, new_size_mult,
                                      "; ".join(reasons) if reasons else "正常")

        self.coordination_log.append({
            "time": now,
            "type": "rule_based",
            "size_mult": new_size_mult,
            "throttle": throttle,
            "risk": risk,
            "reasons": reasons,
        })
        if len(self.coordination_log) > 50:
            self.coordination_log = self.coordination_log[-50:]

        self._consume_learning_journal()

        self.stats["total_coordinations"] += 1
        self.save()

        return self.recommendations

    def _consume_learning_journal(self):
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id, source, content, priority
                    FROM learning_journal
                    WHERE consumed_by_cto = false
                    ORDER BY priority DESC, created_at DESC
                    LIMIT 50
                """)
                unread = cur.fetchall()
                if not unread:
                    return

                ids = [r['id'] for r in unread]

                journal_insights = []
                for r in unread:
                    journal_insights.append(f"[{r['source']}|P{r['priority']}] {str(r['content'])[:200]}")

                self.recommendations["journal_digest"] = journal_insights[:10]

                placeholders = ','.join(['%s'] * len(ids))
                cur.execute(f"""
                    UPDATE learning_journal
                    SET consumed_by_cto = true
                    WHERE id IN ({placeholders})
                """, ids)
                conn.commit()

                logger.info(f"CTO消费学习日志: {len(ids)}条标记已读")
        except Exception as e:
            logger.warning(f"CTO学习日志消费失败(非致命): {e}")

    def reflect(self):
        if len(self.ai_analysis_history) < 2:
            return None

        current = self.module_metrics
        equity_now = current.get("equity", 100000)
        dd_now = current.get("drawdown_pct", 0)
        pnl_now = current.get("total_pnl", 0)

        scores = []
        for i in range(len(self.ai_analysis_history) - 1):
            past = self.ai_analysis_history[i]
            nxt = self.ai_analysis_history[i + 1]

            eq_at_advice = past.get("equity_snapshot", 100000)
            eq_at_next = nxt.get("equity_snapshot", 100000)
            pnl_delta = eq_at_next - eq_at_advice

            pr = past.get("ai_result", {})
            advised_bias = pr.get("regime_bias", "neutral")
            advised_size = pr.get("size_multiplier", 1.0)

            if advised_bias == "defensive" and pnl_delta >= 0:
                scores.append(0.7)
            elif advised_bias == "defensive" and pnl_delta < -50:
                scores.append(0.3)
            elif advised_bias == "aggressive" and pnl_delta > 0:
                scores.append(1.0)
            elif advised_bias == "aggressive" and pnl_delta < 0:
                scores.append(0.0)
            elif advised_bias == "neutral" and abs(pnl_delta) < 100:
                scores.append(0.6)
            else:
                scores.append(0.5)

        recent_scores = scores[-5:] if scores else [0.5]
        accuracy = sum(recent_scores) / len(recent_scores)
        self.stats["ai_accuracy_score"] = round(accuracy, 3)

        lesson_lines = []
        if accuracy < 0.4:
            lesson_lines.append("过去建议效果不佳,需调整判断框架: 可能对市场环境误判")
        elif accuracy > 0.7:
            lesson_lines.append("过去建议效果良好,保持当前判断逻辑")

        if dd_now > 3 and any(p.get("ai_result", {}).get("regime_bias") == "aggressive" for p in self.ai_analysis_history[-3:]):
            lesson_lines.append("近期建议偏激进但回撤加大,反思: 应更早识别风险信号")
        if pnl_now > 0 and all(p.get("ai_result", {}).get("regime_bias") == "defensive" for p in self.ai_analysis_history[-3:]):
            lesson_lines.append("持续防守但盈利中,反思: 可能过于保守,错失更大收益")

        if len(scores) >= 3 and all(s < 0.3 for s in scores[-3:]):
            lesson_lines.append("连续3次建议失准,反思: 当前市场可能进入未知模式,建议减少干预保持中性")

        c_losses = current.get("consecutive_losses", 0)
        if c_losses >= 5:
            lesson_lines.append(f"连亏{c_losses}笔,反思: 检查信号质量或市场环境是否发生结构性变化")

        cap_util = current.get("capital_utilization", 0)
        if cap_util < 0.05:
            lesson_lines.append(f"资金利用率仅{cap_util*100:.1f}%,反思: 入场门槛可能过高导致机会流失")
        elif cap_util > 0.6:
            lesson_lines.append(f"资金利用率{cap_util*100:.1f}%过高,反思: 是否过度暴露风险")

        recent_sizes = [p.get("blended_mult", 1.0) for p in self.ai_analysis_history[-5:]]
        if recent_sizes and max(recent_sizes) - min(recent_sizes) > 0.8:
            lesson_lines.append("仓位乘数波动过大,反思: 建议保持更稳定的判断,避免频繁大幅调整")

        reflection_entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "accuracy_score": round(accuracy, 3),
            "lessons": lesson_lines,
            "per_advice_scores": [round(s, 2) for s in recent_scores],
            "equity": round(equity_now, 2),
            "pnl": round(pnl_now, 2),
            "drawdown": round(dd_now, 2),
        }

        self.reflection_log.append(reflection_entry)
        if len(self.reflection_log) > 10:
            self.reflection_log = self.reflection_log[-10:]

        self.stats["reflection_count"] = self.stats.get("reflection_count", 0) + 1
        self.save()

        logger.info(f"AI CTO反思完成: 准确率{accuracy:.0%}, 教训{len(lesson_lines)}条")
        return reflection_entry

    def _build_system_prompt(self):
        return """你是"神盾计划：不死量化"的首席技术官(CTO)兼AI协调器。

## 你的身份
你是一套百亿级加密货币量化基金的中枢大脑。你不是普通的聊天AI——你是实时运行在交易系统内部的决策引擎,你的每一个输出都会直接影响真实的仓位大小、策略分配和风控参数。请以基金经理的专业视角思考。

## 系统架构概览
本系统名为"神盾计划：不死量化"(Shield Plan: Immortal Quant),核心理念是"先活下来,再赚钱"。

### 三大交易策略
1. **趋势跟踪(Trend)**: ADX>25时启用,顺势做多/做空,依赖MACD+RSI+布林带+一目均衡
2. **区间收割(Range)**: ADX<20时启用,在震荡区间低买高卖,依赖支撑阻力+斐波那契
3. **神经网格(Grid)**: Monte Carlo GBM预测边界,自动几何/等差间距选择,追踪网格模式

### 信号生成链路
原始数据 → TitanMath(44维技术指标) → TitanBrain(双策略引擎) → ML集成模型(RF+LGBM+LR)打分
→ SignalQuality(信号质量校准) → CapitalSizer(仓位计算) → RiskMatrix(三线风控验证) → 下单

### ML模型
- 集成分类器: RandomForest + LightGBM + LogisticRegression
- 44维特征: OBV, Stochastic, Ichimoku, Donchian, Keltner等
- 三重屏障标签: TP/SL模拟生成训练标签
- 概率校准: 3-class Isotonic Regression

### 关键子系统
- **UnifiedDecision(统一决策器)**: 综合市场环境、你的建议、宪法状态、FNG、持仓数等,决定开启哪些交易模式和入场门槛
- **CapitalSizer(资金定量器)**: 整合Kelly/ATR、信号质量、ML置信度、环境、风险预算、你的乘数到单一仓位管线
- **PaperTrader(模拟交易)**: 自动TP/SL执行,追踪止盈,时间止损,动态资金管理
- **RiskBudget(风险预算)**: 按策略分配资金,单策略回撤超限自动冻结
- **Dispatcher(策略调度)**: 检测市场环境自动切换策略,动态分配资金
- **Synapse(突触学习)**: 跨策略协作知识总线,广播交易结果生成规则
- **ReturnTargetEngine(收益引擎)**: 追踪年化收益vs12%目标,低于目标时自动提高进攻性
- **Constitution(宪法)**: 永久回撤熔断器,日内暂停,亏损触发进化

### 三线风控体系
1. **交易级**: 单笔风险≤2%资金,信号质量过滤,ML置信度过滤
2. **组合级**: 相关性分析,VaR计算,净暴露控制,最大持仓限制
3. **系统级**: 最大回撤熔断8%,日亏限额,连亏降速,BTC崩盘保护

## 你的职责和权限

### 你直接控制的参数
1. **size_multiplier**: 全局仓位乘数(0.4-2.5),直接乘到CapitalSizer的最终仓位上
2. **rebalance_advice**: 三策略资金分配比例,影响RiskBudget的再平衡
3. **evolution_tips**: 系统优化建议,展示在仪表盘上供基金经理参考

### 你的建议如何被使用
- 你的size_multiplier与规则引擎60/40混合(规则60%,你40%)
- throttle_level和risk_level由规则引擎硬性控制(连亏≥8=emergency,≥5=reduced),你的值仅供参考
- rebalance_advice直接传给RiskBudget做再平衡
- 你每3次协调被调用1次(其余2次用规则引擎)

## 核心目标
- 年化收益目标: ≥12%(无上限,不刹车)
- 最大回撤: <8%
- Calmar比率: >1.0
- 胜率目标: >45%
- 理念: 小仓高频,严格止损,让利润奔跑

## 决策原则
1. **活下来最重要**: 回撤>3%时必须收缩,回撤>5%时大幅收缩
2. **顺势而为**: trending环境加大趋势仓位,ranging环境加大网格仓位
3. **连亏要减速不要停**: 连亏5-7笔用reduced(缩仓但保持交易),≥8笔才emergency
4. **资金利用率意识**: <10%说明过于保守,应适度放宽;>60%说明过于激进
5. **ML信号质量联动**: ML置信度60-70%是最可信区间(实测60%准确率),80+是警示信号(实测16.7%准确率),不要把高置信度当加仓理由
6. **情绪需要趋势确认**: FNG极低时(≤15)不能单独作为做多信号。
   必须结合BTC宏观趋势：
   - FNG≤15 + BTC上涨(btc_macro_trend=bullish) → 可以考虑逆向做多，小仓位
   - FNG≤15 + BTC下跌(btc_macro_trend=bearish) → 这是做空机会，不是做多
   单独使用FNG逆向策略已被实盘数据证明有害（导致29.2%方向准确率）
7. **网格是稳定器**: 震荡市网格应该是主力,趋势市网格辅助

## 新增职责：AI持仓顾问管理

### 持仓顾问系统(TitanPositionAdvisor)
系统新增了"AI持仓顾问"模块——为每个活跃持仓配备了一个虚拟操盘手。你作为CTO需要了解：

1. **持仓顾问的工作方式**:
   - 每个扫描周期自动评估所有活跃持仓
   - 综合考虑：盈亏状态、K线形态预警、波动率变化、BTC关联风险、持仓时长
   - 输出操作建议：hold(持有)、add(加仓)、reduce(减仓)、close(平仓)、tighten_sl(收紧止损)
   - 每个建议附带推理链条(reasoning_chain)，展示"为什么这么决定"

2. **波动率自适应止损**:
   - 系统现在根据实时ATR与入场ATR的比值，自动调整止损和止盈
   - 5个级别：极端波动(≥2.5x)、高波动(≥1.8x)、波动升高(≥1.3x)、低波动(≤0.65x)、极低波动(≤0.4x)
   - 市场环境感知：volatile环境放宽止损、trending环境适度收紧、ranging环境更紧
   - 高波动时同步扩大止盈目标，低波动时收缩止盈目标
   - 盈利保护：盈利>3%且波动率飙升时，自动将止损移至保本线

3. **你的协调职责**:
   - 你的size_multiplier会影响开仓大小，但持仓顾问负责持仓期间的管理
   - 当持仓顾问建议"close"且置信度<15时，守卫系统会自动执行平仓
   - 你的regime判断会影响波动率自适应的调整幅度
   - 在你的reasoning中，请关注持仓顾问的整体建议分布——如果大部分持仓被建议"reduce"或"close"，说明市场环境可能需要你全局性降低仓位

## 宏观趋势优先级（2026-02-24更新）

生成size_multiplier和strategy_preference时，btc_macro_trend是最高优先级输入：

btc_macro_trend = bearish时：
- size_multiplier上限：0.80（不建议超过）
- strategy_preference：balanced或defensive
- 禁止：激进做多策略

btc_macro_trend = bullish时：
- size_multiplier可以正常范围
- strategy_preference：根据胜率正常判断

ML置信度使用规则：
- ml_confidence > 80：这是警示，建议保守
- ml_confidence 60-70：这是可信信号，可以参考
- 不要把高ML置信度作为放大size_multiplier的理由

## 反思与成长机制
你具备自我反思能力。每次被调用前,系统会自动评估你过去建议的效果:
- 如果你建议"defensive"但回撤很小,说明判断正确
- 如果你建议"aggressive"但回撤加大,说明过于激进
- 系统会计算你的"历史准确率"并生成教训摘要
- 你的反思报告会出现在下方的"自我反思报告"中
- **请认真阅读反思教训,在本次决策中吸取经验**: 如果过去偏保守就适度放开,如果过去偏激进就适度收紧
- 这是你不断成长的核心机制——每一次决策都是学习的机会

## CTO当前任务优先级（2026-02-26更新）

### 你的决策正在被追踪
从今天起，你的所有决策（黑名单/激进度/仓位乘数）
都记录在cto_decisions表，并在24-96小时后自动验证准确性。
这是好事——你的决策质量会随时间积累变得可量化。

做决策时请记录清晰的reason，方便事后归因分析。

### 阶段零观察期（最高优先级）
系统处于信号层修复后的观察期。
- 不推荐任何激进参数调整
- 不推荐扩大标的范围
- 重点观察：空单占比是否提升、方向准确率是否改善
- size_multiplier建议范围：0.65-0.90

### ReturnTargetEngine已修复
原来在回撤期会给你激进度建议的bug已修复。
现在回撤期间ReturnTargetEngine会自动切换为保守模式。
你的size_multiplier不应与ReturnTargetEngine的输出叠加放大。

### MM模型状态
当前MM模型R²=-0.001，已被质量门控跳过。
仓位计算完全基于规则（Kelly+ATR+9维分组加权）。
这是更健康的状态，直到MM模型重新训练到R²>0.15。

### 决策质量自检
每次生成指令时，自问：
1. 这个决策在24小时后能被验证对错吗？
2. 我的黑名单里有没有因为小样本被误封的标的？
3. 当前size_multiplier和市场状态是否一致？

## 新增信息来源（2026-03-10三脑升级）

你现在有以下新数据源，请在制定战略指令时参考：

1. debate_records表：每个信号的多智能体辩论结果。
   当辩论裁决和你的判断冲突时，优先参考辩论结果，
   因为辩论系统综合了4个维度（多头律师/空头律师/风险官/历史学家）。

2. evolution_proposals表：进化脑发现的系统性问题和建议。
   status='pending'的建议需要你评估是否采纳。
   你可以在strategic_directives里加入evolution_adopted_proposals字段记录采纳的建议。

3. counterfactuals表：最近交易的反事实分析。
   如果sl_too_tight出现频率>30%：建议在指令里加入"SL适当放宽"。
   如果trailing_sl_too_late出现频率>30%：建议加入"追踪止损触发提前"。

4. memory_strengths表：高强度记忆（strength>0.7）是系统最可靠的历史经验。
   在制定资产偏好时优先参考高强度记忆。

你的核心职责更新：不只是"制定交易策略"，
而是"协调三脑系统的输出，形成统一的战略指令"。"""

    def _build_user_prompt(self, m):
        recent_ai = ""
        if self.ai_analysis_history:
            last = self.ai_analysis_history[-1]
            recent_ai = f"""
上次AI分析:
- 时间: {last.get('time', 'N/A')}
- 建议仓位乘数: {last.get('blended_mult', 'N/A')}
- 置信度: {last.get('confidence', 'N/A')}
- 判断: {last.get('ai_result', {}).get('reasoning', 'N/A')[:100]}
- 市场展望: {last.get('market_outlook', 'N/A')}"""

        reflection_section = ""
        if self.reflection_log:
            latest_ref = self.reflection_log[-1]
            lessons = latest_ref.get("lessons", [])
            reflection_section = f"""

🪞 自我反思报告 (CTO成长记录):
- 反思时间: {latest_ref.get('time', 'N/A')}
- 历史建议准确率: {latest_ref.get('accuracy_score', 0.5)*100:.0f}%
- 反思时权益: ${latest_ref.get('equity', 0):.2f}, 盈亏: ${latest_ref.get('pnl', 0):.2f}
- 反思时回撤: {latest_ref.get('drawdown', 0):.2f}%
- 总结教训:"""
            if lessons:
                for lesson in lessons[:5]:
                    reflection_section += f"\n  ⚠️ {lesson}"
            else:
                reflection_section += "\n  ✅ 暂无明显偏差"
            reflection_section += f"\n- 总反思次数: {self.stats.get('reflection_count', 0)}次"
            reflection_section += "\n\n请基于以上反思教训调整你本次的判断。如果过去偏保守就适度放开,如果过去偏激进就适度收紧。"

        intel_section = ""
        if self.intelligence_pool:
            intel_lines = ["\n📡 AI模块情报汇总 (各部门最新报告):"]
            for source, data in self.intelligence_pool.items():
                summary = data.get("summary", "无摘要")
                intel_lines.append(f"  - {source}: {summary}")
            intel_section = "\n".join(intel_lines)

        strategy_budgets_str = ""
        budgets = m.get("strategy_budgets", {})
        if budgets:
            lines = []
            for k, v in budgets.items():
                status = "🔒冻结" if v.get("frozen") else "✅正常"
                lines.append(f"  - {k}: 可用${v.get('available', 0):.0f}, 回撤{v.get('drawdown', 0):.1f}%, {status}")
            strategy_budgets_str = "\n".join(lines)

        recent_coord = ""
        if self.coordination_log:
            last_rule = self.coordination_log[-1]
            reasons = last_rule.get("reasons", [])
            recent_coord = f"""
上次规则引擎判断:
- 仓位乘数: {last_rule.get('size_mult', 'N/A')}
- 节流级别: {last_rule.get('throttle', 'N/A')}
- 风险级别: {last_rule.get('risk', 'N/A')}
- 原因: {'、'.join(reasons[:4]) if reasons else '无'}"""

        return f"""当前时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

═══════════ 系统实时仪表盘 ═══════════

📊 交易表现:
- 总交易: {m.get('total_trades', 0)}笔
- 账户权益: ${m.get('equity', 100000):.2f}
- 累计盈亏: ${m.get('total_pnl', 0):.2f}
- 日内盈亏: ${m['daily_pnl']:.2f}
- 当前持仓: {m.get('open_positions', 0)}个
- 连胜: {m['consecutive_wins']}笔 | 连亏: {m['consecutive_losses']}笔

📈 模型性能:
- ML准确率: {m['ml_accuracy']*100:.1f}%
- ML胜率: {m['ml_win_rate']*100:.1f}%
- 规则胜率: {m['rule_win_rate']*100:.1f}%
- ML权重: {m.get('ml_weight', 0.5):.2f} | 规则权重: {m.get('rule_weight', 0.5):.2f}
- 信号质量均值: {m['signal_quality_avg']:.2f}

🛡️ 风控状态:
- 当前回撤: {m['drawdown_pct']:.2f}% (历史最大: {m.get('max_drawdown_ever', 0):.2f}%, 上限8%)
- 最大回撤(PT): {m.get('max_dd_pct', 0):.2f}%
- 资金使用率: {m['capital_utilization']*100:.1f}%
- 冻结策略数: {m['frozen_strategies']}

📊 华尔街绩效指标:
- Sharpe Ratio: {m.get('ws_sharpe', 0)} (目标>1.0)
- Sortino Ratio: {m.get('ws_sortino', 0)} (目标>1.5)
- Calmar Ratio: {m.get('ws_calmar', 0)} (目标>1.0)
- Profit Factor: {m.get('ws_profit_factor', 0)} (目标>1.5)
- 年化收益率: {m.get('ws_annualized_return', 0):+.1f}% (目标≥12%)
- 年化波动率: {m.get('ws_volatility', 0):.1f}%
- 最大回撤: {m.get('ws_max_dd', 0):.1f}% (上限8%)
- 盈亏比: {m.get('ws_risk_reward', 0)} (目标>1.5)
- 每笔期望值: {m.get('ws_expectancy', 0):+.3f}%
- 最大连胜/连亏: {m.get('ws_max_cw', 0)}/{m.get('ws_max_cl', 0)}

🎯 市场与策略:
- 市场环境: {m['regime']}
- 活跃策略: {', '.join(m.get('active_strategies', ['unknown']))}
- 网格状态: {m.get('grid_active', 0)}个活跃, 胜率{m.get('grid_win_rate', 0)*100:.0f}%
- Synapse规则: {m['synapse_rule_count']}条

💰 策略预算:
{strategy_budgets_str if strategy_budgets_str else '  数据加载中...'}

🤖 持仓顾问状态:
- 活跃持仓数: {m.get('open_positions', 0)}
- 持仓顾问建议分布: {m.get('advisor_actions', '暂无数据')}
- 波动率自适应: 已启用(5级自适应,regime感知)
{recent_coord}
{recent_ai}
{reflection_section}
{intel_section}

═══════════ 请给出你的决策 ═══════════

基于以上实时数据,请以CTO身份分析系统状态,返回JSON:
{{
  "size_multiplier": 1.0,
  "risk_level": "low/standard/elevated/critical",
  "regime_bias": "aggressive/neutral/defensive",
  "rebalance_advice": {{"trend": 0.4, "range": 0.3, "grid": 0.3}},
  "reasoning": "150字内深度分析(中文): 先诊断当前最大风险点,再给出调仓理由",
  "confidence": 0.8,
  "evolution_tips": ["具体可执行的优化建议1", "建议2", "建议3"],
  "market_outlook": "对当前市场环境的30字判断",
  "priority_action": "当前最紧急应做的一件事",
  "asset_blacklist_add": ["如有需要新增黑名单的币种"],
  "asset_whitelist_add": ["如有需要优先交易的币种"],
  "aggression_mode": "conservative/moderate/aggressive",
  "max_concurrent_positions": 8,
  "strategy_preference": "trend/range/grid/balanced"
}}

决策约束:
- size_multiplier范围0.4-2.5 (正常区间0.7-1.3, 极端情况才超出)
- rebalance三项必须总和=1.0
- reasoning要有因果逻辑,不要空泛描述
- evolution_tips要具体可执行,不要泛泛而谈
- 如果系统表现健康(胜率>50%,回撤<2%,资金利用率10-40%),保持稳定不要频繁调整"""

    def ai_coordination(self):
        m = self.module_metrics

        last_ai_time = self.stats.get("last_ai_analysis", "")
        if last_ai_time:
            try:
                last_dt = datetime.strptime(last_ai_time, "%Y-%m-%d %H:%M:%S")
                elapsed = (datetime.now() - last_dt).total_seconds()
                if elapsed < 600:
                    logger.info(f"AI协调冷却中: 距上次{elapsed:.0f}秒 < 600秒最小间隔")
                    return {"status": "cooldown", "recommendations": self.recommendations}
            except Exception:
                pass

        try:
            self.reflect()
        except Exception as ref_err:
            logger.warning(f"AI反思异常(非致命): {ref_err}")

        try:
            from server.titan_llm_client import chat_json

            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(m)

            result = chat_json(
                module="cto_coordination",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2000,
            )
            if not result:
                logger.warning("AI协调返回空内容,使用规则兜底")
                return {"status": "fallback", "recommendations": self.recommendations}

            if result.get("confidence", 0) >= 0.5:
                ai_size = max(0.4, min(2.5, result.get("size_multiplier", 1.0)))
                rule_size = self.recommendations.get("size_multiplier", 1.0)
                blended = round(rule_size * 0.6 + ai_size * 0.4, 3)

                if abs(blended - rule_size) >= 0.05:
                    self._record_cto_decision("size_multiplier_change", "size_multiplier(ai_blend)",
                                              rule_size, blended,
                                              f"AI建议={ai_size} 规则={rule_size} 混合60/40 confidence={result.get('confidence',0)}")

                self.recommendations["size_multiplier"] = blended
                self.recommendations["reasoning"] = result.get("reasoning", "")
                self.recommendations["evolution_tips"] = result.get("evolution_tips", [])
                self.recommendations["market_outlook"] = result.get("market_outlook", "")
                self.recommendations["priority_action"] = result.get("priority_action", "")

                ai_blacklist = result.get("asset_blacklist_add", [])
                if isinstance(ai_blacklist, list) and ai_blacklist:
                    current_bl = set(self.strategic_directives.get("asset_blacklist", []))
                    synapse_intel_for_ai = intel.get("synapse", {}) if hasattr(self, '_last_intel') else {}
                    ai_asset_wr = synapse_intel_for_ai.get("asset_win_rates", {})
                    if not ai_asset_wr:
                        ai_asset_wr = getattr(self, '_cached_asset_win_rates', {})
                    for sym in ai_blacklist:
                        if not sym or sym in current_bl:
                            continue
                        stats = ai_asset_wr.get(sym)
                        if stats and (stats["win_rate"] >= 0.30 or stats["total"] < 3):
                            logger.info(f"[CTO] 拒绝AI封禁{sym}: 胜率{stats['win_rate']:.0%}({stats['total']}笔)")
                            continue
                        if not stats:
                            logger.warning(f"[CTO] {sym}无历史交易数据, 跳过AI封禁")
                            continue
                        current_bl.add(sym)
                        self._record_cto_decision("blacklist_add", sym, "", sym,
                                                  f"AI建议拉黑 confidence={result.get('confidence',0)}")
                    self.strategic_directives["asset_blacklist"] = list(current_bl)[:30]

                ai_whitelist = result.get("asset_whitelist_add", [])
                if isinstance(ai_whitelist, list):
                    self.strategic_directives["asset_whitelist"] = ai_whitelist[:20]

                ai_aggression = result.get("aggression_mode")
                if ai_aggression in ("conservative", "moderate", "aggressive"):
                    old_agg = self.strategic_directives.get("aggression_mode", "moderate")
                    dd_now = self.module_metrics.get("drawdown_pct", 0)
                    cl_now = self.module_metrics.get("consecutive_losses", 0)
                    if ai_aggression == "conservative" and dd_now < 2 and cl_now < 5:
                        ai_aggression = "moderate"
                        logger.info(f"[CTO] AI建议conservative但DD={dd_now}%<2%且连亏{cl_now}<5, 覆盖为moderate")
                    if ai_aggression != old_agg:
                        self._record_cto_decision("aggression_change", "aggression_mode(ai)",
                                                  old_agg, ai_aggression,
                                                  f"AI建议 confidence={result.get('confidence',0)} DD={dd_now}%")
                    self.strategic_directives["aggression_mode"] = ai_aggression

                ai_max_pos = result.get("max_concurrent_positions")
                if isinstance(ai_max_pos, (int, float)) and 1 <= ai_max_pos <= 15:
                    old_max = self.strategic_directives.get("max_concurrent_positions", 8)
                    if int(ai_max_pos) != old_max:
                        self._record_cto_decision("max_positions_change", "max_positions(ai)",
                                                  old_max, int(ai_max_pos),
                                                  f"AI建议 confidence={result.get('confidence',0)}")
                    self.strategic_directives["max_concurrent_positions"] = int(ai_max_pos)

                ai_strat_pref = result.get("strategy_preference")
                if ai_strat_pref in ("trend", "range", "grid", "balanced"):
                    self.strategic_directives["strategy_preference"] = ai_strat_pref

                self.strategic_directives["directives_updated_at"] = now

                rebalance = result.get("rebalance_advice", {})
                if rebalance and isinstance(rebalance, dict):
                    total = sum(v for v in rebalance.values() if isinstance(v, (int, float)))
                    if abs(total - 1.0) < 0.1 and total > 0:
                        normalized = {k: round(v/total, 3) for k, v in rebalance.items() if isinstance(v, (int, float))}
                        self.recommendations["rebalance_advice"] = normalized

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.ai_analysis_history.append({
                "time": now,
                "ai_result": result,
                "blended_mult": self.recommendations["size_multiplier"],
                "confidence": result.get("confidence", 0),
                "market_outlook": result.get("market_outlook", ""),
                "priority_action": result.get("priority_action", ""),
                "equity_snapshot": round(m.get("equity", 100000), 2),
                "pnl_snapshot": round(m.get("total_pnl", 0), 2),
                "drawdown_snapshot": round(m.get("drawdown_pct", 0), 2),
            })
            if len(self.ai_analysis_history) > 20:
                self.ai_analysis_history = self.ai_analysis_history[-20:]

            self.stats["total_ai_analyses"] += 1
            self.stats["last_ai_analysis"] = now
            self.save()

            logger.info(f"AI协调完成: size_mult={self.recommendations['size_multiplier']}, "
                        f"reasoning={self.recommendations.get('reasoning', '')[:50]}")
            return {"status": "ok", "recommendations": self.recommendations, "ai_result": result}

        except Exception as e:
            logger.warning(f"AI协调异常,使用规则兜底: {e}")
            return {"status": "fallback", "recommendations": self.recommendations, "error": str(e)}

    def coordinate(self, adaptive_weights=None, risk_budget=None, dispatcher=None,
                   synapse=None, signal_quality=None, paper_trader=None, feedback=None,
                   grid_engine=None, use_ai=True,
                   reviewer=None, diagnostic=None, return_rate_agent=None, agent_memory=None, agi=None):
        self.collect_metrics(adaptive_weights, risk_budget, dispatcher,
                           synapse, signal_quality, paper_trader, feedback,
                           grid_engine=grid_engine)

        self.collect_intelligence(
            reviewer=reviewer,
            diagnostic=diagnostic,
            return_rate_agent=return_rate_agent,
            synapse=synapse,
            agent_memory=agent_memory,
            agi=agi,
        )

        self.generate_strategic_directives()

        self.rule_based_coordination()

        if use_ai and self.stats["total_coordinations"] % 2 == 0:
            return self.ai_coordination()

        return {"status": "ok", "recommendations": self.recommendations}

    def get_size_multiplier(self):
        return self.recommendations.get("size_multiplier", 1.0)

    def get_rebalance_advice(self):
        return self.recommendations.get("rebalance_advice", {})

    def get_status(self):
        return {
            "module_metrics": self.module_metrics,
            "recommendations": self.recommendations,
            "stats": self.stats,
            "recent_coordinations": self.coordination_log[-5:],
            "recent_ai_analyses": self.ai_analysis_history[-3:],
            "market_outlook": self.recommendations.get("market_outlook", ""),
            "priority_action": self.recommendations.get("priority_action", ""),
            "reflection": self.reflection_log[-1] if self.reflection_log else None,
            "ai_accuracy_score": self.stats.get("ai_accuracy_score", 0.5),
            "strategic_directives": self.strategic_directives,
            "intelligence_summary": dict(self.intelligence_pool) if self.intelligence_pool else {},
        }

    def get_strategic_directives(self):
        return self.strategic_directives

    def _refresh_all_data(self):
        metrics_ok = False
        intel_ok = False
        try:
            from server.api import (paper_trader, dispatcher, risk_budget,
                                    signal_quality, grid_engine, synapse,
                                    agent_memory)
            from server.titan_ml import adaptive_weights as adaptive_weight_manager
            self.collect_metrics(
                adaptive_weights=adaptive_weight_manager,
                risk_budget=risk_budget,
                dispatcher=dispatcher,
                synapse=synapse,
                signal_quality=signal_quality,
                paper_trader=paper_trader,
                grid_engine=grid_engine,
            )
            metrics_ok = True
        except Exception as e:
            logger.warning(f"报告metrics刷新失败: {e}")

        try:
            from server.api import agent_memory, synapse
            _reviewer = None
            _diagnostic = None
            _rra = None
            _agi = None
            try:
                from server.titan_ai_reviewer import ai_reviewer
                _reviewer = ai_reviewer
            except Exception:
                pass
            try:
                from server.titan_ai_diagnostic import ai_diagnostic
                _diagnostic = ai_diagnostic
            except Exception:
                pass
            try:
                from server.titan_return_rate_agent import return_rate_agent
                _rra = return_rate_agent
            except Exception:
                pass
            try:
                from server.titan_agi import titan_agi
                _agi = titan_agi
            except Exception:
                pass
            self.collect_intelligence(
                reviewer=_reviewer,
                diagnostic=_diagnostic,
                return_rate_agent=_rra,
                synapse=synapse,
                agent_memory=agent_memory,
                agi=_agi,
            )
            intel_ok = True
        except Exception as e:
            logger.warning(f"报告intelligence刷新失败: {e}")

        if metrics_ok and intel_ok:
            logger.info("报告数据全量刷新完成")
        elif metrics_ok:
            logger.info("报告数据部分刷新: metrics成功, intelligence失败")
        elif intel_ok:
            logger.info("报告数据部分刷新: intelligence成功, metrics失败")
        else:
            logger.warning("报告数据刷新全部失败, 将使用缓存数据")

    def generate_department_briefings(self):
        self._refresh_all_data()

        intel = dict(self.intelligence_pool) if self.intelligence_pool else {}

        if "agi" not in intel:
            try:
                from server.titan_agi import titan_agi
                agi_status = titan_agi.get_status()
                cog = agi_status.get("cognitive_state", {})
                latest_ref = agi_status.get("latest_reflection", {})
                latest_jnl = agi_status.get("latest_journal", [])
                jnl_entries = latest_jnl if isinstance(latest_jnl, list) else ([latest_jnl] if latest_jnl else [])
                ref_findings = latest_ref.get("findings", []) if isinstance(latest_ref, dict) else []
                jnl_insights = [e.get("insight", "")[:200] for e in jnl_entries[:3] if isinstance(e, dict) and e.get("insight")]
                intel["agi"] = {
                    "cognitive_state": {"confidence": cog.get("confidence_calibration", 0), "risk_appetite": cog.get("risk_appetite", "unknown"), "total_reflections": cog.get("total_reflections", 0), "insight_count": cog.get("insight_count", 0)},
                    "latest_findings": ref_findings[:5],
                    "journal_insights": jnl_insights,
                    "summary": f"信心度{cog.get('confidence_calibration', 0):.0%}, 风险偏好{cog.get('risk_appetite', '?')}, 反思{cog.get('total_reflections', 0)}次"
                }
            except Exception as e:
                logger.warning(f"直接获取AGI数据失败: {e}")

        if not intel:
            return {"status": "no_data", "briefings": {}}

        m = self.module_metrics
        equity = m.get("equity", 100000)
        total_pnl = m.get("total_pnl", 0)
        drawdown = m.get("drawdown_pct", m.get("max_dd_pct", 0))
        total_trades = m.get("total_trades", 0)
        win_rate = m.get("rule_win_rate", 0) * 100
        open_pos = m.get("open_positions", 0)

        fng_value = 50
        fng_label = "Neutral"
        btc_price = 0
        ml_accuracy = 0
        try:
            from server.titan_state import TitanState
            btc_pulse = TitanState.market_snapshot.get("btc_pulse", {})
            fng_detail = btc_pulse.get("fng_detail", {})
            fng_value = fng_detail.get("value", btc_pulse.get("fng", 50)) if fng_detail else btc_pulse.get("fng", 50)
            fng_label = fng_detail.get("label", "") if fng_detail else ""
            btc_price = btc_pulse.get("price", 0)
        except Exception:
            pass
        try:
            from server.api import ml_engine
            if ml_engine:
                ml_accuracy = ml_engine.get_status().get("accuracy", 0)
        except Exception:
            pass

        dept_prompts = {}
        dept_names = {
            "reviewer": "审查部",
            "diagnostic": "诊断部",
            "return_rate": "收益部",
            "synapse": "协同部",
            "agent_memory": "记忆部",
            "agi": "AGI智脑",
        }

        for dept_key, dept_data in intel.items():
            dept_name = dept_names.get(dept_key, dept_key)
            data_str = json.dumps(dept_data, ensure_ascii=False, default=str)
            dept_prompts[dept_key] = f"部门: {dept_name}\n原始数据: {data_str}"

        combined_data = "\n\n".join(dept_prompts.values())

        try:
            from server.titan_llm_client import chat_json

            from server.titan_prompt_library import CTO_BRIEFING_PROMPT
            system_prompt = CTO_BRIEFING_PROMPT

            user_prompt = f"""当前基金状况(实时数据):
- BTC价格: ${btc_price:,.1f} | FNG恐贪指数: {fng_value} ({fng_label})
- 总资产: ${equity:,.0f}
- 累计盈亏: ${total_pnl:+,.2f}
- 当前回撤: {drawdown:.2f}%
- 总交易笔数: {total_trades}
- 胜率: {win_rate:.1f}% | ML准确率: {ml_accuracy:.1f}%
- 当前持仓: {open_pos}个

各部门原始数据:
{combined_data}

请为每个部门生成向CEO的工作汇报。"""

            briefings = chat_json(
                module="cto_briefings",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2000,
            )
            if not briefings:
                return self._fallback_briefings(intel)
            self._cached_briefings = {
                "briefings": briefings,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ok",
            }
            self.save()
            logger.info("AI部门汇报生成完成")
            return self._cached_briefings

        except Exception as e:
            logger.warning(f"AI部门汇报生成失败: {e}")
            return self._fallback_briefings(intel)

    def _fallback_briefings(self, intel):
        briefings = {}
        for dept_key, dept_data in intel.items():
            summary = dept_data.get("summary", "暂无数据")
            briefings[dept_key] = summary
        return {"briefings": briefings, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "fallback"}

    def get_department_briefings(self):
        if hasattr(self, '_cached_briefings') and self._cached_briefings:
            return self._cached_briefings
        self._refresh_all_data()
        m = self.module_metrics
        regime_cn = {"trending":"趋势","ranging":"震荡","volatile":"波动","unknown":"未知"}.get(m.get("regime",""), "未知")
        return {
            "briefings": {
                "trading": {"status": "active", "summary": f"已完成{m.get('total_trades',0)}笔交易，胜率{m.get('win_rate',0):.0%}"},
                "risk": {"status": "active", "summary": f"回撤{m.get('drawdown',0):.1f}%，熔断器正常"},
                "market": {"status": "active", "summary": f"市场{regime_cn}环境，FNG={m.get('fng',50)}"},
            },
            "status": "fallback",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def generate_cto_report(self):
        self._refresh_all_data()

        m = self.module_metrics
        intel = dict(self.intelligence_pool) if self.intelligence_pool else {}
        sd = self.strategic_directives

        if "agi" not in intel:
            try:
                from server.titan_agi import titan_agi
                agi_status = titan_agi.get_status()
                cog = agi_status.get("cognitive_state", {})
                latest_ref = agi_status.get("latest_reflection", {})
                latest_jnl = agi_status.get("latest_journal", [])
                jnl_entries = latest_jnl if isinstance(latest_jnl, list) else ([latest_jnl] if latest_jnl else [])
                ref_findings = latest_ref.get("findings", []) if isinstance(latest_ref, dict) else []
                jnl_insights = [e.get("insight", "")[:200] for e in jnl_entries[:3] if isinstance(e, dict) and e.get("insight")]
                intel["agi"] = {
                    "cognitive_state": {"confidence": cog.get("confidence_calibration", 0), "risk_appetite": cog.get("risk_appetite", "unknown"), "total_reflections": cog.get("total_reflections", 0)},
                    "latest_findings": ref_findings[:5],
                    "journal_insights": jnl_insights,
                    "summary": f"信心度{cog.get('confidence_calibration', 0):.0%}, 风险偏好{cog.get('risk_appetite', '?')}, 反思{cog.get('total_reflections', 0)}次"
                }
            except Exception:
                pass

        btc_pulse = {}
        fng_value = 50
        fng_label = "Neutral"
        btc_price = 0
        try:
            from server.titan_state import TitanState
            btc_pulse = TitanState.market_snapshot.get("btc_pulse", {})
            fng_detail = btc_pulse.get("fng_detail", {})
            fng_value = fng_detail.get("value", btc_pulse.get("fng", 50)) if fng_detail else btc_pulse.get("fng", 50)
            fng_label = fng_detail.get("label", "") if fng_detail else ""
            btc_price = btc_pulse.get("price", 0)
        except Exception:
            pass

        ml_accuracy = 0
        ml_f1 = 0
        try:
            from server.api import ml_engine
            if ml_engine:
                ml_s = ml_engine.get_status()
                ml_accuracy = ml_s.get("accuracy", 0)
                ml_f1 = ml_s.get("f1", 0)
        except Exception:
            pass

        equity = m.get("equity", 100000)
        initial_capital = 100000
        total_pnl = m.get("total_pnl", 0)
        drawdown = m.get("drawdown_pct", m.get("max_dd_pct", 0))
        total_trades = m.get("total_trades", 0)
        win_rate = m.get("rule_win_rate", 0) * 100
        ml_wr = m.get("ml_win_rate", 0) * 100
        rule_wr = m.get("rule_win_rate", 0) * 100
        open_pos = m.get("open_positions", 0)
        regime = m.get("regime", "unknown")
        consec_loss = m.get("consecutive_losses", 0)
        consec_win = m.get("consecutive_wins", 0)
        grid_active = m.get("grid_active", 0)
        grid_wr = m.get("grid_win_rate", 0)
        cap_util = m.get("capital_utilization", 0) * 100
        return_pct = ((equity - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0

        dept_summaries = {}
        if hasattr(self, '_cached_briefings') and self._cached_briefings:
            dept_summaries = self._cached_briefings.get("briefings", {})
        elif intel:
            for k, v in intel.items():
                dept_summaries[k] = v.get("summary", "")

        dept_summary_text = "\n".join([f"- {k}: {v}" for k, v in dept_summaries.items() if v]) if dept_summaries else "暂无部门汇报"

        try:
            from server.titan_llm_client import chat_json

            from server.titan_prompt_library import CTO_SUMMARY_PROMPT
            system_prompt = CTO_SUMMARY_PROMPT

            user_prompt = f"""当前基金运行状况(实时数据):
- BTC价格: ${btc_price:,.1f} | FNG恐贪指数: {fng_value} ({fng_label})
- 总资产: ${equity:,.0f} | 累计盈亏: ${total_pnl:+,.2f} | 收益率: {return_pct:+.2f}% | 回撤: {drawdown:.2f}%
- 总交易: {total_trades}笔 | 胜率: {win_rate:.1f}% | ML胜率: {ml_wr:.1f}% | 规则胜率: {rule_wr:.1f}%
- 持仓: {open_pos}个 | 连胜: {consec_win} | 连亏: {consec_loss}
- 市场环境: {regime} | 资金利用率: {cap_util:.1f}%
- 网格: {grid_active}个活跃, 胜率{grid_wr:.1f}%
- ML模型: 准确率{ml_accuracy:.1f}% | F1={ml_f1:.1f}%
- 策略偏好: {sd.get('strategy_preference','N/A')} | 攻守: {sd.get('aggression_mode','N/A')}
- AI准确率: {self.stats.get("ai_accuracy_score", 0.5):.0%}

各部门简要汇报:
{dept_summary_text}

请综合以上信息，向CEO做工作汇报。"""

            report = chat_json(
                module="cto_report",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1000,
            )
            if not report:
                return self._fallback_cto_report(m)
            self._cached_cto_report = {
                "report": report,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "ok",
            }
            logger.info("CTO总结报告生成完成")
            return self._cached_cto_report

        except Exception as e:
            logger.warning(f"CTO总结报告生成失败: {e}")
            return self._fallback_cto_report(m)

    def _fallback_cto_report(self, m):
        regime_cn = {"trending":"趋势","ranging":"震荡","volatile":"波动","unknown":"未知"}.get(m.get("regime",""), "未知")
        report = {
            "title": f"系统运行中 · 市场{regime_cn}环境",
            "report": f"当前系统总资产${m.get('equity',0):,.0f}，累计盈亏${m.get('total_pnl',0):+,.2f}。市场处于{regime_cn}环境，已完成{m.get('total_trades',0)}笔交易。系统各模块正常运行中，建议持续关注市场变化。",
            "risk_level": "medium",
            "action_items": ["持续监控市场环境变化", "关注策略胜率趋势"],
        }
        return {
            "report": report,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "fallback",
        }

    def get_cto_report(self):
        if hasattr(self, '_cached_cto_report') and self._cached_cto_report:
            return self._cached_cto_report
        self._refresh_all_data()
        return self._fallback_cto_report(self.module_metrics)


ai_coordinator = TitanAICoordinator()
