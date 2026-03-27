import os
import json
import time
import logging
from datetime import datetime
from collections import defaultdict
from server.titan_prompt_library import DEEP_EVOLUTION_PROMPT, PHASE_ZERO_CONTEXT

logger = logging.getLogger("TitanDeepEvolution")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADES_PATH = os.path.join(BASE_DIR, "data", "titan_trades.json")
EVOLVED_CONFIG_PATH = os.path.join(BASE_DIR, "data", "titan_evolved_config.json")
MEGA_BACKTEST_PATH = os.path.join(BASE_DIR, "data", "titan_mega_backtest.json")
EVOLUTION_LOG_PATH = os.path.join(BASE_DIR, "data", "deep_evolution_log.json")


class TitanDeepEvolution:

    def _load_json(self, path):
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[DeepEvolution] Failed to load {path}: {e}")
        return None

    def _detect_strategy(self, trade):
        reason = trade.get("reason", "")
        ai_verdict = trade.get("ai_verdict", "")
        combined = f"{reason} {ai_verdict}".lower()
        if "grid" in combined:
            return "grid"
        if "range" in combined:
            return "range"
        return "trend"

    def _build_conditions(self, trade):
        conditions = []
        direction = trade.get("direction", "long")
        if direction == "long":
            conditions.append("macd_bullish")
        else:
            conditions.append("macd_bearish")

        signal_score = trade.get("signal_score", 0)
        if signal_score >= 90:
            conditions.append("adx_strong")
        elif signal_score >= 80:
            conditions.append("adx_moderate")
        else:
            conditions.append("adx_weak")

        ml_conf = trade.get("ml_confidence", 50)
        if ml_conf > 70:
            conditions.append("rsi_neutral")
        elif ml_conf < 40:
            conditions.append("rsi_overbought" if direction == "long" else "rsi_oversold")

        hold_hours = trade.get("hold_hours", 0)
        if hold_hours > 4:
            conditions.append("vol_above_avg")
        elif hold_hours < 1:
            conditions.append("vol_surge")

        return conditions

    def _mine_patterns(self, trades):
        patterns = {
            "by_symbol": defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0, "trades": []}),
            "by_strategy": defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0, "avg_hold": 0, "trades": 0}),
            "by_direction": defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0}),
            "by_hold_bucket": defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0}),
            "by_signal_bucket": defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0}),
            "by_ml_bucket": defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0}),
            "losing_streaks": [],
            "winning_streaks": [],
            "repeat_losers": [],
        }

        for t in trades:
            is_win = t.get("result") == "win"
            pnl = t.get("pnl_pct", 0)
            symbol = t.get("symbol", "?")
            strategy = self._detect_strategy(t)
            direction = t.get("direction", "long")
            hold_hours = t.get("hold_hours", 0)
            signal_score = t.get("signal_score", 0)
            ml_conf = t.get("ml_confidence", 0)

            sp = patterns["by_symbol"][symbol]
            sp["wins" if is_win else "losses"] += 1
            sp["total_pnl"] += pnl
            sp["trades"].append({"pnl": pnl, "strategy": strategy, "direction": direction, "hold_hours": hold_hours})

            st = patterns["by_strategy"][strategy]
            st["wins" if is_win else "losses"] += 1
            st["total_pnl"] += pnl
            st["avg_hold"] += hold_hours
            st["trades"] += 1

            patterns["by_direction"][direction]["wins" if is_win else "losses"] += 1
            patterns["by_direction"][direction]["total_pnl"] += pnl

            if hold_hours <= 1:
                hb = "0-1h"
            elif hold_hours <= 4:
                hb = "1-4h"
            elif hold_hours <= 12:
                hb = "4-12h"
            else:
                hb = "12h+"
            patterns["by_hold_bucket"][hb]["wins" if is_win else "losses"] += 1
            patterns["by_hold_bucket"][hb]["total_pnl"] += pnl

            if signal_score >= 90:
                sb = "90-100"
            elif signal_score >= 80:
                sb = "80-89"
            elif signal_score >= 70:
                sb = "70-79"
            else:
                sb = "<70"
            patterns["by_signal_bucket"][sb]["wins" if is_win else "losses"] += 1
            patterns["by_signal_bucket"][sb]["total_pnl"] += pnl

            if ml_conf >= 70:
                mb = "high(70+)"
            elif ml_conf >= 50:
                mb = "mid(50-69)"
            else:
                mb = "low(<50)"
            patterns["by_ml_bucket"][mb]["wins" if is_win else "losses"] += 1
            patterns["by_ml_bucket"][mb]["total_pnl"] += pnl

        for strategy, data in patterns["by_strategy"].items():
            if data["trades"] > 0:
                data["avg_hold"] = round(data["avg_hold"] / data["trades"], 1)

        streak = 0
        streak_start = 0
        for i, t in enumerate(trades):
            is_loss = t.get("result") != "win"
            if is_loss:
                if streak == 0:
                    streak_start = i
                streak += 1
            else:
                if streak >= 3:
                    symbols = [trades[j].get("symbol", "?") for j in range(streak_start, streak_start + streak)]
                    patterns["losing_streaks"].append({"length": streak, "start_idx": streak_start, "symbols": symbols})
                streak = 0

        if streak >= 3:
            symbols = [trades[j].get("symbol", "?") for j in range(streak_start, streak_start + streak)]
            patterns["losing_streaks"].append({"length": streak, "start_idx": streak_start, "symbols": symbols})

        for sym, data in patterns["by_symbol"].items():
            total = data["wins"] + data["losses"]
            if total >= 2 and data["losses"] >= 2 and data["total_pnl"] < 0:
                patterns["repeat_losers"].append({
                    "symbol": sym,
                    "losses": data["losses"],
                    "wins": data["wins"],
                    "total_pnl": round(data["total_pnl"], 3),
                })

        def make_serializable(d):
            if isinstance(d, defaultdict):
                return {k: make_serializable(v) for k, v in d.items()}
            if isinstance(d, dict):
                return {k: make_serializable(v) for k, v in d.items()}
            if isinstance(d, list):
                return [make_serializable(i) for i in d]
            if isinstance(d, float):
                return round(d, 4)
            return d

        return make_serializable(patterns)

    def _ai_deep_analyze(self, trades, patterns, current_regime):
        try:
            from server.titan_llm_client import chat_json

            total = len(trades)
            wins = sum(1 for t in trades if t.get("result") == "win")
            total_pnl = sum(t.get("pnl_pct", 0) for t in trades)

            strategy_text = "\n".join(
                f"  {s}: {d['trades']}笔, 胜率{round(d['wins']/max(1,d['wins']+d['losses'])*100,1)}%, "
                f"总PnL={round(d['total_pnl'],2)}%, 平均持仓{d['avg_hold']}h"
                for s, d in patterns["by_strategy"].items()
            )

            hold_text = "\n".join(
                f"  {b}: {d['wins']+d['losses']}笔, 胜率{round(d['wins']/max(1,d['wins']+d['losses'])*100,1)}%, PnL={round(d['total_pnl'],2)}%"
                for b, d in sorted(patterns["by_hold_bucket"].items())
            )

            signal_text = "\n".join(
                f"  {b}: {d['wins']+d['losses']}笔, 胜率{round(d['wins']/max(1,d['wins']+d['losses'])*100,1)}%, PnL={round(d['total_pnl'],2)}%"
                for b, d in sorted(patterns["by_signal_bucket"].items())
            )

            ml_text = "\n".join(
                f"  {b}: {d['wins']+d['losses']}笔, 胜率{round(d['wins']/max(1,d['wins']+d['losses'])*100,1)}%, PnL={round(d['total_pnl'],2)}%"
                for b, d in patterns["by_ml_bucket"].items()
            )

            direction_text = "\n".join(
                f"  {d}: {v['wins']+v['losses']}笔, 胜率{round(v['wins']/max(1,v['wins']+v['losses'])*100,1)}%, PnL={round(v['total_pnl'],2)}%"
                for d, v in patterns["by_direction"].items()
            )

            losers_text = "\n".join(
                f"  {r['symbol']}: {r['losses']}负{r['wins']}胜, 总PnL={r['total_pnl']}%"
                for r in patterns["repeat_losers"][:10]
            ) or "  无"

            streaks_text = "\n".join(
                f"  连亏{s['length']}笔: {', '.join(s['symbols'][:5])}"
                for s in patterns["losing_streaks"]
            ) or "  无"

            prompt = PHASE_ZERO_CONTEXT + f"""你是量化基金的首席策略分析师。深度分析以下交易数据模式，找出核心问题和改进方向。

== 总览 ==
共{total}笔交易, {wins}胜{total-wins}负, 总体胜率{round(wins/max(1,total)*100,1)}%, 总PnL={round(total_pnl,2)}%
当前市场环境: {current_regime}

== 策略维度 ==
{strategy_text}

== 持仓时间维度 ==
{hold_text}

== 信号质量维度 ==
{signal_text}

== ML置信度维度 ==
{ml_text}

== 方向维度 ==
{direction_text}

== 重复亏损币种 ==
{losers_text}

== 连败记录 ==
{streaks_text}

请用JSON格式给出深度分析:
{{
  "core_problems": ["核心问题1", "核心问题2", ...],
  "winning_patterns": ["盈利模式1: 具体描述", ...],
  "losing_patterns": ["亏损模式1: 具体描述", ...],
  "hold_time_insight": "最优持仓时间分析",
  "signal_quality_insight": "信号质量与胜率的关系分析",
  "ml_confidence_insight": "ML置信度与实际表现的关系",
  "direction_insight": "多空方向偏好分析",
  "strategy_recommendations": [
    {{"action": "具体建议", "priority": "high/medium/low", "expected_impact": "预期效果", "implementation": "实施方法"}}
  ],
  "risk_warnings": ["风险警告1", ...],
  "optimization_plan": {{
    "short_term": ["1周内可执行的优化"],
    "medium_term": ["1月内的改进计划"],
    "long_term": ["长期战略调整"]
  }},
  "confidence_score": 0.0-1.0
}}"""

            result = chat_json(
                module="deep_evolution",
                messages=[
                    {"role": "system", "content": DEEP_EVOLUTION_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )
            if not result:
                return None
            logger.info(f"[DeepEvolution] AI深度分析完成, {len(result.get('core_problems',[]))}个核心问题, {len(result.get('strategy_recommendations',[]))}条建议")
            return result
        except Exception as e:
            logger.warning(f"[DeepEvolution] AI深度分析失败: {e}")
            return None

    def _record_to_memory_bank(self, trades, patterns, ai_analysis, memory_bank, current_regime):
        if not memory_bank:
            return 0
        recorded = 0
        try:
            for t in trades:
                memory_bank.record_trade_pattern({
                    "symbol": t.get("symbol", ""),
                    "direction": t.get("direction", "long"),
                    "result": t.get("result", "loss"),
                    "pnl_pct": t.get("pnl_pct", 0),
                    "regime": current_regime,
                    "strategy": self._detect_strategy(t),
                    "signal_score": t.get("signal_score", 0),
                    "ml_confidence": t.get("ml_confidence", 0),
                    "holding_hours": t.get("hold_hours", 0),
                    "entry_conditions": {
                        "ai_verdict": t.get("ai_verdict", "")[:50],
                        "reason": t.get("reason", "")[:50],
                    },
                    "lesson": "",
                })
                recorded += 1
        except Exception as e:
            logger.warning(f"[DeepEvolution] MemoryBank trade pattern record error: {e}")

        try:
            total = len(trades)
            wins = sum(1 for t in trades if t.get("result") == "win")
            total_pnl = sum(t.get("pnl_pct", 0) for t in trades)
            memory_bank.record_performance_snapshot({
                "equity": 0,
                "total_trades": total,
                "win_rate": round(wins / max(1, total) * 100, 1),
                "sharpe": 0,
                "max_drawdown": 0,
                "open_positions": 0,
                "regime": current_regime,
            })
            recorded += 1
        except Exception as e:
            logger.warning(f"[DeepEvolution] MemoryBank performance snapshot error: {e}")

        if ai_analysis:
            try:
                for problem in ai_analysis.get("core_problems", [])[:5]:
                    memory_bank.add_insight("trade_analysis", problem, confidence=ai_analysis.get("confidence_score", 0.5), source="deep_evolution_ai")
                    recorded += 1
                for rec in ai_analysis.get("strategy_recommendations", [])[:5]:
                    memory_bank.add_rule(
                        rule_type="ai_strategy_recommendation",
                        condition=rec.get("action", ""),
                        action=rec.get("implementation", ""),
                        performance={"priority": rec.get("priority", "medium"), "expected_impact": rec.get("expected_impact", "")},
                    )
                    recorded += 1
                for warning in ai_analysis.get("risk_warnings", [])[:3]:
                    memory_bank.record_market_event(
                        event_type="risk_warning",
                        description=warning,
                        impact=-1,
                        data={"source": "deep_evolution_ai", "regime": current_regime},
                    )
                    recorded += 1
            except Exception as e:
                logger.warning(f"[DeepEvolution] MemoryBank AI insight record error: {e}")

        logger.info(f"[DeepEvolution] MemoryBank: {recorded} records written")
        return recorded

    def run_deep_evolution(self, synapse, signal_quality, agent_memory, feedback_engine,
                           risk_budget, governor, return_target, ai_coordinator,
                           dispatcher, paper_trader, mega_backtest_data, mm_metrics_data,
                           memory_bank=None):
        print("[DeepEvolution] === Starting Deep Evolution Pass (Enhanced) ===")
        start_time = time.time()

        trades_processed = 0
        predictions_processed = 0
        synapse_broadcasts = 0
        signal_quality_records = 0
        governor_records = 0
        insights_generated = 0
        memory_records = 0
        errors = []

        current_regime = getattr(dispatcher, "current_regime", "unknown")
        print(f"[DeepEvolution] Current regime: {current_regime}")

        trades = self._load_json(TRADES_PATH)
        if not trades:
            trades = []
        print(f"[DeepEvolution] Loaded {len(trades)} historical trades")

        for i, trade in enumerate(trades):
            try:
                symbol = trade.get("symbol", "UNKNOWN")
                direction = trade.get("direction", "long")
                pnl_pct = trade.get("pnl_pct", 0)
                signal_score = trade.get("signal_score", 0)
                hold_hours = trade.get("hold_hours", 0)
                is_win = trade.get("result", "loss") == "win"

                strategy_type = trade.get("strategy", self._detect_strategy(trade))
                trade_regime = trade.get("regime", current_regime)

                trade_info = {
                    "symbol": symbol,
                    "strategy_type": strategy_type,
                    "market_regime": trade_regime,
                    "pnl_pct": pnl_pct,
                    "direction": direction,
                    "signal_score": signal_score,
                    "holding_hours": hold_hours,
                }
                synapse.broadcast_trade_result(trade_info)
                synapse_broadcasts += 1

                conditions = self._build_conditions(trade)
                signal_quality.record_outcome(conditions, is_win, pnl_pct, symbol, trade_regime)
                signal_quality_records += 1

                governor.record_trade_result(is_win)
                governor_records += 1

                trades_processed += 1
                if (i + 1) % 10 == 0:
                    print(f"[DeepEvolution] Processed {i + 1}/{len(trades)} trades")
            except Exception as e:
                errors.append(f"Trade #{i} ({trade.get('symbol', '?')}): {e}")
                print(f"[DeepEvolution] Error processing trade #{i}: {e}")

        print(f"[DeepEvolution] Trades done: {trades_processed} processed, {synapse_broadcasts} synapse, {signal_quality_records} signal_quality, {governor_records} governor")

        predictions = agent_memory.adaptive_weights.get("predictions", [])
        print(f"[DeepEvolution] Found {len(predictions)} predictions in agent_memory")

        for i, pred in enumerate(predictions):
            try:
                outcome = pred.get("outcome")
                if outcome is None:
                    continue

                symbol = pred.get("symbol", "UNKNOWN")
                ml_label = pred.get("ml_label", "unknown")
                if outcome in ("correct", "win"):
                    actual_outcome = "win"
                elif outcome in ("wrong", "loss"):
                    actual_outcome = "loss"
                else:
                    continue

                features_snapshot = {
                    "regime": current_regime,
                    "entry_price": pred.get("entry_price", 0),
                    "ml_confidence": pred.get("ml_confidence", 0),
                }

                feedback_engine.record_prediction_outcome(symbol, ml_label, actual_outcome, features_snapshot, direction=pred.get("direction"))
                predictions_processed += 1
            except Exception as e:
                errors.append(f"Prediction #{i}: {e}")
                print(f"[DeepEvolution] Error processing prediction #{i}: {e}")

        print(f"[DeepEvolution] Predictions done: {predictions_processed} processed")

        print("[DeepEvolution] === Pattern Mining ===")
        patterns = self._mine_patterns(trades)
        pattern_summary = {
            "strategies": len(patterns["by_strategy"]),
            "symbols_analyzed": len(patterns["by_symbol"]),
            "losing_streaks": len(patterns["losing_streaks"]),
            "repeat_losers": len(patterns["repeat_losers"]),
        }
        print(f"[DeepEvolution] Patterns: {pattern_summary}")

        print("[DeepEvolution] === AI Deep Analysis ===")
        ai_analysis = self._ai_deep_analyze(trades, patterns, current_regime)
        if ai_analysis:
            core_problems = ai_analysis.get("core_problems", [])
            recommendations = ai_analysis.get("strategy_recommendations", [])
            print(f"[DeepEvolution] AI found {len(core_problems)} core problems, {len(recommendations)} recommendations")
            for i, problem in enumerate(core_problems[:3]):
                insight_text = f"[AI深度分析] 核心问题{i+1}: {problem}"
                agent_memory.add_insight(insight_text)
                insights_generated += 1
            for rec in recommendations[:3]:
                insight_text = f"[AI深度分析] 建议: {rec.get('action','')} (优先级:{rec.get('priority','')}, 预期:{rec.get('expected_impact','')})"
                agent_memory.add_insight(insight_text)
                insights_generated += 1
        else:
            print("[DeepEvolution] AI analysis unavailable, using rule-based insights")

        print("[DeepEvolution] === MemoryBank Recording ===")
        memory_records = self._record_to_memory_bank(trades, patterns, ai_analysis, memory_bank, current_regime)
        print(f"[DeepEvolution] MemoryBank: {memory_records} records written")

        corr_path = os.path.join(BASE_DIR, "data", "titan_correlation_matrix.json")
        corr_data = self._load_json(corr_path)
        if corr_data and hasattr(synapse, 'knowledge_base'):
            try:
                synapse.knowledge_base["correlation_map"] = {}
                for coin, beta in corr_data.get("btc_betas", {}).items():
                    synapse.knowledge_base["correlation_map"][coin] = {
                        "btc_beta": beta,
                        "btc_corr": corr_data.get("correlation_matrix", {}).get(coin, {}).get("BTC", 0),
                    }
                print(f"[DeepEvolution] Correlation map: {len(synapse.knowledge_base['correlation_map'])} coins injected")
            except Exception as e:
                errors.append(f"Correlation inject: {e}")

        mc_path = os.path.join(BASE_DIR, "data", "titan_monte_carlo_results.json")
        mc_data = self._load_json(mc_path)
        if mc_data and memory_bank:
            try:
                mc_results = mc_data.get("results", {})
                mc_text = (f"MC{mc_data.get('config',{}).get('num_paths',0)}paths: "
                           f"median={round(mc_results.get('median_return',0)*100,1)}%, "
                           f"ruin={round(mc_results.get('ruin_probability',0)*100,1)}%, "
                           f"risk={mc_data.get('risk_assessment',{}).get('level','?')}")
                agent_memory.add_insight(f"[DeepEvolution] {mc_text}")
                insights_generated += 1
                print(f"[DeepEvolution] Monte Carlo insight logged")
            except Exception as e:
                errors.append(f"Monte Carlo insight: {e}")

        evolved_config = self._load_json(EVOLVED_CONFIG_PATH)
        mega_data = self._load_json(MEGA_BACKTEST_PATH)

        if evolved_config:
            try:
                fitness = evolved_config.get("fitness", 0)
                evolved_at = evolved_config.get("evolved_at", "unknown")
                params_str = ", ".join(f"{k}={v}" for k, v in evolved_config.items()
                                       if k not in ("fitness", "evolved_at", "generations", "population_size", "assets_used", "enabled"))
                insight_text = f"[DeepEvolution] 进化配置（适应度={fitness}, 时间={evolved_at}）: {params_str}"
                agent_memory.add_insight(insight_text)
                insights_generated += 1
                print(f"[DeepEvolution] 已记录进化配置洞察")
            except Exception as e:
                errors.append(f"进化配置洞察异常: {e}")

        if mega_data:
            try:
                best_params = mega_data.get("best_params", mega_data.get("best_genes", {}))
                best_calmar = mega_data.get("best_calmar", 0)
                total_gen = mega_data.get("total_generations", 0)
                total_bt = mega_data.get("total_backtests", 0)
                params_str = ", ".join(f"{k}={v}" for k, v in best_params.items())
                insight_text = f"[DeepEvolution] 超级回测最优（卡玛比率={best_calmar}, 代数={total_gen}, 回测次数={total_bt}）: {params_str}"
                agent_memory.add_insight(insight_text)
                insights_generated += 1
                print(f"[DeepEvolution] 已记录超级回测洞察")
            except Exception as e:
                errors.append(f"超级回测洞察异常: {e}")

        total_pnl = sum(t.get("pnl_pct", 0) for t in trades)
        wins = sum(1 for t in trades if t.get("result") == "win")
        losses = sum(1 for t in trades if t.get("result") != "win")
        win_rate = round(wins / max(1, wins + losses) * 100, 1)

        summary_text = (
            f"深度进化完成（增强版）："
            f"{trades_processed}笔交易 → 突触/信号质量/调节器，"
            f"{predictions_processed}条预测 → 反馈引擎，"
            f"{insights_generated}条洞察，{memory_records}条记忆记录。"
            f"模式发现：{len(patterns['by_symbol'])}个标的，{len(patterns['losing_streaks'])}次连亏，{len(patterns['repeat_losers'])}个重复亏损标的。"
            f"交易统计：{wins}胜/{losses}负（{win_rate}%胜率），总盈亏：{total_pnl:.2f}%。"
            f"AI分析：{'✓' if ai_analysis else '✗'}。"
            f"错误：{len(errors)}"
        )

        if errors:
            summary_text += f" | 首个错误: {errors[0]}"

        print(f"[DeepEvolution] {summary_text}")

        print("[DeepEvolution] Saving all modules...")
        try:
            synapse.save()
        except Exception as e:
            print(f"[DeepEvolution] Synapse save error: {e}")
        try:
            signal_quality.save()
        except Exception as e:
            print(f"[DeepEvolution] SignalQuality save error: {e}")
        try:
            agent_memory.save()
        except Exception as e:
            print(f"[DeepEvolution] AgentMemory save error: {e}")
        try:
            governor.save()
        except Exception as e:
            print(f"[DeepEvolution] Governor save error: {e}")

        elapsed = round(time.time() - start_time, 2)
        print(f"[DeepEvolution] === 深度进化完成，耗时 {elapsed}s ===")

        result = {
            "trades_processed": trades_processed,
            "predictions_processed": predictions_processed,
            "synapse_broadcasts": synapse_broadcasts,
            "signal_quality_records": signal_quality_records,
            "insights_generated": insights_generated,
            "memory_records": memory_records,
            "patterns": pattern_summary,
            "ai_analysis": {
                "available": ai_analysis is not None,
                "core_problems": ai_analysis.get("core_problems", []) if ai_analysis else [],
                "winning_patterns": ai_analysis.get("winning_patterns", []) if ai_analysis else [],
                "losing_patterns": ai_analysis.get("losing_patterns", []) if ai_analysis else [],
                "recommendations_count": len(ai_analysis.get("strategy_recommendations", [])) if ai_analysis else 0,
                "hold_time_insight": ai_analysis.get("hold_time_insight", "") if ai_analysis else "",
                "signal_quality_insight": ai_analysis.get("signal_quality_insight", "") if ai_analysis else "",
                "ml_confidence_insight": ai_analysis.get("ml_confidence_insight", "") if ai_analysis else "",
                "direction_insight": ai_analysis.get("direction_insight", "") if ai_analysis else "",
                "optimization_plan": ai_analysis.get("optimization_plan", {}) if ai_analysis else {},
                "risk_warnings": ai_analysis.get("risk_warnings", []) if ai_analysis else [],
                "confidence_score": ai_analysis.get("confidence_score", 0) if ai_analysis else 0,
            },
            "repeat_losers": patterns.get("repeat_losers", []),
            "losing_streaks": patterns.get("losing_streaks", []),
            "summary_text": summary_text,
        }

        self._save_evolution_log(result, elapsed)

        return result

    def _save_evolution_log(self, result, elapsed):
        try:
            log_data = []
            if os.path.exists(EVOLUTION_LOG_PATH):
                with open(EVOLUTION_LOG_PATH, "r") as f:
                    log_data = json.load(f)
                if not isinstance(log_data, list):
                    log_data = []

            safe_result = {k: v for k, v in result.items() if k != "ai_analysis"}
            if result.get("ai_analysis"):
                safe_result["ai_analysis_summary"] = {
                    "available": result["ai_analysis"]["available"],
                    "core_problems_count": len(result["ai_analysis"].get("core_problems", [])),
                    "recommendations_count": result["ai_analysis"].get("recommendations_count", 0),
                    "confidence_score": result["ai_analysis"].get("confidence_score", 0),
                }

            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "elapsed_seconds": elapsed,
                **safe_result,
            }
            log_data.append(log_entry)

            log_data = log_data[-50:]

            with open(EVOLUTION_LOG_PATH, "w") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            print(f"[DeepEvolution] Evolution log saved to {EVOLUTION_LOG_PATH}")
        except Exception as e:
            print(f"[DeepEvolution] Failed to save evolution log: {e}")


def run_evolution():
    from server.titan_synapse import TitanSynapse
    from server.titan_signal_quality import TitanSignalQuality
    from server.titan_agent import agent_memory, governor, feedback_engine
    from server.titan_risk_budget import TitanRiskBudget
    from server.titan_return_target import return_target
    from server.titan_ai_coordinator import ai_coordinator
    from server.titan_dispatcher import dispatcher
    from server.titan_paper_trader import TitanPaperTrader

    synapse = TitanSynapse()
    signal_quality = TitanSignalQuality()
    risk_budget = TitanRiskBudget()
    paper_trader = TitanPaperTrader()

    mega_backtest_data = None
    try:
        mega_path = os.path.join(BASE_DIR, "data", "titan_mega_backtest.json")
        if os.path.exists(mega_path):
            with open(mega_path, "r") as f:
                mega_backtest_data = json.load(f)
    except Exception:
        pass

    mm_metrics_data = None
    try:
        mm_path = os.path.join(BASE_DIR, "data", "titan_mm_metrics.json")
        if os.path.exists(mm_path):
            with open(mm_path, "r") as f:
                mm_metrics_data = json.load(f)
    except Exception:
        pass

    memory_bank = None
    try:
        from server.titan_external_data import TitanMemoryBank
        memory_bank = TitanMemoryBank(data_dir=os.path.join(BASE_DIR, "data"))
    except Exception:
        pass

    engine = TitanDeepEvolution()
    result = engine.run_deep_evolution(
        synapse=synapse,
        signal_quality=signal_quality,
        agent_memory=agent_memory,
        feedback_engine=feedback_engine,
        risk_budget=risk_budget,
        governor=governor,
        return_target=return_target,
        ai_coordinator=ai_coordinator,
        dispatcher=dispatcher,
        paper_trader=paper_trader,
        mega_backtest_data=mega_backtest_data,
        mm_metrics_data=mm_metrics_data,
        memory_bank=memory_bank,
    )

    return result
