import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("TitanBacktester")


class TitanBacktester:

    def run_full_backtest(self, days=30) -> Dict[str, Any]:
        from server.titan_db import db_connection

        report = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backtest_days": days,
            "signal_quality": {},
            "debate_accuracy": {},
            "strategy_performance": {},
            "auto_proposals": [],
            "pending_proposals": [],
            "summary": "",
        }

        try:
            trades = self._load_trades(days)
            rejected = self._load_rejected_signals(days)
            logger.info(f"[Backtest] 加载 {len(trades)} 笔交易, {len(rejected)} 条被拒信号 (过去{days}天)")

            report["signal_quality"] = self._backtest_signal_quality(trades, rejected)
            report["strategy_performance"] = self._backtest_strategy_performance(trades)
            report["debate_accuracy"] = self._backtest_debate_system(days)

            proposals = self._auto_optimize(report)
            report["auto_proposals"] = [p for p in proposals if p.get("auto_adopt") and p["risk"] == "low"]
            report["pending_proposals"] = [p for p in proposals if not p.get("auto_adopt")]

            report["summary"] = self._generate_summary(report, trades)

            self._save_report(report)

        except Exception as e:
            logger.error(f"[Backtest] 回测失败: {e}")
            report["summary"] = f"回测执行异常: {e}"

        return report

    def _load_trades(self, days: int) -> List[Dict]:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT id, symbol, direction, entry_price, exit_price,
                       tp_price, sl_price, pnl_pct, pnl_value, result,
                       open_time, close_time, hold_hours, extra,
                       signal_direction_4h_result, btc_macro_trend_at_entry,
                       peak_unrealized_pnl
                FROM trades
                WHERE open_time >= NOW() - INTERVAL '%s days'
                  AND close_time IS NOT NULL
                ORDER BY close_time DESC
            """ % int(days))
            return [dict(r) for r in cur.fetchall()]

    def _load_rejected_signals(self, days: int) -> List[Dict]:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT symbol, direction, signal_score, ml_confidence,
                       rejected_by, rejection_reason, btc_macro_trend,
                       fng_value, regime, price_at_rejection,
                       price_24h_later, price_change_pct, rejection_was_correct
                FROM rejected_signals
                WHERE created_at >= NOW() - INTERVAL '%s days'
                ORDER BY created_at DESC
            """ % int(days))
            return [dict(r) for r in cur.fetchall()]

    def _backtest_signal_quality(self, trades: List[Dict], rejected: List[Dict]) -> Dict[str, Any]:
        results = {}

        if not trades:
            return {"no_data": {"accuracy": 0, "sample_size": 0, "significant": False}}

        wins = [t for t in trades if (t.get("pnl_pct") or 0) > 0]
        total_acc = len(wins) / len(trades) if trades else 0
        results["overall"] = {
            "accuracy": round(total_acc, 4),
            "sample_size": len(trades),
            "significant": len(trades) >= 30,
            "avg_pnl_pct": round(sum(t.get("pnl_pct", 0) or 0 for t in trades) / len(trades), 4) if trades else 0,
        }

        conditions = {
            "long_trades": lambda t: t.get("direction") == "long",
            "short_trades": lambda t: t.get("direction") == "short",
            "btc_bullish": lambda t: t.get("btc_macro_trend_at_entry") == "bullish",
            "btc_bearish": lambda t: t.get("btc_macro_trend_at_entry") in ("bearish", "crash"),
            "hold_short": lambda t: (t.get("hold_hours") or 0) < 4,
            "hold_medium": lambda t: 4 <= (t.get("hold_hours") or 0) <= 12,
            "hold_long": lambda t: (t.get("hold_hours") or 0) > 12,
        }

        for extra_field_cond in [
            ("fng_extreme", lambda t: self._extra_val(t, "fng_at_entry", 50) < 20),
            ("fng_normal", lambda t: self._extra_val(t, "fng_at_entry", 50) >= 40),
            ("score_high", lambda t: self._extra_val(t, "signal_score", 0) >= 80),
            ("score_mid", lambda t: 73 <= self._extra_val(t, "signal_score", 0) < 80),
            ("volatile_regime", lambda t: self._extra_val(t, "regime", "") == "volatile"),
            ("trending_regime", lambda t: self._extra_val(t, "regime", "") == "trending"),
            ("ranging_regime", lambda t: self._extra_val(t, "regime", "") == "ranging"),
        ]:
            conditions[extra_field_cond[0]] = extra_field_cond[1]

        for name, cond_fn in conditions.items():
            filtered = [t for t in trades if cond_fn(t)]
            if len(filtered) >= 3:
                w = [t for t in filtered if (t.get("pnl_pct") or 0) > 0]
                acc = len(w) / len(filtered)
                avg_pnl = sum(t.get("pnl_pct", 0) or 0 for t in filtered) / len(filtered)
                results[name] = {
                    "accuracy": round(acc, 4),
                    "sample_size": len(filtered),
                    "significant": len(filtered) >= 10,
                    "avg_pnl_pct": round(avg_pnl, 4),
                }

        verified = [r for r in rejected if r.get("rejection_was_correct") is not None]
        if verified:
            correct_rejections = [r for r in verified if r.get("rejection_was_correct")]
            results["rejection_accuracy"] = {
                "accuracy": round(len(correct_rejections) / len(verified), 4),
                "sample_size": len(verified),
                "significant": len(verified) >= 20,
            }

        by_gate = {}
        for r in rejected:
            gate = r.get("rejected_by", "unknown")
            if gate not in by_gate:
                by_gate[gate] = {"total": 0, "correct": 0, "verified": 0}
            by_gate[gate]["total"] += 1
            if r.get("rejection_was_correct") is not None:
                by_gate[gate]["verified"] += 1
                if r.get("rejection_was_correct"):
                    by_gate[gate]["correct"] += 1

        for gate, stats in by_gate.items():
            if stats["verified"] >= 3:
                results[f"gate_{gate}"] = {
                    "accuracy": round(stats["correct"] / stats["verified"], 4),
                    "sample_size": stats["verified"],
                    "total_rejected": stats["total"],
                    "significant": stats["verified"] >= 10,
                }

        return results

    def _backtest_strategy_performance(self, trades: List[Dict]) -> Dict[str, Any]:
        results = {}
        by_strategy = {}

        for t in trades:
            extra = t.get("extra") or {}
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = {}
            strategy = extra.get("strategy", "unknown")
            if strategy not in by_strategy:
                by_strategy[strategy] = []
            by_strategy[strategy].append(t)

        for strat, strat_trades in by_strategy.items():
            wins = [t for t in strat_trades if (t.get("pnl_pct") or 0) > 0]
            pnls = [t.get("pnl_pct", 0) or 0 for t in strat_trades]
            results[strat] = {
                "trade_count": len(strat_trades),
                "win_rate": round(len(wins) / len(strat_trades), 4) if strat_trades else 0,
                "avg_pnl_pct": round(sum(pnls) / len(pnls), 4) if pnls else 0,
                "total_pnl_pct": round(sum(pnls), 4),
                "best_trade": round(max(pnls), 4) if pnls else 0,
                "worst_trade": round(min(pnls), 4) if pnls else 0,
            }

        return results

    def _backtest_debate_system(self, days: int) -> Dict[str, Any]:
        from server.titan_db import db_connection
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT t.pnl_value, t.pnl_pct, d.verdict, d.bull_score,
                           d.bear_score, d.confidence
                    FROM trades t
                    JOIN debate_records d ON t.symbol = d.symbol
                    WHERE t.close_time IS NOT NULL
                      AND t.open_time >= NOW() - INTERVAL '%s days'
                      AND d.created_at >= t.open_time - INTERVAL '5 minutes'
                      AND d.created_at <= t.open_time + INTERVAL '5 minutes'
                """ % int(days))
                rows = [dict(r) for r in cur.fetchall()]

            if not rows:
                return {
                    "accuracy": 0,
                    "sample_size": 0,
                    "benchmark": 0,
                    "message": "暂无辩论+交易匹配数据（Shadow模式刚上线）",
                }

            correct = 0
            total = len(rows)
            for r in rows:
                predicted_win = r.get("verdict") == "execute" and (r.get("confidence") or 0) > 0.6
                actual_win = (r.get("pnl_pct") or 0) > 0
                if predicted_win == actual_win:
                    correct += 1

            return {
                "accuracy": round(correct / total, 4) if total > 0 else 0,
                "sample_size": total,
                "benchmark": round(len([r for r in rows if (r.get("pnl_pct") or 0) > 0]) / total, 4) if total > 0 else 0,
            }
        except Exception as e:
            logger.warning(f"[Backtest] 辩论系统回测异常: {e}")
            return {"accuracy": 0, "sample_size": 0, "error": str(e)}

    def _auto_optimize(self, report: Dict) -> List[Dict]:
        proposals = []
        sq = report.get("signal_quality", {})

        hold_short = sq.get("hold_short", {})
        hold_long = sq.get("hold_long", {})
        if (hold_short.get("sample_size", 0) >= 5 and hold_long.get("sample_size", 0) >= 5):
            short_acc = hold_short.get("accuracy", 0.5)
            long_acc = hold_long.get("accuracy", 0.5)
            if short_acc < 0.25 and long_acc > 0.40:
                proposals.append({
                    "type": "hold_time_filter",
                    "target": "min_hold_signal",
                    "current": "none",
                    "suggested": "短持仓(<4h)胜率过低，建议Phase 1加入时间过滤",
                    "evidence": f"短持仓胜率{short_acc:.0%} vs 长持仓{long_acc:.0%}",
                    "confidence": 0.75,
                    "risk": "medium",
                    "auto_adopt": False,
                })

        long_trades = sq.get("long_trades", {})
        short_trades = sq.get("short_trades", {})
        if (long_trades.get("sample_size", 0) >= 5 and short_trades.get("sample_size", 0) >= 5):
            long_acc = long_trades.get("accuracy", 0.5)
            short_acc = short_trades.get("accuracy", 0.5)
            if short_acc < 0.20:
                proposals.append({
                    "type": "direction_filter",
                    "target": "short_signal_threshold",
                    "current": 73,
                    "suggested": 78,
                    "evidence": f"做空胜率{short_acc:.0%}(n={short_trades['sample_size']})，做多胜率{long_acc:.0%}(n={long_trades['sample_size']})",
                    "confidence": 0.70,
                    "risk": "medium",
                    "auto_adopt": False,
                })

        for gate_key, gate_data in sq.items():
            if gate_key.startswith("gate_") and gate_data.get("verified", gate_data.get("sample_size", 0)) >= 10:
                acc = gate_data.get("accuracy", 0)
                if acc < 0.40:
                    proposals.append({
                        "type": "gate_review",
                        "target": gate_key.replace("gate_", ""),
                        "current": f"accuracy={acc:.0%}",
                        "suggested": "审查该过滤器规则，可能过度拒绝",
                        "evidence": f"拒绝准确率仅{acc:.0%}(n={gate_data.get('sample_size', 0)})",
                        "confidence": 0.65,
                        "risk": "low",
                        "auto_adopt": False,
                    })

        for p in proposals:
            self._save_proposal(p)

        return proposals

    def _generate_summary(self, report: Dict, trades: List[Dict]) -> str:
        sq = report.get("signal_quality", {})
        overall = sq.get("overall", {})
        debate = report.get("debate_accuracy", {})

        parts = [
            f"回测范围：过去{report['backtest_days']}天",
            f"总交易数：{overall.get('sample_size', 0)}笔",
            f"整体胜率：{overall.get('accuracy', 0):.1%}",
            f"平均PnL：{overall.get('avg_pnl_pct', 0):.2f}%",
        ]

        if debate.get("sample_size", 0) > 0:
            parts.append(f"辩论系统准确率：{debate.get('accuracy', 0):.1%}(n={debate['sample_size']})")
        else:
            parts.append("辩论系统：暂无匹配数据")

        best_cond = None
        best_acc = 0
        worst_cond = None
        worst_acc = 1.0
        for k, v in sq.items():
            if k in ("overall", "no_data", "rejection_accuracy") or k.startswith("gate_"):
                continue
            if not v.get("significant"):
                continue
            acc = v.get("accuracy", 0.5)
            if acc > best_acc:
                best_acc = acc
                best_cond = k
            if acc < worst_acc:
                worst_acc = acc
                worst_cond = k

        if best_cond:
            parts.append(f"最佳条件：{best_cond} {best_acc:.1%}")
        if worst_cond:
            parts.append(f"最差条件：{worst_cond} {worst_acc:.1%}")

        auto_count = len(report.get("auto_proposals", []))
        pending_count = len(report.get("pending_proposals", []))
        parts.append(f"自动优化：{auto_count}项 | 待审核：{pending_count}项")

        return " | ".join(parts)

    def _save_report(self, report: Dict):
        from server.titan_db import db_connection
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO backtest_reports
                    (backtest_days, signal_accuracy, debate_accuracy,
                     strategy_performance, auto_optimizations,
                     pending_proposals, summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    report["backtest_days"],
                    json.dumps(report["signal_quality"], ensure_ascii=False, default=str),
                    report["debate_accuracy"].get("accuracy", 0) if isinstance(report["debate_accuracy"], dict) else 0,
                    json.dumps(report["strategy_performance"], ensure_ascii=False, default=str),
                    len(report.get("auto_proposals", [])),
                    len(report.get("pending_proposals", [])),
                    report.get("summary", ""),
                ))
                conn.commit()
            logger.info("[Backtest] 报告已保存到DB")
        except Exception as e:
            logger.warning(f"[Backtest] 保存报告失败: {e}")

    def _save_proposal(self, proposal: Dict):
        from server.titan_db import db_connection
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO evolution_proposals
                    (proposal_type, target, evidence,
                     confidence, risk_level, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    proposal.get("type", "backtest"),
                    proposal.get("target", ""),
                    proposal.get("evidence", ""),
                    proposal.get("confidence", 0.5),
                    proposal.get("risk", "medium"),
                    "auto_adopted" if proposal.get("auto_adopt") else "pending",
                ))
                conn.commit()
        except Exception as e:
            logger.debug(f"[Backtest] 保存proposal失败: {e}")

    def _extra_val(self, trade: Dict, key: str, default=None):
        extra = trade.get("extra") or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                return default
        ei = extra.get("entry_indicators", {})
        return ei.get(key, extra.get(key, default))
