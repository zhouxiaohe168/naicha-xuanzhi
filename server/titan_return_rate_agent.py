import os
import json
import time
import logging
from datetime import datetime
from server.titan_prompt_library import RETURN_RATE_PROMPT, PHASE_ZERO_CONTEXT
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanReturnRateAgent")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_PATH = os.path.join(BASE_DIR, "data", "titan_return_rate_agent.json")


class TitanReturnRateAgent:

    def __init__(self):
        self.thought_log = []
        self.recommendations = []
        self.current_diagnosis = {}
        self.evolution_insights = []
        self.stats = {
            "total_thoughts": 0,
            "total_recommendations": 0,
            "applied_recommendations": 0,
            "last_think_time": "",
            "consecutive_below_target": 0,
            "best_annualized_seen": 0,
            "worst_annualized_seen": 0,
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(AGENT_PATH):
                with open(AGENT_PATH, "r") as f:
                    data = json.load(f)
                self.thought_log = data.get("thought_log", [])[-100:]
                self.recommendations = data.get("recommendations", [])[-50:]
                self.current_diagnosis = data.get("current_diagnosis", {})
                self.evolution_insights = data.get("evolution_insights", [])[-30:]
                self.stats = data.get("stats", self.stats)
        except Exception as e:
            logger.warning(f"ReturnRateAgent load failed: {e}")

    def save(self):
        try:
            data = {
                "thought_log": self.thought_log[-100:],
                "recommendations": self.recommendations[-50:],
                "current_diagnosis": self.current_diagnosis,
                "evolution_insights": self.evolution_insights[-30:],
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            atomic_json_save(AGENT_PATH, data)
        except Exception:
            pass

    def think(self, context, agent_memory=None, ai_coordinator=None, return_target=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rt = context.get("return_target", {})
        portfolio = context.get("paper_portfolio", {})
        trades = context.get("trades_history", [])
        coordinator_recs = context.get("coordinator_recs", {})
        regime = context.get("dispatcher_regime", "unknown")
        risk_budget = context.get("risk_budget", {})
        fng = context.get("fng", 50)
        ud = context.get("unified_decision", {})
        ml_acc = context.get("ml_accuracy", 0)
        synapse_data = context.get("synapse", {})
        sq_data = context.get("signal_quality", {})

        annualized = rt.get("annualized_return_pct", 0)
        total_return = rt.get("total_return_pct", 0)
        days_running = rt.get("days_running", 0)
        aggression = rt.get("aggression_multiplier", 1.0)
        on_target = rt.get("on_target", False)
        equity = rt.get("current_equity", 100000)
        peak = rt.get("peak_equity", 100000)

        observations = []
        diagnosis = {}
        recommendations = []

        if on_target:
            self.stats["consecutive_below_target"] = 0
            observations.append(f"年化收益{annualized:.1f}%已达标(≥12%)")
            diagnosis["status"] = "on_target"
            diagnosis["severity"] = "healthy"
        else:
            self.stats["consecutive_below_target"] += 1
            observations.append(f"年化收益{annualized:.1f}%未达12%目标, 连续{self.stats['consecutive_below_target']}次检查未达标")
            diagnosis["status"] = "below_target"
            diagnosis["severity"] = "warning" if annualized > 0 else "critical" if annualized < -10 else "alert"

        if annualized > self.stats["best_annualized_seen"]:
            self.stats["best_annualized_seen"] = round(annualized, 2)
        if annualized < self.stats["worst_annualized_seen"]:
            self.stats["worst_annualized_seen"] = round(annualized, 2)

        if days_running < 7:
            observations.append(f"运行仅{days_running}天, 年化数据尚不稳定, 以总收益{total_return:.2f}%为准")
            diagnosis["data_maturity"] = "immature"
        elif days_running < 30:
            observations.append(f"运行{days_running}天, 数据积累中, 年化参考性中等")
            diagnosis["data_maturity"] = "developing"
        else:
            observations.append(f"运行{days_running}天, 数据已具参考性")
            diagnosis["data_maturity"] = "mature"

        drawdown = 0
        if peak > 0:
            drawdown = round((peak - equity) / peak * 100, 2)
        diagnosis["drawdown_pct"] = drawdown
        if drawdown > 8:
            observations.append(f"⚠️ 回撤{drawdown:.1f}%超过8%警戒线")
        elif drawdown > 5:
            observations.append(f"回撤{drawdown:.1f}%接近警戒区域")

        recent_trades = trades[-10:] if trades else []
        if recent_trades:
            wins = sum(1 for t in recent_trades if t.get("pnl_pct", 0) > 0 or t.get("result") == "win")
            total = len(recent_trades)
            wr = round(wins / total * 100, 1)
            avg_pnl = round(sum(t.get("pnl_pct", 0) for t in recent_trades) / total, 2)
            observations.append(f"近{total}笔交易: 胜率{wr}%, 平均收益{avg_pnl}%")
            diagnosis["recent_win_rate"] = wr
            diagnosis["recent_avg_pnl"] = avg_pnl

            if wr < 30 and total >= 5:
                recommendations.append({
                    "type": "reduce_trading_frequency",
                    "priority": "high",
                    "reason": f"近期胜率仅{wr}%, 建议提高入场门槛减少交易频率",
                    "action": "raise_threshold",
                    "value": 5,
                })

            if avg_pnl < -1.0:
                recommendations.append({
                    "type": "tighten_stop_loss",
                    "priority": "high",
                    "reason": f"平均亏损{avg_pnl}%过大, 建议收紧止损",
                    "action": "adjust_sl",
                })

            losing_symbols = {}
            for t in recent_trades:
                sym = t.get("symbol", "?")
                if t.get("pnl_pct", 0) < 0 or t.get("result") == "loss":
                    losing_symbols[sym] = losing_symbols.get(sym, 0) + 1
            repeat_losers = {k: v for k, v in losing_symbols.items() if v >= 2}
            if repeat_losers:
                observations.append(f"重复亏损币种: {repeat_losers}")
                recommendations.append({
                    "type": "avoid_repeat_losers",
                    "priority": "medium",
                    "reason": f"多次在相同币种亏损: {list(repeat_losers.keys())[:3]}",
                    "action": "add_ban_rule",
                    "symbols": list(repeat_losers.keys())[:5],
                })

        observations.append(f"市场环境: {regime}, FNG={fng}")
        if fng <= 15:
            observations.append("极度恐惧市场, 做空风险高, 适合逢低建仓优质资产")
        elif fng >= 85:
            observations.append("极度贪婪市场, 做多风险高, 注意获利了结")

        observations.append(f"ML准确率: {ml_acc}%")
        if ml_acc < 55:
            recommendations.append({
                "type": "reduce_ml_weight",
                "priority": "medium",
                "reason": f"ML准确率{ml_acc}%偏低, 建议降低ML权重",
                "action": "adjust_ml_weight",
                "value": 0.25,
            })
        elif ml_acc > 65:
            recommendations.append({
                "type": "increase_ml_weight",
                "priority": "low",
                "reason": f"ML准确率{ml_acc}%良好, 可适当提高ML权重",
                "action": "adjust_ml_weight",
                "value": 0.45,
            })

        ud_last = ud.get("last_decision", {})
        current_mode = ud_last.get("mode", "unknown")
        observations.append(f"当前交易模式: {current_mode}")

        coord_size = coordinator_recs.get("size_multiplier", 1.0)
        coord_throttle = coordinator_recs.get("throttle_level", "normal")
        observations.append(f"协调器: 仓位因子={coord_size:.2f}, 节流={coord_throttle}")

        synapse_broadcasts = synapse_data.get("total_broadcasts", 0)
        sq_evaluated = sq_data.get("total_evaluated", 0)
        observations.append(f"知识积累: 突触{synapse_broadcasts}次广播, 信号质量{sq_evaluated}次评估")

        if not on_target and annualized < 0:
            if regime == "trending" and fng < 30:
                recommendations.append({
                    "type": "strategy_suggestion",
                    "priority": "high",
                    "reason": "趋势市+恐惧情绪=潜在抄底机会, 关注大市值币种回调",
                    "action": "focus_large_cap",
                })
            elif regime == "ranging":
                recommendations.append({
                    "type": "strategy_suggestion",
                    "priority": "medium",
                    "reason": "震荡市适合网格交易, 建议增加网格配置",
                    "action": "enable_grid",
                })

        if aggression >= 1.3 and drawdown > 5:
            recommendations.append({
                "type": "risk_warning",
                "priority": "critical",
                "reason": f"激进度{aggression}x+回撤{drawdown}%=高风险状态, 建议降低激进度",
                "action": "cap_aggression",
                "value": 1.15,
            })

        thinking = (
            f"【收益智能体思考】{now}\n"
            f"状态: 年化{annualized:.1f}%, 总收益{total_return:.2f}%, 运行{days_running}天\n"
            f"诊断: {diagnosis.get('status', 'unknown')} ({diagnosis.get('severity', 'unknown')})\n"
            f"观察:\n" + "\n".join(f"  - {o}" for o in observations) + "\n"
            f"建议数: {len(recommendations)}"
        )

        thought = {
            "time": now,
            "observations": observations,
            "diagnosis": diagnosis,
            "recommendations": [r.copy() for r in recommendations],
            "thinking_summary": thinking,
            "context_snapshot": {
                "annualized": annualized,
                "total_return": total_return,
                "days_running": days_running,
                "aggression": aggression,
                "regime": regime,
                "fng": fng,
                "ml_accuracy": ml_acc,
                "mode": current_mode,
                "drawdown": drawdown,
            },
        }
        self.thought_log.append(thought)
        if len(self.thought_log) > 100:
            self.thought_log = self.thought_log[-100:]

        self.current_diagnosis = diagnosis
        self.recommendations = recommendations
        self.stats["total_thoughts"] += 1

        ai_insight = self._ai_analyze(observations, diagnosis, recommendations, context)
        if ai_insight:
            thought["ai_insight"] = ai_insight
            if ai_insight.get("ai_recommendations"):
                for ai_rec in ai_insight["ai_recommendations"][:3]:
                    recommendations.append({
                        "type": "ai_suggestion",
                        "priority": ai_rec.get("priority", "medium"),
                        "reason": ai_rec.get("suggestion", ""),
                        "action": "ai_advisory",
                        "source": "gpt-4o-mini",
                    })

        applied = self._apply_recommendations(recommendations, agent_memory, ai_coordinator, return_target)

        insight_text = f"收益智能体[{now}]: 年化{annualized:.1f}% | {diagnosis.get('severity','?')} | {len(recommendations)}条建议 | {applied}条已应用"
        if ai_insight:
            insight_text += f" | AI分析: {ai_insight.get('summary', '')[:60]}"
        self.evolution_insights.append({"time": now, "insight": insight_text})
        if agent_memory:
            agent_memory.add_insight(insight_text)

        self.save()

        return {
            "thinking": thinking,
            "observations": observations,
            "diagnosis": diagnosis,
            "recommendations": recommendations,
            "applied": applied,
            "ai_insight": ai_insight,
            "timestamp": now,
        }

    def _ai_analyze(self, observations, diagnosis, recommendations, context):
        try:
            from server.titan_llm_client import chat_json

            obs_text = "\n".join(f"- {o}" for o in observations[:12])
            rec_text = "\n".join(f"- [{r['priority']}] {r['reason']}" for r in recommendations[:6])

            prompt = PHASE_ZERO_CONTEXT + f"""你是量化基金的收益诊断AI顾问。分析以下收益数据，给出精准诊断和改进建议。

== 当前观察 ==
{obs_text}

== 诊断结果 ==
严重度: {diagnosis.get('severity', 'unknown')}
年化收益: {context.get('return_target', {}).get('annualized_return_pct', 0):.1f}%
目标: 12%(无上限)
回撤: {diagnosis.get('drawdown_pct', 0):.1f}%
市场环境: {context.get('dispatcher_regime', 'unknown')}
FNG: {context.get('fng', 50)}

== 已有建议 ==
{rec_text}

请用JSON格式回答:
{{
  "summary": "一句话诊断(20字以内)",
  "root_cause": "收益未达标的根本原因分析",
  "ai_recommendations": [
    {{"priority": "high/medium/low", "suggestion": "具体改进建议", "expected_impact": "预期效果"}}
  ],
  "risk_alert": "当前最大风险点",
  "outlook": "未来1周展望"
}}"""

            result = chat_json(
                module="return_rate_agent",
                messages=[
                    {"role": "system", "content": RETURN_RATE_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )
            if not result:
                return None
            logger.info(f"ReturnRateAgent AI分析完成: {result.get('summary', '')}")
            return result
        except Exception as e:
            logger.warning(f"ReturnRateAgent AI分析失败: {e}")
            return None

    def _apply_recommendations(self, recommendations, agent_memory, ai_coordinator, return_target):
        applied = 0
        for rec in recommendations:
            try:
                action = rec.get("action")
                priority = rec.get("priority", "low")

                if priority == "critical" and action == "cap_aggression":
                    if return_target and return_target.aggression_multiplier > rec.get("value", 1.15):
                        return_target.aggression_multiplier = rec["value"]
                        return_target.threshold_delta = max(return_target.threshold_delta, -4)
                        applied += 1
                        rec["applied"] = True

                elif action == "add_ban_rule" and agent_memory:
                    for sym in rec.get("symbols", [])[:3]:
                        existing = [r for r in agent_memory.critic_ban_rules
                                   if r.get("type") == "return_agent_ban" and r.get("symbol") == sym]
                        if not existing:
                            agent_memory.critic_ban_rules.append({
                                "type": "return_agent_ban",
                                "symbol": sym,
                                "reason": rec["reason"],
                                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            })
                            applied += 1
                            rec["applied"] = True

                elif action == "adjust_ml_weight" and agent_memory:
                    new_weight = rec.get("value", 0.35)
                    agent_memory.adaptive_weights["ml_weight_override"] = new_weight
                    applied += 1
                    rec["applied"] = True

            except Exception as e:
                logger.warning(f"ReturnRateAgent apply failed: {e}")

        return applied

    def periodic_review(self, context, agent_memory=None, ai_coordinator=None, return_target=None):
        if len(self.thought_log) < 2:
            return self.think(context, agent_memory, ai_coordinator, return_target)

        recent_thoughts = self.thought_log[-5:]
        improving = False
        if len(recent_thoughts) >= 2:
            latest = recent_thoughts[-1].get("context_snapshot", {})
            prev = recent_thoughts[-2].get("context_snapshot", {})
            if latest.get("annualized", 0) > prev.get("annualized", 0):
                improving = True

        result = self.think(context, agent_memory, ai_coordinator, return_target)

        if improving:
            result["trend"] = "improving"
            self.evolution_insights.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "insight": "收益趋势改善中，继续当前策略方向",
            })
        else:
            result["trend"] = "declining"
            self.evolution_insights.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "insight": "收益趋势下滑，需要调整策略方向",
            })

        self.save()
        return result

    def get_status(self):
        recent = self.thought_log[-3:] if self.thought_log else []
        return {
            "current_diagnosis": self.current_diagnosis,
            "latest_recommendations": self.recommendations[:5],
            "stats": self.stats,
            "recent_thinking": [
                {
                    "time": t.get("time"),
                    "severity": t.get("diagnosis", {}).get("severity", "unknown"),
                    "observations_count": len(t.get("observations", [])),
                    "observations": t.get("observations", [])[:8],
                    "recommendations_count": len(t.get("recommendations", [])),
                    "snapshot": t.get("context_snapshot", {}),
                }
                for t in recent
            ],
            "evolution_insights": self.evolution_insights[-5:],
        }


return_rate_agent = TitanReturnRateAgent()
