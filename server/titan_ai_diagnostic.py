import os
import json
import logging
from datetime import datetime
from server.titan_prompt_library import AI_DIAGNOSTIC_PROMPT

logger = logging.getLogger("TitanAIDiagnostic")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAGNOSTIC_PATH = os.path.join(BASE_DIR, "data", "titan_ai_diagnostics.json")

DIAGNOSTIC_MODEL = "gpt-4o-mini"


class TitanAIDiagnostic:

    def __init__(self):
        self.reports = []
        self.latest_report = {}
        self.stats = {
            "total_diagnostics": 0,
            "last_diagnostic": "",
            "avg_health_score": 0,
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(DIAGNOSTIC_PATH):
                with open(DIAGNOSTIC_PATH, "r") as f:
                    data = json.load(f)
                self.reports = data.get("reports", [])[-20:]
                self.latest_report = data.get("latest_report", {})
                self.stats = data.get("stats", self.stats)
                logger.info(f"AIDiagnostic loaded: {self.stats['total_diagnostics']} reports")
        except Exception as e:
            logger.warning(f"AIDiagnostic load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(DIAGNOSTIC_PATH), exist_ok=True)
            data = {
                "reports": self.reports[-20:],
                "latest_report": self.latest_report,
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(DIAGNOSTIC_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def collect_system_snapshot(self, modules):
        snapshot = {}
        try:
            ml_status = modules.get("ml_engine")
            if ml_status:
                s = ml_status.get_status() if hasattr(ml_status, 'get_status') else {}
                snapshot["ml"] = {
                    "accuracy": s.get("accuracy", 0),
                    "f1": s.get("f1", 0),
                    "samples": s.get("samples", 0),
                    "train_count": s.get("train_count", 0),
                    "is_trained": s.get("is_trained", False),
                }
        except Exception:
            snapshot["ml"] = {"error": "unavailable"}

        try:
            pt = modules.get("paper_trader")
            if pt:
                summary = pt.get_portfolio_summary() if hasattr(pt, 'get_portfolio_summary') else {}
                snapshot["portfolio"] = {
                    "equity": summary.get("equity", 0),
                    "total_pnl_pct": summary.get("total_pnl_pct", 0),
                    "win_rate": summary.get("win_rate", 0),
                    "total_wins": getattr(pt, 'total_wins', 0),
                    "total_losses": getattr(pt, 'total_losses', 0),
                    "active_positions": len(pt.positions) if hasattr(pt, 'positions') else 0,
                    "consecutive_wins": getattr(pt, 'consecutive_wins', 0),
                    "consecutive_losses": getattr(pt, 'consecutive_losses', 0),
                }
        except Exception:
            snapshot["portfolio"] = {"error": "unavailable"}

        try:
            rt = modules.get("return_target")
            if rt:
                s = rt.get_status() if hasattr(rt, 'get_status') else {}
                snapshot["return_target"] = {
                    "annualized_return_pct": s.get("annualized_return_pct", 0),
                    "target_pct": s.get("target_pct", 12),
                    "aggression_multiplier": s.get("aggression_multiplier", 1.0),
                    "days_tracked": s.get("days_tracked", 0),
                }
        except Exception:
            snapshot["return_target"] = {"error": "unavailable"}

        try:
            rb = modules.get("risk_budget")
            if rb:
                s = rb.get_status() if hasattr(rb, 'get_status') else {}
                total_cap = s.get("total_capital", 10000)
                budgets = s.get("strategy_budgets", {})
                total_used = sum(b.get("used", 0) for b in budgets.values())
                frozen_list = [name for name, b in budgets.items() if b.get("frozen")]
                utilization = round(total_used / total_cap * 100, 1) if total_cap > 0 else 0
                snapshot["risk_budget"] = {
                    "total_capital": total_cap,
                    "total_drawdown": s.get("total_drawdown_pct", 0),
                    "max_drawdown_ever": s.get("max_drawdown_ever_pct", 0),
                    "frozen_strategies": frozen_list,
                    "capital_utilization": utilization,
                    "daily_pnl": s.get("daily_pnl", 0),
                    "daily_remaining": s.get("daily_remaining", 0),
                    "rebalance_count": s.get("rebalance_count", 0),
                    "strategy_budgets": {k: {"allocation_pct": v.get("allocation_pct", 0), "used": v.get("used", 0), "frozen": v.get("frozen", False)} for k, v in budgets.items()},
                }
        except Exception:
            snapshot["risk_budget"] = {"error": "unavailable"}

        try:
            disp = modules.get("dispatcher")
            if disp:
                snapshot["dispatcher"] = {
                    "current_regime": getattr(disp, 'current_regime', 'unknown'),
                    "active_strategies": getattr(disp, 'active_strategies', []),
                }
        except Exception:
            snapshot["dispatcher"] = {"error": "unavailable"}

        try:
            syn = modules.get("synapse")
            if syn:
                s = syn.get_status() if hasattr(syn, 'get_status') else {}
                snapshot["synapse"] = {
                    "total_broadcasts": s.get("total_broadcasts", 0),
                    "active_rules": s.get("active_rules", 0),
                    "strategy_performance": s.get("strategy_performance", {}),
                }
        except Exception:
            snapshot["synapse"] = {"error": "unavailable"}

        try:
            sq = modules.get("signal_quality")
            if sq:
                s = sq.get_status() if hasattr(sq, 'get_status') else {}
                snapshot["signal_quality"] = {
                    "avg_quality": s.get("avg_quality", 0),
                    "total_signals": s.get("total_evaluated", s.get("total_signals", 0)),
                    "calibration_count": s.get("calibrated_conditions", s.get("calibration_count", 0)),
                    "total_conditions": s.get("total_conditions", 0),
                    "condition_count": s.get("condition_count", 0),
                    "hot_conditions": len(s.get("hot_conditions", [])),
                    "cold_conditions": len(s.get("cold_conditions", [])),
                }
        except Exception:
            snapshot["signal_quality"] = {"error": "unavailable"}

        try:
            coord = modules.get("ai_coordinator")
            if coord:
                snapshot["coordinator"] = {
                    "risk_level": getattr(coord, 'recommendations', {}).get("risk_level", "standard"),
                    "throttle_level": getattr(coord, 'recommendations', {}).get("throttle_level", "normal"),
                    "size_multiplier": getattr(coord, 'recommendations', {}).get("size_multiplier", 1.0),
                }
        except Exception:
            snapshot["coordinator"] = {"error": "unavailable"}

        try:
            ud = modules.get("unified_decision")
            if ud:
                s = ud.get_status() if hasattr(ud, 'get_status') else {}
                last_dec = s.get("last_decision", {})
                ud_stats = s.get("stats", {})
                recent_decs = s.get("recent_decisions", [])
                snapshot["unified_decision"] = {
                    "mode": last_dec.get("mode", "unknown"),
                    "total_decisions": ud_stats.get("total_decisions", 0),
                    "mode_counts": ud_stats.get("mode_counts", {}),
                    "last_decision_time": ud_stats.get("last_decision_time", ""),
                    "current_thresholds": {
                        "long": last_dec.get("long_threshold", 72),
                        "short": last_dec.get("short_threshold", 55),
                    },
                    "enable_long": last_dec.get("enable_long", True),
                    "enable_short": last_dec.get("enable_short", True),
                    "enable_grid": last_dec.get("enable_grid", True),
                    "reasons": last_dec.get("reasons", [])[:5],
                    "recent_modes": [d.get("mode", "unknown") for d in recent_decs[-5:]],
                }
        except Exception:
            snapshot["unified_decision"] = {"error": "unavailable"}

        try:
            const = modules.get("constitution")
            if const:
                s = const.get_status() if hasattr(const, 'get_status') else {}
                snapshot["constitution"] = {
                    "permanent_breaker": s.get("permanent_breaker", False),
                    "daily_breaker": s.get("daily_breaker", False),
                    "onchain_emergency": s.get("onchain_emergency", False),
                    "peak_equity": s.get("total_peak_equity", s.get("peak_equity", 0)),
                    "daily_start_equity": s.get("daily_start_equity", 0),
                    "risk_limits": s.get("risk_limits", {}),
                }
        except Exception:
            snapshot["constitution"] = {"error": "unavailable"}

        try:
            aw = modules.get("adaptive_weights")
            if aw:
                w = aw.get_adaptive_weights() if hasattr(aw, 'get_adaptive_weights') else {}
                snapshot["adaptive_weights"] = {
                    "w_ml": w.get("w_ml", 0.35),
                    "w_rule": w.get("w_rule", 0.65),
                    "ml_override": w.get("ml_weight_override"),
                }
        except Exception:
            snapshot["adaptive_weights"] = {"error": "unavailable"}

        try:
            fb = modules.get("feedback_engine")
            if fb:
                rolling_acc = fb.get_rolling_accuracy() if hasattr(fb, 'get_rolling_accuracy') else None
                fb_status = fb.get_status() if hasattr(fb, 'get_status') else {}
                snapshot["feedback"] = {
                    "rolling_accuracy": rolling_acc if rolling_acc is not None else 0,
                    "has_data": rolling_acc is not None,
                    "total_predictions": fb_status.get("total_predictions", len(getattr(fb, 'accuracy_history', []))),
                    "per_class_accuracy": fb_status.get("per_class_accuracy", {}),
                    "suggestions_count": len(fb_status.get("suggestions", [])),
                }
        except Exception:
            snapshot["feedback"] = {"error": "unavailable"}

        try:
            market = modules.get("market_snapshot", {})
            btc_pulse = market.get("btc_pulse", {})
            snapshot["market"] = {
                "btc_price": btc_pulse.get("price", 0),
                "btc_change": btc_pulse.get("change", "0%"),
                "fng": btc_pulse.get("fng", 50),
                "total_scanned": market.get("total_scanned", 0),
                "scan_mode": market.get("scan_mode", "unknown"),
            }
        except Exception:
            snapshot["market"] = {"error": "unavailable"}

        try:
            mega = modules.get("mega_backtest")
            if mega:
                snapshot["mega_backtest"] = {
                    "best_calmar": getattr(mega, 'best_calmar', 0),
                    "generations": getattr(mega, 'generation', 0),
                }
        except Exception:
            snapshot["mega_backtest"] = {"error": "unavailable"}

        try:
            grid = modules.get("grid_engine")
            if grid:
                snapshot["grid"] = {
                    "active_grids": len(grid.active_grids) if hasattr(grid, 'active_grids') else 0,
                }
        except Exception:
            snapshot["grid"] = {"error": "unavailable"}

        try:
            rra = modules.get("return_rate_agent")
            if rra:
                s = rra.get_status() if hasattr(rra, 'get_status') else {}
                rra_diag = s.get("current_diagnosis", {})
                rra_stats = s.get("stats", {})
                snapshot["return_rate_agent"] = {
                    "severity": rra_diag.get("severity", "unknown"),
                    "total_thoughts": rra_stats.get("total_thoughts", 0),
                    "total_recommendations": rra_stats.get("total_recommendations", 0),
                    "applied_recommendations": rra_stats.get("applied_recommendations", 0),
                    "consecutive_below_target": rra_stats.get("consecutive_below_target", 0),
                    "last_think_time": rra_stats.get("last_think_time", ""),
                    "latest_observations": [t.get("observations", [])[:3] for t in s.get("recent_thinking", [])[-1:]] if s.get("recent_thinking") else [],
                }
        except Exception:
            snapshot["return_rate_agent"] = {"error": "unavailable"}

        return snapshot

    def run_diagnostic(self, modules):

        snapshot = self.collect_system_snapshot(modules)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prev_report = self.latest_report.get("diagnosis", {}) if self.latest_report else {}
        prev_health = prev_report.get("health_score", 0) if prev_report else 0

        prompt = f"""你是一个顶级量化基金的首席技术官(CTO)，负责诊断和优化一个加密货币量化交易系统。

当前时间: {now}
上次诊断健康分: {prev_health}/100

== 重要背景 ==
系统正处于【阶段零观察期】(2026-02-26启动)，此阶段的核心原则：
1. 不做代码修改，不调整参数，只观察和积累数据
2. 信号层v3.0于2月24日上线，修复前的历史数据(准确率29.2%)不代表当前系统能力
3. 信号门槛当前为72分(FNG<15时自动提升到72)，这是有意为之的高质量过滤
4. 资金利用率低是正常的——阶段零期间保守运行，不追求资金效率
5. ML权重是动态的(AdaptiveWeightManager)，不是固定值，不要建议设定固定权重
6. MM模型当前R²=-0.001，已被质量门控跳过，纯规则引擎运行
7. 任何"降低信号门槛"、"提升激进度"、"最大化风险参与度"的建议在阶段零期间都是错误的
8. 诊断评分应区分"修复前历史数据的拖累"和"当前系统的实际状态"

== 系统实时快照 ==
{json.dumps(snapshot, ensure_ascii=False, indent=1)}

请从以下维度对系统进行全面诊断，用中文回答，JSON格式输出:

{{
  "health_score": 0-100的整体健康分,
  "severity": "healthy/warning/alert/critical",
  "summary": "一句话总结当前系统状态",
  "vs_last": "与上次对比: 改善/恶化/持平 + 原因",
  "dimensions": {{
    "trading_performance": {{
      "score": 0-100,
      "status": "状态描述",
      "issues": ["问题1", "问题2"],
      "suggestions": ["建议1"]
    }},
    "ml_model_health": {{
      "score": 0-100,
      "status": "状态描述",
      "issues": [],
      "suggestions": []
    }},
    "risk_control": {{
      "score": 0-100,
      "status": "状态描述",
      "issues": [],
      "suggestions": []
    }},
    "strategy_allocation": {{
      "score": 0-100,
      "status": "状态描述",
      "issues": [],
      "suggestions": []
    }},
    "signal_quality": {{
      "score": 0-100,
      "status": "状态描述",
      "issues": [],
      "suggestions": []
    }},
    "capital_efficiency": {{
      "score": 0-100,
      "status": "状态描述",
      "issues": [],
      "suggestions": []
    }},
    "evolution_progress": {{
      "score": 0-100,
      "status": "状态描述",
      "issues": [],
      "suggestions": []
    }}
  }},
  "top_priorities": [
    {{"priority": 1, "action": "最紧急的改进建议", "impact": "high/medium/low", "auto_applicable": true/false}},
    {{"priority": 2, "action": "...", "impact": "...", "auto_applicable": false}},
    {{"priority": 3, "action": "...", "impact": "...", "auto_applicable": false}}
  ],
  "market_outlook": "基于当前市场数据的简短展望和操作建议"
}}

注意:
1. 基于实际数据分析，不要泛泛而谈
2. health_score要客观: 胜率<30%扣分，回撤>5%扣分，ML准确率<60%扣分
3. 每个维度的suggestions必须具体可操作，格式为"动作+目标+预期效果"，例如"将ML权重从0.5降至0.3以减少错误信号影响"
4. auto_applicable=true表示系统可以自动执行的建议(如调整参数、冻结策略、触发训练等)
5. issues每个维度至少给出2-3个具体问题，引用实际数值
6. suggestions每个维度至少给出1-2个具体修复方案"""

        try:
            from server.titan_llm_client import chat_json
            diagnosis = chat_json(
                module="ai_diagnostic",
                messages=[
                    {"role": "system", "content": AI_DIAGNOSTIC_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )
            if not diagnosis:
                diagnosis = {
                    "health_score": 50,
                    "severity": "warning",
                    "summary": "AI诊断输出解析失败",
                    "dimensions": {},
                    "top_priorities": [],
                }
        except Exception as e:
            logger.error(f"AI diagnostic call failed: {e}")
            return {"error": str(e), "status": "failed"}

        report = {
            "timestamp": now,
            "diagnosis": diagnosis,
            "snapshot_summary": {
                "btc_price": snapshot.get("market", {}).get("btc_price", 0),
                "fng": snapshot.get("market", {}).get("fng", 0),
                "equity": snapshot.get("portfolio", {}).get("equity", 0),
                "win_rate": snapshot.get("portfolio", {}).get("win_rate", 0),
                "ml_accuracy": snapshot.get("ml", {}).get("accuracy", 0),
                "regime": snapshot.get("dispatcher", {}).get("current_regime", "unknown"),
                "active_positions": snapshot.get("portfolio", {}).get("active_positions", 0),
            },
        }

        self.latest_report = report
        self.reports.append(report)
        self.reports = self.reports[-20:]

        self.stats["total_diagnostics"] += 1
        self.stats["last_diagnostic"] = now
        health = diagnosis.get("health_score", 0)
        prev_avg = self.stats.get("avg_health_score", 0)
        n = self.stats["total_diagnostics"]
        self.stats["avg_health_score"] = round(((prev_avg * (n - 1)) + health) / n, 1)

        self.save()
        logger.info(f"AI Diagnostic complete: health={health}, severity={diagnosis.get('severity')}")

        health_trend = []
        for r in self.reports[-10:]:
            rd = r.get("diagnosis", {})
            health_trend.append({
                "timestamp": r.get("timestamp", ""),
                "health_score": rd.get("health_score", 0),
                "severity": rd.get("severity", "unknown"),
            })

        result = {
            "status": "ok",
            "health_score": health,
            "severity": diagnosis.get("severity", "unknown"),
            "summary": diagnosis.get("summary", ""),
            "vs_last": diagnosis.get("vs_last", ""),
            "dimensions": diagnosis.get("dimensions", {}),
            "top_priorities": diagnosis.get("top_priorities", []),
            "market_outlook": diagnosis.get("market_outlook", ""),
            "health_trend": health_trend,
            "total_diagnostics": self.stats["total_diagnostics"],
            "avg_health_score": self.stats["avg_health_score"],
        }
        return result

    def get_status(self):
        return {
            "stats": self.stats,
            "latest_report": self.latest_report,
            "report_count": len(self.reports),
        }

    def get_history(self):
        return {
            "reports": self.reports,
            "stats": self.stats,
        }


ai_diagnostic = TitanAIDiagnostic()
