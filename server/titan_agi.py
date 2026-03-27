import os
import json
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from server.titan_prompt_library import AGI_REFLECTION_PROMPT, PHASE_ZERO_CONTEXT
from server.titan_db import db_connection

logger = logging.getLogger("TitanAGI")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_PATH = os.path.join(BASE_DIR, "data", "titan_learning_journal.json")
REFLECTION_PATH = os.path.join(BASE_DIR, "data", "titan_reflections.json")


class TitanMetaCognition:
    def __init__(self):
        self.decision_log = []
        self.reflection_history = []
        self.learning_journal = []
        self.performance_patterns = defaultdict(list)
        self.self_improvement_queue = []
        self.cognitive_state = {
            "confidence_calibration": 1.0,
            "risk_appetite": "moderate",
            "learning_rate": 0.5,
            "last_reflection": None,
            "total_reflections": 0,
            "insight_count": 0,
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(JOURNAL_PATH):
                with open(JOURNAL_PATH, "r") as f:
                    data = json.load(f)
                self.learning_journal = data.get("journal", [])
                self.cognitive_state.update(data.get("cognitive_state", {}))
                self.performance_patterns = defaultdict(list, data.get("patterns", {}))
                self.self_improvement_queue = data.get("improvements", [])
                logger.info(f"AGI学习日志加载: {len(self.learning_journal)}条记录")
        except Exception as e:
            logger.warning(f"AGI学习日志加载失败: {e}")

        try:
            if os.path.exists(REFLECTION_PATH):
                with open(REFLECTION_PATH, "r") as f:
                    self.reflection_history = json.load(f)
                logger.info(f"AGI反思历史加载: {len(self.reflection_history)}条")
        except Exception as e:
            logger.warning(f"AGI反思历史加载失败: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
            journal_data = {
                "journal": self.learning_journal[-500:],
                "cognitive_state": self.cognitive_state,
                "patterns": dict(self.performance_patterns),
                "improvements": self.self_improvement_queue[-50:],
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(JOURNAL_PATH, "w") as f:
                json.dump(journal_data, f, ensure_ascii=False, indent=2)

            with open(REFLECTION_PATH, "w") as f:
                json.dump(self.reflection_history[-100:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"AGI数据保存失败: {e}")

    def record_decision(self, symbol, score, direction, reasons, context):
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "symbol": symbol,
            "score": score,
            "direction": direction,
            "reasons": reasons,
            "context": {
                "regime": context.get("regime", "未知"),
                "fng": context.get("fng", 50),
                "confluence_level": context.get("confluence_level", "未知"),
                "veto_active": context.get("veto_active", False),
                "funding_rate": context.get("funding_rate"),
                "ml_confidence": context.get("ml_confidence", 0),
            },
            "outcome": None,
        }
        self.decision_log.append(entry)
        if len(self.decision_log) > 1000:
            self.decision_log = self.decision_log[-1000:]
        return entry

    def record_outcome(self, symbol, pnl_pct, was_correct):
        for entry in reversed(self.decision_log):
            if entry["symbol"] == symbol and entry["outcome"] is None:
                entry["outcome"] = {
                    "pnl_pct": pnl_pct,
                    "correct": was_correct,
                    "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                regime = entry["context"].get("regime", "未知")
                self.performance_patterns[regime].append({
                    "correct": was_correct,
                    "pnl": pnl_pct,
                    "score": entry["score"],
                    "confluence": entry["context"].get("confluence_level", "未知"),
                })

                if len(self.performance_patterns[regime]) > 200:
                    self.performance_patterns[regime] = self.performance_patterns[regime][-200:]
                break

    def _get_combat_data_context(self):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                        ROUND(SUM(CASE WHEN result='win' THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*),0) * 100, 1) as win_rate,
                        ROUND(SUM(COALESCE(pnl_value, 0))::numeric, 2) as total_pnl,
                        MAX(created_at) as last_trade_time
                    FROM trades
                    WHERE (extra->>'is_test_data')::boolean IS NOT TRUE
                """)
                r = cur.fetchone()
                if not r or r['total'] == 0:
                    return None

                cur.execute("""
                    SELECT strategy_type as strategy,
                        COUNT(*) as cnt,
                        SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                        ROUND(SUM(COALESCE(pnl_value, 0))::numeric, 2) as pnl
                    FROM trades
                    WHERE (extra->>'is_test_data')::boolean IS NOT TRUE
                    GROUP BY strategy_type ORDER BY cnt DESC
                """)
                strat_rows = cur.fetchall()

                strat_lines = []
                for s in (strat_rows or []):
                    total = s['cnt'] or 0
                    w = s['wins'] or 0
                    wr = round(w / total * 100, 1) if total > 0 else 0
                    strat_lines.append(f"  {s['strategy']}: {total}笔 胜率{wr}% PNL=${s['pnl']}")

                cur.execute("""
                    SELECT target, confidence, notes
                    FROM evolution_proposals
                    WHERE confidence >= 0.75 AND status = 'pending'
                    ORDER BY confidence DESC LIMIT 5
                """)
                evo_rows = cur.fetchall()
                evo_lines = []
                for e in (evo_rows or []):
                    notes = (e.get('notes') or '')[:60]
                    evo_lines.append(f"  [{e['confidence']}] {e['target']}: {notes}")

            days_silent = 0
            if r.get('last_trade_time'):
                try:
                    last_t = r['last_trade_time']
                    if hasattr(last_t, 'replace'):
                        days_silent = (datetime.now() - last_t.replace(tzinfo=None)).days
                except Exception:
                    pass

            context = (
                f"总交易: {r['total']}笔 | 胜率: {r['win_rate']}% | 总PNL: ${r['total_pnl']}\n"
                f"距上次交易: {days_silent}天\n"
                f"按策略:\n" + "\n".join(strat_lines)
            )
            if evo_lines:
                context += "\n高置信度进化提案(≥0.75):\n" + "\n".join(evo_lines)
            return context
        except Exception as e:
            logger.warning(f"AGI获取实战数据失败: {e}")
            return None

    def _get_evolution_context(self):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT target, suggested_value, confidence, notes
                    FROM evolution_proposals
                    WHERE confidence >= 0.75 AND status = 'pending'
                    ORDER BY confidence DESC LIMIT 10
                """)
                rows = cur.fetchall()
            if not rows:
                return ""
            lines = []
            for r in rows:
                notes = (r.get('notes') or '')[:80]
                lines.append(f"- [{r['confidence']}] {r['target']}={r.get('suggested_value','')}: {notes}")
            return "\n## 高置信度进化提案(待决策)\n" + "\n".join(lines)
        except Exception as e:
            logger.warning(f"AGI获取进化提案失败: {e}")
            return ""

    def self_reflect(self, recent_trades=None, ml_accuracy=None, governor_state=None):
        reflection = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "periodic_review",
            "findings": [],
            "recommendations": [],
            "confidence_adjustment": 0,
        }

        regime_performance = {}
        for regime, records in self.performance_patterns.items():
            if len(records) < 5:
                continue
            wins = sum(1 for r in records[-50:] if r.get("correct", False))
            total = len(records[-50:])
            win_rate = wins / total if total > 0 else 0
            avg_pnl = sum(r.get("pnl", 0) for r in records[-50:]) / total if total > 0 else 0
            regime_performance[regime] = {"win_rate": round(win_rate, 3), "avg_pnl": round(avg_pnl, 4), "count": total}

            if win_rate < 0.35:
                reflection["findings"].append(f"在{regime}环境中胜率仅{win_rate*100:.0f}%，建议回避")
                reflection["recommendations"].append({
                    "type": "avoid_regime",
                    "regime": regime,
                    "reason": f"历史胜率{win_rate*100:.0f}%低于阈值",
                })
            elif win_rate > 0.65:
                reflection["findings"].append(f"在{regime}环境中胜率高达{win_rate*100:.0f}%，可适当加仓")
                reflection["recommendations"].append({
                    "type": "increase_exposure",
                    "regime": regime,
                    "reason": f"历史胜率{win_rate*100:.0f}%表现优异",
                })

        if ml_accuracy is not None:
            if ml_accuracy < 45:
                reflection["findings"].append(f"ML准确率仅{ml_accuracy}%，低于随机水平，应降低ML权重")
                reflection["recommendations"].append({
                    "type": "reduce_ml_weight",
                    "current_accuracy": ml_accuracy,
                    "suggested_weight": 0.15,
                })
                reflection["confidence_adjustment"] = -0.1
            elif ml_accuracy > 60:
                reflection["findings"].append(f"ML准确率{ml_accuracy}%，表现优秀，可提高ML权重")
                reflection["recommendations"].append({
                    "type": "increase_ml_weight",
                    "current_accuracy": ml_accuracy,
                    "suggested_weight": 0.5,
                })
                reflection["confidence_adjustment"] = 0.1

        if governor_state:
            dd = governor_state.get("drawdown_pct", 0)
            mode = governor_state.get("mode", "normal")
            if dd > 6:
                reflection["findings"].append(f"回撤{dd}%接近系统上限8%，建议立即收缩，当前{mode}模式")
                reflection["recommendations"].append({
                    "type": "risk_reduction",
                    "severity": "critical",
                    "reason": f"回撤{dd}%需要立即收缩，距永久熔断仅{15-dd:.1f}%",
                })
                reflection["confidence_adjustment"] -= 0.15
            elif dd > 4:
                reflection["findings"].append(f"回撤{dd}%进入警戒区间，建议谨慎，当前{mode}模式")
                reflection["recommendations"].append({
                    "type": "drawdown_caution",
                    "severity": "warning",
                    "reason": f"回撤{dd}%，建议减少新开仓并收紧止损",
                })
                reflection["confidence_adjustment"] -= 0.05

        confluence_decisions = [d for d in self.decision_log[-100:] if d.get("outcome")]
        if confluence_decisions:
            strong_confluence = [d for d in confluence_decisions if "强共振" in d["context"].get("confluence_level", "")]
            weak_confluence = [d for d in confluence_decisions if d["context"].get("confluence_level") == "信号分歧"]

            if strong_confluence:
                sc_wins = sum(1 for d in strong_confluence if d["outcome"].get("correct", False))
                sc_rate = sc_wins / len(strong_confluence) if strong_confluence else 0
                reflection["findings"].append(f"强共振信号胜率: {sc_rate*100:.0f}% (样本{len(strong_confluence)})")

            if weak_confluence:
                wc_wins = sum(1 for d in weak_confluence if d["outcome"].get("correct", False))
                wc_rate = wc_wins / len(weak_confluence) if weak_confluence else 0
                reflection["findings"].append(f"分歧信号胜率: {wc_rate*100:.0f}% (样本{len(weak_confluence)})")

        veto_decisions = [d for d in self.decision_log[-200:] if d["context"].get("veto_active", False)]
        if veto_decisions:
            reflection["findings"].append(f"链上否决触发{len(veto_decisions)}次")

        self.cognitive_state["confidence_calibration"] = max(0.3, min(1.5,
            self.cognitive_state["confidence_calibration"] + reflection["confidence_adjustment"]))
        self.cognitive_state["last_reflection"] = reflection["time"]
        self.cognitive_state["total_reflections"] += 1

        if not reflection["findings"]:
            combat_data = self._get_combat_data_context()
            if combat_data:
                reflection["findings"].append(f"实战数据总结: {combat_data.split(chr(10))[0]}")
                lines = combat_data.split('\n')
                for line in lines[1:]:
                    line = line.strip()
                    if line:
                        reflection["findings"].append(line)
                reflection["recommendations"].append({
                    "type": "data_driven_analysis",
                    "reason": "基于DB实战数据生成的分析，非内存模式匹配",
                    "combat_data": combat_data,
                })
            else:
                reflection["findings"].append("系统刚启动，尚无交易数据可分析")

        reflection["regime_performance"] = regime_performance
        reflection["cognitive_state"] = dict(self.cognitive_state)

        self.reflection_history.append(reflection)
        self.cognitive_state["insight_count"] = len(reflection["findings"])

        self.save()
        logger.info(f"AGI自省完成: {len(reflection['findings'])}条发现, {len(reflection['recommendations'])}条建议")
        return reflection

    async def llm_deep_reflection(self, recent_data_summary):
        try:
            from server.titan_llm_client import chat

            recent_reflections = self.reflection_history[-3:]
            patterns_summary = {}
            for regime, records in self.performance_patterns.items():
                if records:
                    wins = sum(1 for r in records[-30:] if r.get("correct", False))
                    total = len(records[-30:])
                    patterns_summary[regime] = f"胜率{wins}/{total}={wins/total*100:.0f}%" if total > 0 else "无数据"

            combat_data = self._get_combat_data_context() or "暂无实战数据"
            evolution_context = self._get_evolution_context()

            prompt = PHASE_ZERO_CONTEXT + f"""你是Titan V18.2智能交易系统的自省引擎。请基于以下数据进行深度分析，提出具体的自我改进建议。

## 当前认知状态
- 置信度校准: {self.cognitive_state['confidence_calibration']}
- 风险偏好: {self.cognitive_state['risk_appetite']}
- 总反思次数: {self.cognitive_state['total_reflections']}

## 各环境胜率
{json.dumps(patterns_summary, ensure_ascii=False, indent=2)}

## 实战数据（DB真实统计）
{combat_data}

## 最近反思摘要
{json.dumps([r.get('findings', []) for r in recent_reflections], ensure_ascii=False)}

## 市场环境摘要
{recent_data_summary}
{evolution_context}

基于以上实战数据，必须给出：
1. 当前系统最大的3个问题（基于真实交易统计）
2. 每个问题的根因分析
3. 具体的改进建议（不允许说"继续观察"或"数据不足"）
4. 下一步应该优先学习什么？

用中文回答，简洁具体，每点至少2-3句话。"""

            insight = chat(
                module="agi_reflection",
                messages=[{"role": "system", "content": AGI_REFLECTION_PROMPT},
                          {"role": "user", "content": prompt}],
                json_mode=False,
                max_tokens=16000,
            )

            if not insight:
                return {"success": False, "error": "LLM returned empty response"}

            self.learning_journal.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "llm_deep_reflection",
                "insight": insight,
                "trigger": "scheduled",
                "status": "pending",
                "adopted_at": None,
                "quality_score": None,
            })

            if len(self.learning_journal) > 500:
                self.learning_journal = self.learning_journal[-500:]

            self.save()

            try:
                with db_connection() as (conn, cur):
                    cur.execute("""
                        INSERT INTO learning_journal (source, content, priority, consumed_by_cto)
                        VALUES (%s, %s, %s, false)
                    """, ("agi_reflection", insight[:5000], "high"))
                    conn.commit()
                logger.info(f"AGI反思已写入DB learning_journal")
            except Exception as db_err:
                logger.warning(f"AGI反思写入DB失败: {db_err}")

            logger.info(f"AGI深度反思完成（LLM）: {len(insight)}字")
            return {"success": True, "insight": insight}

        except Exception as e:
            logger.warning(f"LLM深度反思失败: {e}")
            return {"success": False, "error": str(e)}

    def run_deep_reflection_sync(self, recent_data_summary):
        try:
            from server.titan_llm_client import chat

            recent_reflections = self.reflection_history[-3:]
            patterns_summary = {}
            for regime, records in self.performance_patterns.items():
                if records:
                    wins = sum(1 for r in records[-30:] if r.get("correct", False))
                    total = len(records[-30:])
                    patterns_summary[regime] = f"胜率{wins}/{total}={wins/total*100:.0f}%" if total > 0 else "无数据"

            combat_data = self._get_combat_data_context() or "暂无实战数据"
            evolution_context = self._get_evolution_context()

            from server.titan_prompt_library import AGI_REFLECTION_PROMPT, PHASE_ZERO_CONTEXT
            prompt = PHASE_ZERO_CONTEXT + f"""你是Titan V18.2智能交易系统的自省引擎。请基于以下数据进行深度分析，提出具体的自我改进建议。

## 当前认知状态
- 置信度校准: {self.cognitive_state['confidence_calibration']}
- 风险偏好: {self.cognitive_state['risk_appetite']}
- 总反思次数: {self.cognitive_state['total_reflections']}

## 各环境胜率
{json.dumps(patterns_summary, ensure_ascii=False, indent=2)}

## 实战数据（DB真实统计）
{combat_data}

## 最近反思摘要
{json.dumps([r.get('findings', []) for r in recent_reflections], ensure_ascii=False)}

## 市场环境摘要
{recent_data_summary}
{evolution_context}

基于以上实战数据，必须给出：
1. 当前系统最大的3个问题（基于真实交易统计）
2. 每个问题的根因分析
3. 具体的改进建议（不允许说"继续观察"或"数据不足"）
4. 下一步应该优先学习什么？

用中文回答，简洁具体，每点至少2-3句话。"""

            insight = chat(
                module="agi_reflection",
                messages=[{"role": "system", "content": AGI_REFLECTION_PROMPT},
                          {"role": "user", "content": prompt}],
                json_mode=False,
                max_tokens=16000,
            )

            if not insight:
                return {"success": False, "error": "LLM returned empty response"}

            self.learning_journal.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "llm_deep_reflection",
                "insight": insight,
                "trigger": "daily_scheduled",
            })
            if len(self.learning_journal) > 500:
                self.learning_journal = self.learning_journal[-500:]
            self.save()

            try:
                with db_connection() as (conn, cur):
                    cur.execute("""
                        INSERT INTO learning_journal (source, content, priority, consumed_by_cto)
                        VALUES (%s, %s, %s, false)
                    """, ("agi_reflection", insight[:5000], "high"))
                    conn.commit()
            except Exception as db_err:
                logger.warning(f"AGI反思写入DB失败(sync): {db_err}")

            logger.info(f"AGI同步反思完成: {len(insight)}字")
            return {"success": True, "insight": insight}

        except Exception as e:
            logger.warning(f"AGI同步反思失败: {e}")
            return {"success": False, "error": str(e)}

    def get_active_recommendations(self):
        if not self.reflection_history:
            return []
        latest = self.reflection_history[-1]
        return latest.get("recommendations", [])

    def get_status(self):
        return {
            "cognitive_state": self.cognitive_state,
            "decision_count": len(self.decision_log),
            "journal_entries": len(self.learning_journal),
            "reflection_count": len(self.reflection_history),
            "patterns_tracked": len(self.performance_patterns),
            "active_recommendations": len(self.get_active_recommendations()),
            "latest_reflection": self.reflection_history[-1] if self.reflection_history else None,
            "latest_journal": self.learning_journal[-3:] if self.learning_journal else [],
            "improvement_queue": self.self_improvement_queue[-5:],
        }

    def get_learning_summary(self):
        total_decisions = len(self.decision_log)
        decided_with_outcome = len([d for d in self.decision_log if d.get("outcome")])
        correct = len([d for d in self.decision_log if (d.get("outcome") or {}).get("correct", False)])

        regime_summary = {}
        for regime, records in self.performance_patterns.items():
            if not records:
                continue
            wins = sum(1 for r in records if r.get("correct", False))
            total = len(records)
            regime_summary[regime] = {
                "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
                "total_trades": total,
                "avg_pnl": round(sum(r.get("pnl", 0) for r in records) / total, 4) if total > 0 else 0,
            }

        return {
            "total_decisions": total_decisions,
            "evaluated": decided_with_outcome,
            "correct": correct,
            "overall_accuracy": round(correct / decided_with_outcome * 100, 1) if decided_with_outcome > 0 else 0,
            "regime_breakdown": regime_summary,
            "confidence_calibration": self.cognitive_state["confidence_calibration"],
            "total_reflections": self.cognitive_state["total_reflections"],
        }


titan_agi = TitanMetaCognition()
